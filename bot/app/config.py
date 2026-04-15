from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings

_ROOT_ENV = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    bot_token: str
    webapp_host: str = "0.0.0.0"
    webapp_port: int = 8000
    webapp_url: str = Field("", alias="WEBAPP_URL")
    database_url: str = "sqlite:///./data/bot.db"
    hr_chat_id: str = Field("", alias="HR_CHAT_ID")

    @property
    def async_database_url(self) -> str:
        return self.database_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

    env: str = "development"
    allowed_email_domains: str = Field(
        "example.com,test.com",
        alias="ALLOWED_EMAIL_DOMAINS",
        description="Comma-separated email domains",
    )

    @computed_field
    @property
    def allowed_email_domains_list(self) -> list[str]:
        return [x.strip() for x in self.allowed_email_domains.split(",") if x.strip()]

    smtp_enabled: bool = Field(False, alias="SMTP")
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    mail_from: str | None = None

    class Config:
        env_file = str(_ROOT_ENV) if _ROOT_ENV.exists() else ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()

