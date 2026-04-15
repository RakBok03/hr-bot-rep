import asyncio

from db.session import ensure_database
from .bot.bot import create_bot_and_dispatcher, set_webapp_menu_button
from .bot.routers.interview_feedback import run_daily_interview_feedback_scheduler
from .bot.routers.request_exit_reminders import run_daily_request_exit_scheduler


def run() -> None:
    ensure_database()

    async def _start_bot() -> None:
        bot, dp = create_bot_and_dispatcher()
        await set_webapp_menu_button(bot)
        feedback_task = asyncio.create_task(run_daily_interview_feedback_scheduler(bot))
        request_exit_task = asyncio.create_task(run_daily_request_exit_scheduler(bot))
        try:
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
            )
        finally:
            feedback_task.cancel()
            request_exit_task.cancel()
            await asyncio.gather(feedback_task, request_exit_task, return_exceptions=True)

    asyncio.run(_start_bot())


if __name__ == "__main__":
    run()

