from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta, date

from app.utils.telegram import safe_send_message
from db.repository import RequestRepo, get_user_by_id
from db.session import async_session_maker
from utils.dates import format_date, parse_date

logger = logging.getLogger(__name__)

def _build_requests_exit_text(request_rows: list[tuple[object, str]], *, is_yesterday: bool) -> str:
    blocks: list[str] = []
    for req, start_str in request_rows:
        venue = getattr(req, "venue", "") or "—"
        position = getattr(req, "position", "") or "Заявка"
        blocks.append(
            f"#Заявка #ID_{getattr(req, 'id', '—')} | {venue} · {position}\n"
            f"├─ Дата выхода: {start_str}"
        )

    when_line = "была вчера" if is_yesterday else "уже в прошлом"
    return (
        "📅 <b>Напоминание по заявкам</b>\n\n"
        + "\n\n".join(blocks)
        + "\n\n"
        + f"По этим заявкам предполагаемая дата выхода {when_line}.\n"
        + "Пожалуйста, укажите актуальный статус заявки в приложении.\n\n"
        + "<b>Как обновить статус:</b>\n"
        + "<blockquote>"
        + "1. Откройте веб‑приложение HR.\n"
        + "2. Найдите заявку по номеру или по позиции.\n"
        + "3. Обновите статус заявки (например, «Закрыта» или «Отменена»),\n"
        + "   либо измените дату выхода, если она перенеслась."
        + "</blockquote>"
    )


async def run_request_exit_yesterday(bot, run_date: date) -> int:
    target_day = run_date - timedelta(days=1)
    sent_total = 0
    async with async_session_maker() as db:
        req_repo = RequestRepo(db)
        requests = await req_repo.list_active_with_owner()
        by_owner: dict[int, list[tuple[object, str]]] = {}
        for req in requests:
            start_raw = getattr(req, "start_date", None) or ""
            dt = parse_date(start_raw)
            if not dt or dt.date() != target_day:
                continue
            owner_id = getattr(req, "owner_id", None)
            if not owner_id:
                continue
            by_owner.setdefault(int(owner_id), []).append((req, format_date(start_raw)))

        for owner_id, rows in by_owner.items():
            owner = await get_user_by_id(db, owner_id)
            if not owner or not owner.tg_id:
                continue
            text = _build_requests_exit_text(rows, is_yesterday=True)
            ok = await safe_send_message(bot, owner.tg_id, text, parse_mode="HTML")
            if ok:
                sent_total += 1
    return sent_total


async def _run_request_exit_once(bot, run_date: date) -> int:
    sent_total = 0
    async with async_session_maker() as db:
        req_repo = RequestRepo(db)
        requests = await req_repo.list_active_with_owner()
        by_owner: dict[int, list[tuple[object, str]]] = {}
        for req in requests:
            start_raw = getattr(req, "start_date", None) or ""
            dt = parse_date(start_raw)
            if not dt:
                continue
            if dt.date() >= run_date:
                continue
            owner_id = getattr(req, "owner_id", None)
            if not owner_id:
                continue
            by_owner.setdefault(int(owner_id), []).append((req, format_date(start_raw)))

        for owner_id, rows in by_owner.items():
            owner = await get_user_by_id(db, owner_id)
            if not owner or not owner.tg_id:
                continue
            text = _build_requests_exit_text(rows, is_yesterday=False)
            ok = await safe_send_message(bot, owner.tg_id, text, parse_mode="HTML")
            if ok:
                sent_total += 1
    return sent_total


async def run_daily_request_exit_scheduler(bot) -> None:
    while True:
        now = datetime.now()
        run_at = datetime.combine(now.date(), time(hour=11, minute=10))
        if now >= run_at:
            run_at = run_at + timedelta(days=1)
        await asyncio.sleep(max(1, int((run_at - now).total_seconds())))
        try:
            run_date = datetime.now().date()
            await _run_request_exit_once(bot, run_date)
        except Exception:
            logger.exception("run_daily_request_exit_scheduler")




