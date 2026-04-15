import secrets

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from db.repository import UserRepo
from db.session import async_session_maker
from app.mail import send_verification_email
from db.models import User
from app.utils.helpers import comma_separated_to_list
from app.utils.telegram import safe_send_message

router = Router(name="registration")


class RegistrationStates(StatesGroup):
    WAITING_FOR_EMAIL = State()
    WAITING_FOR_CODE = State()
    WAITING_FOR_FULL_NAME = State()


@router.callback_query(F.data == "register")
async def start_registration(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(RegistrationStates.WAITING_FOR_EMAIL)

    await callback.message.edit_text(
        "✉️ Введите вашу корпоративную почту (например, name@example.com):",
        reply_markup=None,
    )
    await callback.answer()


@router.message(RegistrationStates.WAITING_FOR_EMAIL)
async def process_email(message: Message, state: FSMContext) -> None:
    email = (message.text or "").strip()

    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        await safe_send_message(message.bot, message.chat.id, "⚠️ Похоже, это не похоже на email. Попробуйте ещё раз.")
        return

    _, domain = email.rsplit("@", 1)

    settings = get_settings()
    allowed_domains = set(settings.allowed_email_domains_list)
    if not allowed_domains:
        allowed_domains = set(comma_separated_to_list("example.com,test.com"))

    if domain.lower() not in {d.lower() for d in allowed_domains}:
        await safe_send_message(message.bot, message.chat.id, "❌ Регистрация доступна только по корпоративной почте.")
        return

    async with async_session_maker() as db:
        repo = UserRepo(message.from_user.id, db)
        user = await repo.get()
        if user is None:
            user = User(
                tg_id=repo.tg_id,
                full_name=message.from_user.full_name or message.from_user.first_name or "",
                username=message.from_user.username,
            )
            repo.db.add(user)
        existing_email_user = await repo.db.scalar(
            select(User).where(User.email == email, User.id != user.id)
        )
        if existing_email_user is not None:
            await safe_send_message(
                message.bot,
                message.chat.id,
                "❌ Эта почта уже используется другим аккаунтом. Укажите другую корпоративную почту.",
            )
            return
        user.email = email
        try:
            await repo.db.commit()
        except IntegrityError:
            await repo.db.rollback()
            await safe_send_message(
                message.bot,
                message.chat.id,
                "❌ Эта почта уже зарегистрирована. Укажите другую корпоративную почту.",
            )
            return

    if settings.smtp_enabled:
        code = "".join(secrets.choice("0123456789") for _ in range(6))
        await state.update_data(verification_code=code, code_attempts=0)

        if not send_verification_email(email, code):
            await safe_send_message(
                message.bot,
                message.chat.id,
                "❌ Не удалось отправить письмо с кодом. Проверьте настройки почты или попробуйте позже."
            )
            return

        await state.set_state(RegistrationStates.WAITING_FOR_CODE)
        await safe_send_message(
            message.bot,
            message.chat.id,
            "✅ На вашу почту отправлен код подтверждения.\n"
            "Пожалуйста, введите код из письма в этот чат."
        )
    else:
        await state.update_data(verification_code="1111", code_attempts=0)
        await state.set_state(RegistrationStates.WAITING_FOR_CODE)
        await safe_send_message(
            message.bot,
            message.chat.id,
            "✅ Введите код подтверждения (в режиме без SMTP используйте код 1111)."
        )


@router.message(RegistrationStates.WAITING_FOR_CODE)
async def process_code(message: Message, state: FSMContext) -> None:
    entered = (message.text or "").strip()
    data = await state.get_data()
    expected_code = data.get("verification_code")
    attempts = int(data.get("code_attempts", 0))

    if not expected_code:
        await state.clear()
        await safe_send_message(message.bot, message.chat.id, "❌ Сессия истекла. Начните регистрацию заново (/start).")
        return

    if entered != expected_code:
        attempts += 1
        await state.update_data(code_attempts=attempts)
        if attempts >= 3:
            await state.clear()
            await safe_send_message(
                message.bot,
                message.chat.id,
                "❌ Код введён неверно 3 раза.\n"
                "Пожалуйста, заново начните регистрацию и запросите новый код."
            )
        else:
            await safe_send_message(
                message.bot,
                message.chat.id,
                f"❌ Неверный код. Попробуйте ещё раз. Осталось попыток: {3 - attempts}."
            )
        return

    async with async_session_maker() as db:
        repo = UserRepo(message.from_user.id, db)
        user = await repo.get()
        if user is not None:
            user.role = User.Role.EMPLOYEE.value
            await repo.db.commit()

    await state.set_state(RegistrationStates.WAITING_FOR_FULL_NAME)
    await safe_send_message(
        message.bot,
        message.chat.id,
        "✅ Почта подтверждена. Укажите ФИО полностью, например:\n"
        "<code>Иванов Иван Иванович</code>"
    )


@router.message(RegistrationStates.WAITING_FOR_FULL_NAME)
async def process_full_name(message: Message, state: FSMContext) -> None:
    full_name = (message.text or "").strip()

    if len(full_name) < 3 or full_name.count(" ") < 1:
        await safe_send_message(
            message.bot,
            message.chat.id,
            "⚠️ Введите ФИО полностью (минимум фамилия и имя), например: <code>Иванов Иван Иванович</code>",
        )
        return

    async with async_session_maker() as db:
        repo = UserRepo(message.from_user.id, db)
        user = await repo.get()
        if user is not None:
            user.full_name = full_name
            await repo.db.commit()

    await state.clear()
    await safe_send_message(message.bot, message.chat.id, "✅ Регистрация завершена. Ваш аккаунт активирован.")
