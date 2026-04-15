from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import get_settings
from app.utils.telegram import safe_send_message
from db.repository import CandidateRepo, RequestRepo, get_user_by_id
from db.session import async_session_maker
from integrations.client import GoogleSheetsClient
from integrations.config import GoogleSheetsConfig
from utils.dates import format_datetime

logger = logging.getLogger(__name__)

router = Router(name="interview_feedback")


class InterviewFeedbackStates(StatesGroup):
    waiting_reject_reason = State()
    waiting_reschedule_datetime = State()


def _esc(s: str) -> str:
    if not s:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _kb_first(candidate_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принят", callback_data=f"ifa_{candidate_id}"),
            InlineKeyboardButton(text="❌ Отказано", callback_data=f"ifrm_{candidate_id}"),
        ],
        [InlineKeyboardButton(text="✍🏻 Перенесено", callback_data=f"ifsm_{candidate_id}")],
    ])


def _kb_reject(candidate_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍🏻 Указать причину", callback_data=f"ifrr_{candidate_id}")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data=f"ifrb_{candidate_id}")],
    ])


def _kb_reschedule(candidate_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍🏻 Указать дату", callback_data=f"ifsd_{candidate_id}")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data=f"ifsb_{candidate_id}")],
    ])


async def _send_hr_message(bot, text: str) -> bool:
    settings = get_settings()
    hr_chat_id = (settings.hr_chat_id or "").strip()
    if not hr_chat_id:
        return False
    return await safe_send_message(bot, hr_chat_id, text, parse_mode="HTML")


def _reminder_target_day() -> datetime.date:
    return datetime.now().date() - timedelta(days=1)


def _parse_dt(text: str) -> datetime | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%d.%m.%Y %H:%M")
    except ValueError:
        return None


def _build_reminder_text(req_id, venue, position, cand, interview_str: str) -> str:
    resume_url = (cand.resume_url or "").strip()
    resume_line = f'<a href="{_esc(resume_url)}">ссылка</a>' if resume_url else "—"
    return (
        "📅 <b>Обратная связь по собеседованию</b>\n\n"
        f"Заявка: #ID_{req_id or '—'}\n"
        f"├─ Площадка: {_esc(venue)}\n"
        f"├─ Должность: {_esc(position)}\n\n"
        f"<b>Кандидат</b>\n"
        f"├─ ФИО: {_esc(cand.full_name or '—')}\n"
        f"├─ Контакт: {_esc(cand.contact or '—')}\n"
        f"├─ Резюме: {resume_line}\n"
        f"├─ Собеседование: {interview_str}\n\n"
        "Вчера по информации в базе было собеседование. Дайте, пожалуйста, обратную связь."
    )


async def _send_next_pending_interview_feedback(bot, owner_id: int) -> None:
    target_day = _reminder_target_day()
    await _send_next_pending_interview_feedback_for_day(bot, owner_id, target_day)


async def _send_next_pending_interview_feedback_for_day(
    bot, owner_id: int, target_day, run_date=None
) -> bool:
    async with async_session_maker() as db:
        cand_repo = CandidateRepo(db)
        cand = await cand_repo.get_next_pending_interview_feedback_for_owner(
            owner_id, target_day, run_date=run_date
        )
        if not cand:
            return False
        owner = await get_user_by_id(db, owner_id)
        if not owner or not owner.tg_id:
            return False
        req = await RequestRepo(db).get(cand.request_id) if cand.request_id else None
        text = _build_reminder_text(
            getattr(req, "id", None),
            (req.venue or "—") if req else "—",
            (req.position or "—") if req else "—",
            cand,
            format_datetime(cand.interview_date),
        )
        ok = await safe_send_message(
            bot,
            owner.tg_id,
            text,
            parse_mode="HTML",
            reply_markup=_kb_first(cand.id),
        )
        if not ok:
            return False
        await cand_repo.update(cand.id, interview_feedback_notified_at=datetime.utcnow())
        return True


async def _run_interview_feedback_once(bot, target_day, run_date=None) -> tuple[int, int]:
    run_date = run_date or datetime.now().date()
    owners_total = 0
    sent_total = 0
    async with async_session_maker() as db:
        cand_repo = CandidateRepo(db)
        owner_ids = await cand_repo.list_owner_ids_with_pending_interview_feedback(
            target_day, run_date=run_date
        )
        owners_total = len(owner_ids)
        for owner_id in owner_ids:
            has_active = await cand_repo.has_active_interview_feedback_for_owner(owner_id)
            if has_active:
                continue
            sent = await _send_next_pending_interview_feedback_for_day(
                bot, owner_id, target_day, run_date=run_date
            )
            if sent:
                sent_total += 1
    return owners_total, sent_total


