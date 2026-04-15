import hashlib
import hmac
import json
from urllib.parse import parse_qsl


def validate_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    if not init_data or not bot_token:
        return None
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        hash_value = parsed.pop("hash", None)
        if not hash_value:
            return None
        data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(
            b"WebAppData", bot_token.encode(), hashlib.sha256
        ).digest()
        computed = hmac.new(
            secret_key, data_check.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(computed, hash_value):
            return None
        user_str = parsed.get("user")
        if not user_str:
            return {"auth_date": parsed.get("auth_date"), "user": None}
        return {"user": json.loads(user_str), "auth_date": parsed.get("auth_date")}
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
