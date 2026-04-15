from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings

_ROOT_ENV = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    bot_token: str = ""
    webapp_url: str = Field("", alias="WEBAPP_URL")
    hr_chat_id: str = Field("", alias="HR_CHAT_ID")
    admin_tg_ids: str = Field("", alias="ADMIN_TG_IDS")

    @computed_field
    @property
    def admin_tg_ids_list(self) -> list[int]:
        ids: list[int] = []
        for part in (self.admin_tg_ids or "").split(","):
            s = part.strip()
            if not s:
                continue
            try:
                ids.append(int(s))
            except ValueError:
                continue
        return ids

    class Config:
        env_file = str(_ROOT_ENV) if _ROOT_ENV.exists() else ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
