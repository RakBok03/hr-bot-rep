from __future__ import annotations

import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import get_settings
from app.utils.telegram import safe_send_message
from db.repository import CandidateRepo, RequestRepo, get_user_by_id
from db.session import async_session_maker
from utils.dates import format_datetime

logger = logging.getLogger(__name__)

router = Router(name="candidate_approval")

CANDIDATE_STATUS_LABELS = {
    "new": "Новая",
    "interview": "Собес",
    "hired": "Принят",
    "rejected": "Отказ",
    "offer": "Оффер",
}


class CandidateApprovalStates(StatesGroup):
    waiting_reject_reason = State()
    waiting_self_datetime = State()


def _html_esc(s: str) -> str:
    if not s:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _keyboard_approve_first(candidate_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подходит", callback_data=f"ca_{candidate_id}"),
            InlineKeyboardButton(text="❌ Не подходит", callback_data=f"cr_{candidate_id}"),
        ],
    ])


def _keyboard_approve_second(candidate_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ HR согласует дату/время", callback_data=f"ha_{candidate_id}")],
        [InlineKeyboardButton(text="✍🏻 Указать дату/время самостоятельно", callback_data=f"sd_{candidate_id}")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data=f"ba_ap_{candidate_id}")],
    ])


def _keyboard_reject_second(candidate_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍🏻 Указать причину", callback_data=f"rr_{candidate_id}")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data=f"ba_rj_{candidate_id}")],
    ])


async def _send_hr_message(bot, text: str) -> bool:
    settings = get_settings()
    hr_chat_id = (settings.hr_chat_id or "").strip()
    if not hr_chat_id or not settings.bot_token:
        return False
    return await safe_send_message(
        bot,
        hr_chat_id,
        text,
        parse_mode="HTML",
    )


async def _resend_with_new_keyboard(
    message: Message,
    reply_markup: InlineKeyboardMarkup | None,
) -> None:
    text = (getattr(message, "html_text", None) or message.text or "").strip()
    if not text:
        await message.edit_reply_markup(reply_markup=reply_markup)
        return
    try:
        await message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    except Exception:
        logger.exception("edit_with_new_keyboard")
        await message.edit_reply_markup(reply_markup=reply_markup)


async def _send_next_pending_candidate(bot, owner_id: int | None) -> None:
    if not owner_id:
        return
    async with async_session_maker() as db:
        cand_repo = CandidateRepo(db)
        cand = await cand_repo.get_next_pending_approval_for_owner(owner_id)
        if not cand:
            return
        owner = await get_user_by_id(db, owner_id)
        if not owner or not owner.tg_id:
            return
        req = await RequestRepo(db).get(cand.request_id) if cand.request_id else None
        request_id = getattr(req, "id", None)
        venue = (req.venue or "—") if req else "—"
        position = (req.position or "—") if req else "—"
        status_raw = (cand.status or "new").strip() or "new"
        status_label = CANDIDATE_STATUS_LABELS.get(status_raw, status_raw)
        text = (
            f"🆕 <b>Новый кандидат по вашей заявке</b>\n\n"
            f"Заявка: #{request_id or '—'}\n"
            f"Площадка: {_html_esc(venue)}\n"
            f"Должность: {_html_esc(position)}\n\n"
            f"<b>Кандидат</b>\n"
            f"ФИО: {_html_esc(cand.full_name or '—')}\n"
            f"Контакт: {_html_esc(cand.contact or '—')}\n"
            f"Возраст: {cand.age or '—'}\n"
            f"Опыт: {_html_esc((cand.work_experience or '—')[:200])}\n"
            f"Резюме: {_html_esc((cand.resume_url or '—')[:100])}\n"
            f"Дата хантинга: {format_datetime(cand.hunting_date)}\n"
            f"Собеседование: {format_datetime(cand.interview_date)}\n"
            f"Статус: {status_label}\n\n"
            f"Данные добавлены в систему. Подробности — в разделе «Кандидаты» в боте."
        )
    ok = await safe_send_message(
        bot,
        owner.tg_id,
        text,
        parse_mode="HTML",
        reply_markup=_keyboard_approve_first(cand.id),
    )
    if not ok:
        logger.warning("send_next_pending_candidate failed owner_id=%s candidate_id=%s", owner_id, cand.id)
        return
    async with async_session_maker() as db:
        cand_repo = CandidateRepo(db)
        await cand_repo.update(cand.id, approval_notified_at=datetime.utcnow())


