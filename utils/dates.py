"""Единый формат дат в проекте: dd.mm.yyyy и dd.mm.yyyy HH:MM."""
from __future__ import annotations

from datetime import datetime, timedelta

FMT_DATE = "%d.%m.%Y"
FMT_DATETIME = "%d.%m.%Y %H:%M"


def format_date(s: str | None) -> str:
    """Любая строка даты (YYYY-MM-DD или dd.mm.yyyy) -> dd.mm.yyyy. Пусто -> "—"."""
    if not s or len(s) < 10:
        return (s or "").strip() or "—"
    s = s.strip()[:10]
    if s[2] == "." and s[5] == ".":
        return s
    try:
        y, m, d = s.split("-")
        if len(y) == 4 and len(m) == 2 and len(d) == 2:
            return f"{d}.{m}.{y}"
    except ValueError:
        pass
    return s


def format_datetime(dt) -> str:
    """datetime или строка -> dd.mm.yyyy HH:MM. None -> "—"."""
    if dt is None:
        return "—"
    if hasattr(dt, "strftime"):
        return dt.strftime(FMT_DATETIME)
    if isinstance(dt, (int, float)):
        try:
            d = datetime(1899, 12, 30) + timedelta(days=float(dt))
            return d.strftime(FMT_DATETIME)
        except (ValueError, OSError):
            return str(dt)
    s = str(dt).strip()
    return s if s else "—"


def parse_date(val) -> datetime | None:
    """Строка dd.mm.yyyy, yyyy-mm-dd, число Excel или datetime -> datetime или None."""
    if val is None:
        return None
    if hasattr(val, "year"):
        return val
    if isinstance(val, (int, float)):
        try:
            return datetime(1899, 12, 30) + timedelta(days=float(val))
        except (ValueError, OSError):
            return None
    s = str(val).strip()
    if not s:
        return None
    for fmt in (FMT_DATE, FMT_DATETIME, "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return None


def normalize_start_date(s: str) -> str:
    """Ввод из формы (YYYY-MM-DD или dd.mm.yyyy) -> dd.mm.yyyy для хранения в БД."""
    s = (s or "").strip()
    if not s or len(s) < 10:
        return s
    if s[2] == "." and s[5] == "." and len(s) >= 10:
        return s[:10]
    parts = s[:10].split("-")
    if len(parts) == 3 and len(parts[0]) == 4 and len(parts[1]) == 2 and len(parts[2]) == 2:
        return f"{parts[2]}.{parts[1]}.{parts[0]}"
    return s
