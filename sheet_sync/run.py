"""
Синхронизация кандидатов из листа «Кандидаты» Google Таблицы в БД.

Раз в минуту проверяет столбец L (с 3-й строки): если значение «Отправить» —
считает строку новым кандидатом, заменяет L на «Отправленно», вносит запись в БД,
отправляет автору заявки сообщение в Telegram и записывает id кандидата в ячейку A.

Запуск: из корня проекта
  python -m sheet_sync.run

Или в Docker: сервис sheet_sync (см. docker-compose.yml).
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if "/app" not in sys.path and Path("/app/utils").exists():
    sys.path.insert(0, "/app")

from utils.dates import format_datetime, parse_date
from utils.telegram import safe_send_message

_ENV = _ROOT / ".env"
if _ENV.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_ENV)
    except ImportError:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%d.%m.%Y %H:%M:%S",
)
logger = logging.getLogger("sheet_sync")

INTERVAL_SECONDS = 60

CANDIDATE_STATUS_LABELS = {
    "new": "Новая",
    "interview": "Собеседование",
    "hired": "Принят",
    "rejected": "Отказ",
    "offer": "Оффер",
}


def _escape_html(s: str) -> str:
    if not s:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _inline_keyboard_approval_first(candidate_id: int) -> list:
    """Клавиатура первого уровня: Подходит / Не подходит (требуется согласование)."""
    return [
        [
            {"text": "✅ Подходит", "callback_data": f"ca_{candidate_id}"},
            {"text": "❌ Не подходит", "callback_data": f"cr_{candidate_id}"},
        ],
    ]


async def send_telegram_to_user(
    bot_token: str,
    chat_id: int,
    text: str,
    reply_markup: dict | None = None,
) -> bool:
    return await safe_send_message(
        bot_token,
        chat_id,
        text,
        parse_mode="HTML",
        reply_markup=reply_markup,
        logger=logger,
    )


def fetch_new_candidates_sync():
    """Синхронный вызов: получить новых кандидатов и заменить L на «Отправленно»."""
    from integrations.client import GoogleSheetsClient
    from integrations.config import GoogleSheetsConfig
    config = GoogleSheetsConfig()
    if not config.is_configured:
        return []
    client = GoogleSheetsClient(config)
    return client.fetch_new_candidates_from_sheet()


async def process_one_candidate(row_index: int, data: dict) -> None:
    from db.db.repository import CandidateRepo, RequestRepo, get_user_by_id
    from db.db.session import async_session_maker

    request_id = data.get("request_id")
    full_name = (data.get("full_name") or "").strip()
    contact = (data.get("contact") or "").strip()
    if not full_name:
        logger.warning("Пропуск строки %s: пустое ФИО", row_index)
        return

    owner_id = None
    owner_tg_id = None
    venue = "—"
    position = "—"
    should_send_approval_now = False
    requires_approval = False

    async with async_session_maker() as db:
        if request_id is not None:
            req_repo = RequestRepo(db)
            req = await req_repo.get(request_id)
            if not req:
                logger.warning("Заявка request_id=%s не найдена, кандидат всё равно будет создан без привязки", request_id)
                request_id = None
        else:
            req = None

        hunting_date = parse_date(data.get("hunting_date"))
        interview_date = parse_date(data.get("interview_date"))
        decision_date = parse_date(data.get("decision_date"))
        requires_approval = interview_date is None
        candidate_repo = CandidateRepo(db)
        status_from_sheet = (data.get("status") or "new").strip() or "new"
        cand = await candidate_repo.get_by_sheet_row_index(row_index)
        if cand is None:
            cand = await candidate_repo.get_by_request_and_full_name(request_id, full_name)

        if cand is None:
            cand = await candidate_repo.create(
                full_name=full_name,
                contact=contact or "—",
                request_id=request_id,
                age=data.get("age"),
                work_experience=data.get("work_experience"),
                resume_url=data.get("resume_url"),
                hunting_date=hunting_date,
                interview_date=interview_date,
                decision_date=decision_date,
                status=status_from_sheet,
                result_notes=data.get("result_notes"),
                sheet_row_index=row_index,
            )
        else:
            cand.full_name = full_name
            cand.contact = contact or "—"
            cand.request_id = request_id
            cand.age = data.get("age")
            cand.work_experience = data.get("work_experience")
            cand.resume_url = data.get("resume_url")
            cand.hunting_date = hunting_date
            cand.interview_date = interview_date
            cand.decision_date = decision_date
            cand.status = status_from_sheet
            cand.result_notes = data.get("result_notes")
            cand.sheet_row_index = row_index
            await db.commit()
            await db.refresh(cand)
        candidate_id = cand.id

        if req and req.owner_id:
            owner_id = req.owner_id
            owner = await get_user_by_id(db, owner_id)
            if owner:
                owner_tg_id = owner.tg_id
            venue = req.venue or "—"
            position = req.position or "—"

        if requires_approval and owner_id:
            has_active = await candidate_repo.has_active_approval_for_owner(owner_id)
            should_send_approval_now = not has_active

    bot_token = (os.environ.get("BOT_TOKEN") or "").strip()
    if bot_token and owner_tg_id:
        status_raw = (data.get("status") or "new").strip() or "new"
        status_label = CANDIDATE_STATUS_LABELS.get(status_raw, status_raw)
        status_norm = status_raw.strip().lower()
        is_interview_notice = status_norm in ("собес", "собеседование", "interview")
        resume_url = (data.get("resume_url") or "").strip()
        resume_line = (
            f'<a href="{_escape_html(resume_url)}">ссылка</a>'
            if resume_url
            else "—"
        )
        candidate_block = (
            f"<b>Кандидат</b>\n"
            f"├─ ФИО: {_escape_html(full_name)}\n"
            f"├─ Контакт: {_escape_html(contact or '—')}\n"
            f"├─ Возраст: {data.get('age') or '—'}\n"
            f"├─ Опыт: {_escape_html((data.get('work_experience') or '—')[:200])}\n"
            f"├─ Резюме: {resume_line}\n"
            f"├─ Дата хантинга: {format_datetime(data.get('hunting_date'))}\n"
            f"├─ Собеседование: {format_datetime(data.get('interview_date'))}\n"
            f"├─ Статус: {status_label}"
        )
        request_block = (
            f"Заявка: #ID_{request_id or '—'}\n"
            f"├─ Площадка: {_escape_html(venue)}\n"
            f"├─ Должность: {_escape_html(position)}"
        )
        if is_interview_notice and interview_date is not None:
            text = (
                f"📅 <b>Обновление по кандидату</b>\n\n"
                f"{request_block}\n\n"
                f"{candidate_block}\n\n"
                f"Собеседование назначено на <code>{format_datetime(interview_date)}</code>.\n\n"
                f"Данные обновлены в системе. Подробности — в разделе «Кандидаты» в боте."
            )
        else:
            text = (
                f"🆕 <b>Новый кандидат по вашей заявке</b>\n\n"
                f"{request_block}\n\n"
                f"{candidate_block}\n\n"
                f"Данные добавлены в систему. Подробности — в разделе «Кандидаты» в боте."
            )
        reply_markup = None
        if requires_approval and should_send_approval_now:
            reply_markup = {"inline_keyboard": _inline_keyboard_approval_first(candidate_id)}
        if requires_approval and not should_send_approval_now:
            logger.info(
                "Кандидат поставлен в очередь согласования: owner_id=%s, candidate_id=%s",
                owner_id,
                candidate_id,
            )
        else:
            ok = await send_telegram_to_user(bot_token, owner_tg_id, text, reply_markup=reply_markup)
            if ok:
                logger.info("Уведомление отправлено автору заявки tg_id=%s, candidate_id=%s", owner_tg_id, candidate_id)
                if requires_approval:
                    async with async_session_maker() as db:
                        cand_repo = CandidateRepo(db)
                        await cand_repo.update(candidate_id, approval_notified_at=datetime.utcnow())
            else:
                logger.warning("Не удалось отправить уведомление автору tg_id=%s", owner_tg_id)
    else:
        if not owner_tg_id and request_id:
            logger.warning("У заявки request_id=%s нет автора (owner_id), уведомление не отправлено", request_id)

    logger.info("Кандидат добавлен: id=%s, строка=%s, ФИО=%s", candidate_id, row_index, full_name)


async def run_once() -> None:
    loop = asyncio.get_event_loop()
    try:
        pairs = await loop.run_in_executor(None, fetch_new_candidates_sync)
    except Exception:
        logger.exception("Ошибка при чтении листа «Кандидаты»")
        return
    for row_index, data in pairs:
        try:
            await process_one_candidate(row_index, data)
        except Exception:
            logger.exception("Ошибка обработки кандидата строка=%s data=%s", row_index, data)


async def main_loop() -> None:
    logger.info("Запуск синхронизации кандидатов из Google Таблицы (интервал %s с)", INTERVAL_SECONDS)
    while True:
        try:
            await run_once()
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("run_once")
        await asyncio.sleep(INTERVAL_SECONDS)


def main() -> None:
    from db.db.session import ensure_database
    ensure_database()
    asyncio.run(main_loop())


if __name__ == "__main__":
    main()