def _parse_interview_datetime(text: str) -> datetime | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%d.%m.%Y %H:%M")
    except ValueError:
        return None


@router.callback_query(F.data.startswith("ca_"))
async def cb_approve(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        return
    try:
        cid = int(callback.data.split("_", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка")
        return
    await _resend_with_new_keyboard(callback.message, _keyboard_approve_second(cid))
    await callback.answer()


@router.callback_query(F.data.startswith("cr_"))
async def cb_reject(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        return
    try:
        cid = int(callback.data.split("_", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка")
        return
    await _resend_with_new_keyboard(callback.message, _keyboard_reject_second(cid))
    await callback.answer()


@router.callback_query(F.data.startswith("ba_ap_"))
async def cb_back_approve(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        return
    try:
        cid = int(callback.data.split("_", 2)[2])
    except (ValueError, IndexError):
        await callback.answer("Ошибка")
        return
    await _resend_with_new_keyboard(callback.message, _keyboard_approve_first(cid))
    await callback.answer()


@router.callback_query(F.data.startswith("ba_rj_"))
async def cb_back_reject(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        return
    try:
        cid = int(callback.data.split("_", 2)[2])
    except (ValueError, IndexError):
        await callback.answer("Ошибка")
        return
    await _resend_with_new_keyboard(callback.message, _keyboard_approve_first(cid))
    await callback.answer()


@router.callback_query(F.data.startswith("ha_"))
async def cb_hr_agrees(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        return
    try:
        cid = int(callback.data.split("_", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка")
        return
    async with async_session_maker() as db:
        candidate_repo = CandidateRepo(db)
        cand = await candidate_repo.get(cid)
        if not cand:
            await callback.answer("Кандидат не найден")
            return
        req = None
        if cand.request_id:
            req = await RequestRepo(db).get(cand.request_id)
        request_id = getattr(req, "id", None) if req else None
        owner_id = getattr(req, "owner_id", None) if req else None
        venue = (req.venue or "—") if req else "—"
        position = (req.position or "—") if req else "—"
        full_name = cand.full_name or "—"
        resume_url = (cand.resume_url or "").strip()
        resume_line = f'<a href="{_html_esc(resume_url)}">ссылка</a>' if resume_url else "—"
        req_id = getattr(req, "id", "")
        sheet_row_index = getattr(cand, "sheet_row_index", None)
        now = datetime.utcnow()
        text_hr = (
            f"✍🏻 <b>Согласование даты/времени с кандидатом</b>\n\n"
            f"#Заявка #ID_{req_id} | {_html_esc(venue)} · {_html_esc(position)}\n"
            f"├─ Кандидат: {_html_esc(full_name)}\n"
            f"├─ Резюме: {resume_line}\n\n"
            f"Заказчик выбрал: HR согласует дату и время собеседования."
        )
        await candidate_repo.update(cid, approval_decided_at=now)
    await _send_hr_message(callback.bot, text_hr)
    try:
        from integrations.client import GoogleSheetsClient
        from integrations.config import GoogleSheetsConfig

        config = GoogleSheetsConfig()
        if config.is_configured:
            client = GoogleSheetsClient(config)
            import asyncio

            await asyncio.to_thread(
                client.update_candidate_decision,
                cid,
                format_datetime(now),
                "Назначить собес",
                None,
                sheet_row_index,
                request_id,
                full_name,
            )
            await asyncio.to_thread(
                client.update_candidate_send_flag,
                cid,
                "Ожидание",
                sheet_row_index,
                request_id,
                full_name,
            )
    except Exception:
        logger.exception("Google Sheets set status 'Назначить собес' candidate_id=%s", cid)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    if callback.message:
        await safe_send_message(
            callback.bot,
            callback.message.chat.id,
            "✅ Информация отправлена в HR отдел. Дата и время собеседования будут отправлены Вам после согласования с кандидатом.",
        )
    await _send_next_pending_candidate(callback.bot, owner_id)


@router.callback_query(F.data.startswith("sd_"))
async def cb_self_date(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return
    try:
        cid = int(callback.data.split("_", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка")
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    await safe_send_message(
        callback.bot,
        callback.message.chat.id,
        "Отправьте дату и время в формате <code>01.01.2026 12:00</code>",
    )
    await state.update_data(candidate_approval_candidate_id=cid)
    await state.set_state(CandidateApprovalStates.waiting_self_datetime)
    await callback.answer()


@router.message(CandidateApprovalStates.waiting_self_datetime)
async def msg_self_datetime_any(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip():
        await safe_send_message(
            message.bot,
            message.chat.id,
            "Отправьте дату и время в формате <code>01.01.2026 12:00</code>",
        )
        return

    interview_dt = _parse_interview_datetime(message.text)
    if interview_dt is None:
        await safe_send_message(
            message.bot,
            message.chat.id,
            "Неверный формат. Отправьте дату и время в виде <code>01.01.2026 12:00</code>",
        )
        return

    data = await state.get_data()
    cid = data.get("candidate_approval_candidate_id")
    if cid is None:
        await state.clear()
        return

    owner_id = None
    sheet_row_index = None
    async with async_session_maker() as db:
        candidate_repo = CandidateRepo(db)
        cand = await candidate_repo.get(cid)
        if not cand:
            await safe_send_message(message.bot, message.chat.id, "Кандидат не найден.")
            await state.clear()
            return
        req = await RequestRepo(db).get(cand.request_id) if cand.request_id else None
        request_id = getattr(req, "id", None) if req else None
        owner_id = getattr(req, "owner_id", None) if req else None
        venue = (req.venue or "—") if req else "—"
        position = (req.position or "—") if req else "—"
        full_name = cand.full_name or "—"
        resume_url = (cand.resume_url or "").strip()
        resume_line = f'<a href="{_html_esc(resume_url)}">ссылка</a>' if resume_url else "—"
        req_id = getattr(req, "id", "")
        now = datetime.utcnow()
        sheet_row_index = getattr(cand, "sheet_row_index", None)
        await candidate_repo.update(
            cid,
            status="interview",
            interview_date=interview_dt,
            decision_date=now,
            approval_decided_at=now,
        )

    interview_str = format_datetime(interview_dt)
    decision_str = format_datetime(now)
    text_hr = (
        f"✅ <b>Кандидат — собеседование назначено заказчиком</b>\n\n"
        f"#Результат #ID_{req_id} | {_html_esc(venue)} · {_html_esc(position)}\n"
        f"├─ Кандидат: {_html_esc(full_name)}\n"
        f"├─ Дата решения: {decision_str}\n"
        f"├─ Дата собеседования: {interview_str}\n"
        f"├─ Резюме: {resume_line}"
    )
    await _send_hr_message(message.bot, text_hr)
    try:
        from integrations.client import GoogleSheetsClient
        from integrations.config import GoogleSheetsConfig

        config = GoogleSheetsConfig()
        if config.is_configured:
            client = GoogleSheetsClient(config)
            import asyncio

            await asyncio.to_thread(
                client.update_candidate_decision,
                cid,
                decision_str,
                "Собес",
                None,
                sheet_row_index,
                request_id,
                full_name,
            )
            await asyncio.to_thread(
                client.update_candidate_interview,
                cid,
                interview_str,
                sheet_row_index,
                request_id,
                full_name,
            )
    except Exception:
        logger.exception("Google Sheets update interview/decision candidate_id=%s", cid)

    await state.clear()
    await safe_send_message(message.bot, message.chat.id, "✅ Информация отправлена в HR отдел.")
    await _send_next_pending_candidate(message.bot, owner_id)


@router.callback_query(F.data.startswith("rr_"))
async def cb_reject_reason(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return
    try:
        cid = int(callback.data.split("_", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка")
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    await safe_send_message(callback.bot, callback.message.chat.id, "Напишите в чат причину отказа кандидату")
    await state.update_data(candidate_approval_candidate_id=cid)
    await state.set_state(CandidateApprovalStates.waiting_reject_reason)
    await callback.answer()


@router.message(CandidateApprovalStates.waiting_reject_reason)
async def msg_reject_reason_any(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip():
        await safe_send_message(
            message.bot,
            message.chat.id,
            "Пожалуйста, отправьте текстом причину отказа кандидату.",
        )
        return
    await _process_reject_reason(message, state)


async def _process_reject_reason(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    cid = data.get("candidate_approval_candidate_id")
    if cid is None:
        await state.clear()
        return
    reason = (message.text or "").strip()
    if not reason:
        await safe_send_message(message.bot, message.chat.id, "Введите текст причины отказа.")
        return
    sheet_row_index = None
    owner_id = None
    async with async_session_maker() as db:
        candidate_repo = CandidateRepo(db)
        cand = await candidate_repo.get(cid)
        if not cand:
            await safe_send_message(message.bot, message.chat.id, "Кандидат не найден.")
            await state.clear()
            return
        req = None
        if cand.request_id:
            req = await RequestRepo(db).get(cand.request_id)
        request_id = getattr(req, "id", None) if req else None
        owner_id = getattr(req, "owner_id", None) if req else None
        venue = (req.venue or "—") if req else "—"
        position = (req.position or "—") if req else "—"
        full_name = cand.full_name or "—"
        resume_url = (cand.resume_url or "").strip()
        resume_line = f'<a href="{_html_esc(resume_url)}">ссылка</a>' if resume_url else "—"
        req_id = getattr(req, "id", "")
        sheet_row_index = getattr(cand, "sheet_row_index", None)
        now = datetime.utcnow()
        await candidate_repo.update(
            cid,
            status="rejected",
            result_notes=reason,
            decision_date=now,
            approval_decided_at=now,
        )
    decision_str = format_datetime(now)
    text_hr = (
        f"❌ <b>Кандидат — отказ</b> (причина от заказчика)\n\n"
        f"#Результат #ID_{req_id} | {_html_esc(venue)} · {_html_esc(position)}\n"
        f"├─ Кандидат: {_html_esc(full_name)}\n"
        f"├─ Дата решения: {decision_str}\n"
        f"├─ Резюме: {resume_line}\n\n"
        f"Причина:\n<blockquote>{_html_esc(reason)}</blockquote>"
    )
    await _send_hr_message(message.bot, text_hr)
    try:
        from integrations.client import GoogleSheetsClient
        from integrations.config import GoogleSheetsConfig
        config = GoogleSheetsConfig()
        if config.is_configured:
            client = GoogleSheetsClient(config)
            import asyncio
            await asyncio.to_thread(
                client.update_candidate_decision,
                cid,
                decision_str,
                "Отказ",
                reason,
                sheet_row_index,
                request_id,
                full_name,
            )
    except Exception:
        logger.exception("Google Sheets update_candidate_decision candidate_id=%s", cid)
    await state.clear()
    await safe_send_message(message.bot, message.chat.id, "✅ Информация отправлена в HR отдел.")
    await _send_next_pending_candidate(message.bot, owner_id)
