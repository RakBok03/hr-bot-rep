"""Настройки подключения к Google Таблицам (из переменных окружения)."""
import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ROOT_ENV = _PROJECT_ROOT / ".env"


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        if _ROOT_ENV.exists():
            load_dotenv(_ROOT_ENV)
    except ImportError:
        pass


class GoogleSheetsConfig:
    """Конфиг для Google Sheets: путь к ключу, ID таблицы, имена листов."""

    def __init__(
        self,
        *,
        credentials_path: str | None = None,
        spreadsheet_id: str | None = None,
        sheet_requests: str = "Заявки",
        sheet_candidates: str = "Кандидаты",
    ) -> None:
        _load_dotenv()
        root = _PROJECT_ROOT
        self.credentials_path = (
            credentials_path
            or os.environ.get("GOOGLE_CREDENTIALS_PATH")
            or os.environ.get("GOOGLE_SHEETS_CREDENTIALS_PATH")
            or ""
        ).strip()
        if self.credentials_path and not Path(self.credentials_path).is_absolute():
            self.credentials_path = str(root / self.credentials_path)
        self.spreadsheet_id = (
            spreadsheet_id or os.environ.get("GOOGLE_SPREADSHEET_ID") or ""
        ).strip()
        self.sheet_requests = sheet_requests or "Заявки"
        self.sheet_candidates = sheet_candidates or "Кандидаты"

    @property
    def is_configured(self) -> bool:
        return bool(self.credentials_path and self.spreadsheet_id)
