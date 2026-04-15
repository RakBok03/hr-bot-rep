from datetime import datetime, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.keyboards.inline import registration_button
from app.utils.telegram import safe_send_message
from app.bot.routers.request_exit_reminders import run_request_exit_yesterday
from db.models import User
from db.repository import UserRepo
from db.session import async_session_maker

router = Router(name="commands")


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    async with async_session_maker() as db:
        repo = UserRepo(message.from_user.id, db)
        user = await repo.get_or_create(
            full_name=message.from_user.full_name or message.from_user.first_name,
            username=message.from_user.username,
        )
        is_unknown = user.role == User.Role.UNKNOWN.value

    text = (
        "👋 Привет! Я внутренний HR-бот компании.\n\n"
        "Я помогу оставлять заявки, смотреть статус подбора и работать с кандидатами.\n"
    )
    if is_unknown:
        text += (
            "\n🔐 Сейчас вы не зарегистрированы. "
            "Нажмите кнопку ниже, чтобы пройти регистрацию по корпоративной почте."
        )
        await safe_send_message(
            message.bot,
            message.chat.id,
            text,
            reply_markup=registration_button(),
        )
    else:
        await safe_send_message(message.bot, message.chat.id, text)


@router.message(Command("get_id"))
async def cmd_get_id(message: Message) -> None:
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else None
    text = f"🆔 ID чата: <code>{chat_id}</code>"
    if user_id is not None:
        text += f"\n👤 Ваш user id: <code>{user_id}</code>"
    await safe_send_message(message.bot, message.chat.id, text, parse_mode="HTML")
