from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import MenuButtonWebApp, WebAppInfo

from app.config import get_settings
from app.utils.enums import BotMode


def create_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    settings = get_settings()
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher(storage=MemoryStorage())

    from .routers.commands import router as commands_router
    from .routers.registration import router as registration_router
    from .routers.candidate_approval import router as candidate_approval_router
    from .routers.interview_feedback import router as interview_feedback_router
    dp.include_router(commands_router)
    dp.include_router(registration_router)
    dp.include_router(candidate_approval_router)
    dp.include_router(interview_feedback_router)

    _ = BotMode

    return bot, dp


async def set_webapp_menu_button(bot: Bot) -> None:
    settings = get_settings()
    url = (settings.webapp_url or "").rstrip("/")
    if not url:
        return
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Заявки", web_app=WebAppInfo(url=url)),
        )
    except Exception:
        pass