async def _build_pending_preview(target_day, run_date=None) -> str:
    run_date = run_date or datetime.now().date()
    lines: list[str] = []
    async with async_session_maker() as db:
        cand_repo = CandidateRepo(db)
        owner_ids = await cand_repo.list_owner_ids_with_pending_interview_feedback(
            target_day, run_date=run_date
        )
        for owner_id in owner_ids:
            cand = await cand_repo.get_next_pending_interview_feedback_for_owner(
                owner_id, target_day, run_date=run_date
            )
            if not cand:
                continue
            req = await RequestRepo(db).get(cand.request_id) if cand.request_id else None
            lines.append(
                f"• owner_id={owner_id}, candidate_id={cand.id}, "
                f"#{getattr(req, 'id', '—')} {_esc(cand.full_name or '—')} "
                f"({format_datetime(cand.interview_date)})"
            )
    if not lines:
        return "Кандидаты не найдены."
    return "\n".join(lines[:20])


async def run_daily_interview_feedback_scheduler(bot) -> None:
    while True:
        now = datetime.now()
        run_at = datetime.combine(now.date(), time(hour=11, minute=0))
        if now >= run_at:
            run_at = run_at + timedelta(days=1)
        await asyncio.sleep(max(1, int((run_at - now).total_seconds())))
        try:
            target_day = _reminder_target_day()
            run_date = datetime.now().date()
            await _run_interview_feedback_once(bot, target_day, run_date=run_date)
        except Exception:
            logger.exception("run_daily_interview_feedback_scheduler")


