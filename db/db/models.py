from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base


class User(Base):
    __tablename__ = "users"

    class Role(str, Enum):
        HR = "hr"
        ADMIN = "admin"
        EMPLOYEE = "employee"
        UNKNOWN = "unknown"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tg_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    role: Mapped[str] = mapped_column(String(50), default=Role.UNKNOWN.value)


class Request(Base):
    __tablename__ = "requests"

    STATUS_LABELS: dict[str, str] = {
        "new": "Новая",
        "in_progress": "В работе",
        "cancelled": "Отменена",
        "closed": "Закрыта",
    }

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    result_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    venue: Mapped[str] = mapped_column(String(255))
    position: Mapped[str] = mapped_column(String(255))
    headcount: Mapped[int] = mapped_column(Integer)
    schedule: Mapped[str] = mapped_column(String(100))
    salary: Mapped[str] = mapped_column(String(100))
    employment_type: Mapped[str] = mapped_column(String(50))
    requirements: Mapped[str] = mapped_column(Text)
    start_date: Mapped[str] = mapped_column(String(20))
    contact: Mapped[str] = mapped_column(String(255))
    work_time: Mapped[str | None] = mapped_column(String(100), nullable=True)
    requires_candidate_approval: Mapped[bool] = mapped_column(Boolean, default=True)

    owner_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("User", backref="requests")


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    request_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("requests.id"), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255))
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    work_experience: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact: Mapped[str] = mapped_column(String(255))
    resume_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    hunting_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    interview_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decision_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="new")
    result_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sheet_row_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approval_notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approval_decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    interview_feedback_notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    interview_feedback_decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    request = relationship("Request", backref="candidates")
