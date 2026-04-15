import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

_ROOT_ENV = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_ROOT_ENV)

_database_url = os.getenv("DATABASE_URL", "sqlite:///./data/bot.db")
_async_database_url = _database_url.replace("sqlite://", "sqlite+aiosqlite://", 1)


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    _async_database_url,
    connect_args={"check_same_thread": False} if "sqlite" in _async_database_url else {},
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db():
    async with async_session_maker() as session:
        yield session


def ensure_database() -> None:
    from . import models  # noqa: F401 — загрузка моделей для Base.metadata

    url = _database_url
    if url.startswith("sqlite") and url != "sqlite:///:memory:":
        path_str = url.replace("sqlite:///", "").split("?")[0]
        path = Path(path_str) if Path(path_str).is_absolute() else Path.cwd() / path_str
        path.parent.mkdir(parents=True, exist_ok=True)

    sync_engine = create_engine(
        url,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
    )
    Base.metadata.create_all(bind=sync_engine)
    existing = set(inspect(sync_engine).get_table_names())
    expected = set(Base.metadata.tables.keys())
    if expected - existing:
        raise RuntimeError(f"В БД отсутствуют таблицы: {expected - existing}")
    if url.startswith("sqlite") and "candidates" in existing:
        cols = [c["name"] for c in inspect(sync_engine).get_columns("candidates")]
        if "sheet_row_index" not in cols:
            with sync_engine.connect() as conn:
                conn.execute(text("ALTER TABLE candidates ADD COLUMN sheet_row_index INTEGER"))
                conn.commit()
        if "approval_notified_at" not in cols:
            with sync_engine.connect() as conn:
                conn.execute(text("ALTER TABLE candidates ADD COLUMN approval_notified_at DATETIME"))
                conn.execute(text(
                    "UPDATE candidates "
                    "SET approval_notified_at = created_at "
                    "WHERE interview_date IS NULL AND approval_notified_at IS NULL"
                ))
                conn.commit()
        if "approval_decided_at" not in cols:
            with sync_engine.connect() as conn:
                conn.execute(text("ALTER TABLE candidates ADD COLUMN approval_decided_at DATETIME"))
                conn.execute(text(
                    "UPDATE candidates "
                    "SET approval_decided_at = decision_date "
                    "WHERE decision_date IS NOT NULL AND approval_decided_at IS NULL"
                ))
                conn.commit()
        if "interview_feedback_notified_at" not in cols:
            with sync_engine.connect() as conn:
                conn.execute(text("ALTER TABLE candidates ADD COLUMN interview_feedback_notified_at DATETIME"))
                conn.commit()
        if "interview_feedback_decided_at" not in cols:
            with sync_engine.connect() as conn:
                conn.execute(text("ALTER TABLE candidates ADD COLUMN interview_feedback_decided_at DATETIME"))
                conn.commit()
    sync_engine.dispose()
