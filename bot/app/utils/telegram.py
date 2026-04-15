from __future__ import annotations

import asyncio
import logging

from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.types import InlineKeyboardMarkup

logger = logging.getLogger(__name__)


def _is_permanent_bad_request(err: TelegramBadRequest) -> bool:
    text = str(err).lower()
    permanent_patterns = (
        "chat not found",
        "user not found",
        "bot was blocked",
        "bot is blocked",
        "have no rights",
        "not enough rights",
        "chat_id is empty",
        "peer_id_invalid",
    )
    return any(p in text for p in permanent_patterns)


async def safe_send_message(
    bot,
    chat_id: int | str,
    text: str,
    *,
    parse_mode: str = "HTML",
    reply_markup: InlineKeyboardMarkup | None = None,
    max_attempts: int = 5,
    base_delay_seconds: float = 1.0,
) -> bool:
    for attempt in range(1, max_attempts + 1):
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
            return True
        except TelegramRetryAfter as err:
            if attempt >= max_attempts:
                logger.warning(
                    "safe_send_message: retry_after exhausted chat_id=%s retry_after=%s",
                    chat_id,
                    err.retry_after,
                )
                return False
            delay = float(max(err.retry_after, base_delay_seconds))
            logger.warning(
                "safe_send_message: flood control chat_id=%s attempt=%s/%s sleep=%ss",
                chat_id,
                attempt,
                max_attempts,
                delay,
            )
            await asyncio.sleep(delay)
        except TelegramForbiddenError:
            logger.warning("safe_send_message: forbidden chat_id=%s", chat_id)
            return False
        except TelegramBadRequest as err:
            if _is_permanent_bad_request(err):
                logger.warning("safe_send_message: permanent bad request chat_id=%s err=%s", chat_id, err)
                return False
            if attempt >= max_attempts:
                logger.warning("safe_send_message: bad request exhausted chat_id=%s err=%s", chat_id, err)
                return False
            delay = base_delay_seconds * attempt
            logger.warning(
                "safe_send_message: bad request retry chat_id=%s attempt=%s/%s sleep=%ss err=%s",
                chat_id,
                attempt,
                max_attempts,
                delay,
                err,
            )
            await asyncio.sleep(delay)
        except (TelegramNetworkError, TelegramServerError) as err:
            if attempt >= max_attempts:
                logger.warning("safe_send_message: network/server exhausted chat_id=%s err=%s", chat_id, err)
                return False
            delay = base_delay_seconds * (2 ** (attempt - 1))
            logger.warning(
                "safe_send_message: network/server retry chat_id=%s attempt=%s/%s sleep=%ss",
                chat_id,
                attempt,
                max_attempts,
                delay,
            )
            await asyncio.sleep(delay)
        except TelegramAPIError as err:
            if attempt >= max_attempts:
                logger.warning("safe_send_message: api error exhausted chat_id=%s err=%s", chat_id, err)
                return False
            delay = base_delay_seconds * attempt
            logger.warning(
                "safe_send_message: api error retry chat_id=%s attempt=%s/%s sleep=%ss err=%s",
                chat_id,
                attempt,
                max_attempts,
                delay,
                err,
            )
            await asyncio.sleep(delay)
        except Exception:
            if attempt >= max_attempts:
                logger.exception("safe_send_message: unexpected exhausted chat_id=%s", chat_id)
                return False
            delay = base_delay_seconds * attempt
            logger.exception(
                "safe_send_message: unexpected retry chat_id=%s attempt=%s/%s sleep=%ss",
                chat_id,
                attempt,
                max_attempts,
                delay,
            )
            await asyncio.sleep(delay)
    return False