@router.callback_query(F.data.startswith("ifrm_"))
async def cb_reject_menu(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        return
    cid = int(callback.data.split("_", 1)[1])
    await callback.message.edit_reply_markup(reply_markup=_kb_reject(cid))
    await callback.answer()


@router.callback_query(F.data.startswith("ifsm_"))
async def cb_reschedule_menu(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        return
    cid = int(callback.data.split("_", 1)[1])
    await callback.message.edit_reply_markup(reply_markup=_kb_reschedule(cid))
    await callback.answer()


@router.callback_query(F.data.startswith("ifrb_"))
@router.callback_query(F.data.startswith("ifsb_"))
async def cb_back_first(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        return
    cid = int(callback.data.split("_", 1)[1].split("_")[-1])
    await callback.message.edit_reply_markup(reply_markup=_kb_first(cid))
    await callback.answer()


@router.callback_query(F.data.startswith("ifa_"))
async def cb_accept(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        return
    cid = int(callback.data.split("_", 1)[1])
    async with async_session_maker() as db:
        cand_repo = CandidateRepo(db)
        cand = await cand_repo.get(cid)
        if not cand:
            await callback.answer("Кандидат не найден")
            return
        req = await RequestRepo(db).get(cand.request_id) if cand.request_id else None
        owner_id = getattr(req, "owner_id", None) if req else None
        now = datetime.utcnow()
        await cand_repo.update(
            cid,
            status="hired",
            decision_date=now,
            interview_feedback_decided_at=now,
        )
        text_hr = (
            f"✅ <b>Кандидат принят</b>\n\n"
            f"#Результат #ID_{getattr(req, 'id', '')} | {_esc((req.venue or '—') if req else '—')} · {_esc((req.position or '—') if req else '—')}\n"
            f"├─ Кандидат: {_esc(cand.full_name or '—')}\n"
            f"├─ Дата решения: {format_datetime(now)}"
        )
        sheet_row_index = getattr(cand, "sheet_row_index", None)
        request_id = getattr(req, "id", None) if req else None
        full_name = cand.full_name or ""
    await _send_hr_message(callback.bot, text_hr)
    try:
        config = GoogleSheetsConfig()
        if config.is_configured:
            client = GoogleSheetsClient(config)
            await asyncio.to_thread(
                client.update_candidate_decision,
                cid,
                format_datetime(now),
                "Принят",
                None,
                sheet_row_index,
                request_id,
                full_name,
            )
    except Exception:
        logger.exception("scheduler feedback: update hired candidate_id=%s", cid)
    await callback.message.edit_reply_markup(reply_markup=None)
    await safe_send_message(callback.bot, callback.message.chat.id, "✅ Информация обновлена, спасибо.")
    await callback.answer()
    if owner_id:
        await _send_next_pending_interview_feedback(callback.bot, owner_id)


@router.callback_query(F.data.startswith("ifrr_"))
async def cb_reject_reason_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return
    cid = int(callback.data.split("_", 1)[1])
    await state.update_data(interview_feedback_candidate_id=cid)
    await state.set_state(InterviewFeedbackStates.waiting_reject_reason)
    await callback.message.edit_reply_markup(reply_markup=None)
    await safe_send_message(callback.bot, callback.message.chat.id, "Напишите причину отказа кандидату.")
    await callback.answer()


@router.message(InterviewFeedbackStates.waiting_reject_reason)
async def msg_reject_reason(message: Message, state: FSMContext) -> None:
    reason = (message.text or "").strip()
    if not reason:
        await safe_send_message(message.bot, message.chat.id, "Введите причину отказа текстом.")
        return
    data = await state.get_data()
    cid = data.get("interview_feedback_candidate_id")
    if cid is None:
        await state.clear()
        return
    async with async_session_maker() as db:
        cand_repo = CandidateRepo(db)
        cand = await cand_repo.get(cid)
        if not cand:
            await state.clear()
            return
        req = await RequestRepo(db).get(cand.request_id) if cand.request_id else None
        owner_id = getattr(req, "owner_id", None) if req else None
        now = datetime.utcnow()
        await cand_repo.update(
            cid,
            status="rejected",
            result_notes=reason,
            decision_date=now,
            interview_feedback_decided_at=now,
        )
        text_hr = (
            f"❌ <b>Кандидат — отказ</b>\n\n"
            f"#Результат #ID_{getattr(req, 'id', '')} | {_esc((req.venue or '—') if req else '—')} · {_esc((req.position or '—') if req else '—')}\n"
            f"├─ Кандидат: {_esc(cand.full_name or '—')}\n"
            f"├─ Дата решения: {format_datetime(now)}\n\n"
            f"Причина:\n<blockquote>{_esc(reason)}</blockquote>"
        )
        sheet_row_index = getattr(cand, "sheet_row_index", None)
        request_id = getattr(req, "id", None) if req else None
        full_name = cand.full_name or ""
    await _send_hr_message(message.bot, text_hr)
    try:
        config = GoogleSheetsConfig()
        if config.is_configured:
            client = GoogleSheetsClient(config)
            await asyncio.to_thread(
                client.update_candidate_decision,
                cid,
                format_datetime(now),
                "Отказ",
                reason,
                sheet_row_index,
                request_id,
                full_name,
            )
    except Exception:
        logger.exception("scheduler feedback: update rejected candidate_id=%s", cid)
    await state.clear()
    await safe_send_message(message.bot, message.chat.id, "✅ Информация обновлена, спасибо.")
    if owner_id:
        await _send_next_pending_interview_feedback(message.bot, owner_id)


@router.callback_query(F.data.startswith("ifsd_"))
async def cb_reschedule_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return
    cid = int(callback.data.split("_", 1)[1])
    await state.update_data(interview_feedback_candidate_id=cid)
    await state.set_state(InterviewFeedbackStates.waiting_reschedule_datetime)
    await callback.message.edit_reply_markup(reply_markup=None)
    await safe_send_message(
        callback.bot,
        callback.message.chat.id,
        "Отправьте новую дату/время в формате <code>01.01.2026 12:00</code>",
    )
    await callback.answer()


@router.message(InterviewFeedbackStates.waiting_reschedule_datetime)
async def msg_reschedule_datetime(message: Message, state: FSMContext) -> None:
    dt = _parse_dt(message.text or "")
    if dt is None:
        await safe_send_message(
            message.bot,
            message.chat.id,
            "Неверный формат. Отправьте дату/время в формате <code>01.01.2026 12:00</code>",
        )
        return
    data = await state.get_data()
    cid = data.get("interview_feedback_candidate_id")
    if cid is None:
        await state.clear()
        return
    async with async_session_maker() as db:
        cand_repo = CandidateRepo(db)
        cand = await cand_repo.get(cid)
        if not cand:
            await state.clear()
            return
        req = await RequestRepo(db).get(cand.request_id) if cand.request_id else None
        owner_id = getattr(req, "owner_id", None) if req else None
        now = datetime.utcnow()
        await cand_repo.update(
            cid,
            status="interview",
            interview_date=dt,
            decision_date=now,
            interview_feedback_decided_at=now,
        )
        text_hr = (
            f"✍🏻 <b>Перенос собеседования</b>\n\n"
            f"#Заявка #ID_{getattr(req, 'id', '')} | {_esc((req.venue or '—') if req else '—')} · {_esc((req.position or '—') if req else '—')}\n"
            f"├─ Кандидат: {_esc(cand.full_name or '—')}\n"
            f"├─ Новая дата собеседования: {format_datetime(dt)}"
        )
        sheet_row_index = getattr(cand, "sheet_row_index", None)
        request_id = getattr(req, "id", None) if req else None
        full_name = cand.full_name or ""
    await _send_hr_message(message.bot, text_hr)
    try:
        config = GoogleSheetsConfig()
        if config.is_configured:
            client = GoogleSheetsClient(config)
            await asyncio.to_thread(
                client.update_candidate_decision,
                cid,
                format_datetime(now),
                "Собес",
                None,
                sheet_row_index,
                request_id,
                full_name,
            )
            await asyncio.to_thread(
                client.update_candidate_interview,
                cid,
                format_datetime(dt),
                sheet_row_index,
                request_id,
                full_name,
            )
    except Exception:
        logger.exception("scheduler feedback: update reschedule candidate_id=%s", cid)
    await state.clear()
    await safe_send_message(message.bot, message.chat.id, "✅ Информация обновлена, спасибо.")
    if owner_id:
        await _send_next_pending_interview_feedback(message.bot, owner_id)
