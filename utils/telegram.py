from __future__ import annotations

import asyncio
import logging

import httpx


def _is_permanent_error(error_code: int, description: str) -> bool:
    if error_code in (403,):
        return True
    if error_code != 400:
        return False
    d = (description or "").lower()
    permanent_patterns = (
        "chat not found",
        "user not found",
        "bot was blocked",
        "bot is blocked",
        "forbidden",
        "have no rights",
        "not enough rights",
        "chat_id is empty",
        "peer_id_invalid",
    )
    return any(p in d for p in permanent_patterns)


async def safe_send_message(
    bot_token: str,
    chat_id: int | str,
    text: str,
    *,
    parse_mode: str = "HTML",
    reply_markup: dict | None = None,
    max_attempts: int = 5,
    base_delay_seconds: float = 1.0,
    timeout_seconds: float = 10.0,
    logger: logging.Logger | None = None,
) -> bool:
    """Безопасная отправка сообщения через Telegram Bot API с ретраями."""
    _logger = logger or logging.getLogger(__name__)
    token = (bot_token or "").strip()
    if not token:
        _logger.warning("safe_send_message: empty bot token")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = reply_markup

    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=timeout_seconds)
            data = {}
            try:
                data = response.json()
            except Exception:
                data = {}

            if 200 <= response.status_code < 300 and data.get("ok", True):
                return True

            error_code = int(data.get("error_code") or response.status_code or 0)
            description = str(data.get("description") or response.text or "").strip()
            retry_after = (
                data.get("parameters", {}).get("retry_after")
                if isinstance(data.get("parameters"), dict)
                else None
            )

            if error_code == 429:
                if attempt >= max_attempts:
                    _logger.warning(
                        "safe_send_message: flood exhausted chat_id=%s status=%s desc=%s",
                        chat_id,
                        error_code,
                        description[:300],
                    )
                    return False
                delay = float(retry_after or max(base_delay_seconds, 1.0))
                _logger.warning(
                    "safe_send_message: flood retry chat_id=%s attempt=%s/%s sleep=%ss",
                    chat_id,
                    attempt,
                    max_attempts,
                    delay,
                )
                await asyncio.sleep(delay)
                continue

            if _is_permanent_error(error_code, description):
                _logger.warning(
                    "safe_send_message: permanent chat_id=%s status=%s desc=%s",
                    chat_id,
                    error_code,
                    description[:300],
                )
                return False

            if error_code >= 500:
                if attempt >= max_attempts:
                    _logger.warning(
                        "safe_send_message: server exhausted chat_id=%s status=%s desc=%s",
                        chat_id,
                        error_code,
                        description[:300],
                    )
                    return False
                delay = base_delay_seconds * (2 ** (attempt - 1))
                _logger.warning(
                    "safe_send_message: server retry chat_id=%s attempt=%s/%s sleep=%ss",
                    chat_id,
                    attempt,
                    max_attempts,
                    delay,
                )
                await asyncio.sleep(delay)
                continue

            if attempt >= max_attempts:
                _logger.warning(
                    "safe_send_message: api exhausted chat_id=%s status=%s desc=%s",
                    chat_id,
                    error_code,
                    description[:300],
                )
                return False

            delay = base_delay_seconds * attempt
            _logger.warning(
                "safe_send_message: api retry chat_id=%s attempt=%s/%s sleep=%ss status=%s",
                chat_id,
                attempt,
                max_attempts,
                delay,
                error_code,
            )
            await asyncio.sleep(delay)
        except httpx.RequestError as err:
            if attempt >= max_attempts:
                _logger.warning(
                    "safe_send_message: network exhausted chat_id=%s err=%s",
                    chat_id,
                    err,
                )
                return False
            delay = base_delay_seconds * (2 ** (attempt - 1))
            _logger.warning(
                "safe_send_message: network retry chat_id=%s attempt=%s/%s sleep=%ss",
                chat_id,
                attempt,
                max_attempts,
                delay,
            )
            await asyncio.sleep(delay)
        except Exception:
            if attempt >= max_attempts:
                _logger.exception("safe_send_message: unexpected exhausted chat_id=%s", chat_id)
                return False
            delay = base_delay_seconds * attempt
            _logger.exception(
                "safe_send_message: unexpected retry chat_id=%s attempt=%s/%s sleep=%ss",
                chat_id,
                attempt,
                max_attempts,
                delay,
            )
            await asyncio.sleep(delay)
    return False
