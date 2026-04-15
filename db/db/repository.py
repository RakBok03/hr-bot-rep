from datetime import date, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import Candidate, Request, User


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    r = await db.execute(select(UserRepo.model).where(UserRepo.model.id == user_id))
    return r.scalar_one_or_none()


class UserRepo:
    model = User
    __slots__ = ("tg_id", "db")

    def __init__(self, tg_id: int, db: AsyncSession) -> None:
        self.tg_id = tg_id
        self.db = db

    async def get(self) -> User | None:
        r = await self.db.execute(select(self.model).where(self.model.tg_id == self.tg_id))
        return r.scalar_one_or_none()

    async def get_or_create(self, full_name: str, username: str | None = None) -> User:
        user = await self.get()
        if user:
            return user
        user = self.model(tg_id=self.tg_id, full_name=full_name, username=username)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def delete_me(self) -> bool:
        """Удаляет пользователя и все связанные данные (его заявки и кандидатов по ним)."""
        user = await self.get()
        if user is None:
            return False
        await self.db.execute(delete(Candidate).where(Candidate.request_id.in_(
            select(Request.id).where(Request.owner_id == user.id)
        )))
        await self.db.execute(delete(Request).where(Request.owner_id == user.id))
        await self.db.execute(delete(self.model).where(self.model.id == user.id))
        await self.db.commit()
        return True


class RequestRepo:
    model = Request
    __slots__ = ("db",)

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, request_id: int) -> Request | None:
        r = await self.db.execute(select(self.model).where(self.model.id == request_id))
        return r.scalar_one_or_none()

    async def create(
        self,
        venue: str,
        position: str,
        headcount: int,
        schedule: str,
        salary: str,
        employment_type: str,
        requirements: str,
        start_date: str,
        contact: str,
        requires_candidate_approval: bool = True,
        work_time: str | None = None,
        owner_id: int | None = None,
    ) -> Request:
        obj = self.model(
            venue=venue,
            position=position,
            headcount=headcount,
            schedule=schedule,
            salary=salary,
            employment_type=employment_type,
            requirements=requirements,
            start_date=start_date,
            contact=contact,
            requires_candidate_approval=requires_candidate_approval,
            work_time=work_time,
            owner_id=owner_id,
        )
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def list_by_owner(self, owner_id: int) -> list[Request]:
        r = await self.db.execute(
            select(self.model).where(self.model.owner_id == owner_id).order_by(self.model.created_at.desc())
        )
        return list(r.scalars().all())

    async def list_active_with_owner(self) -> list[Request]:
        """Активные заявки (не закрыты и не отменены) с назначенным владельцем."""
        r = await self.db.execute(
            select(self.model).where(
                self.model.owner_id.is_not(None),
                ~self.model.status.in_(("closed", "cancelled")),
            )
        )
        return list(r.scalars().all())

    async def list_all(self) -> list[Request]:
        r = await self.db.execute(select(self.model).order_by(self.model.created_at.desc()))
        return list(r.scalars().all())

    async def update(
        self,
        request_id: int,
        *,
        venue: str | None = None,
        position: str | None = None,
        headcount: int | None = None,
        schedule: str | None = None,
        salary: str | None = None,
        employment_type: str | None = None,
        requirements: str | None = None,
        start_date: str | None = None,
        contact: str | None = None,
        work_time: str | None = None,
        requires_candidate_approval: bool | None = None,
    ) -> Request | None:
        req = await self.get(request_id)
        if req is None:
            return None
        if venue is not None:
            req.venue = venue
        if position is not None:
            req.position = position
        if headcount is not None:
            req.headcount = max(1, headcount)
        if schedule is not None:
            req.schedule = schedule
        if salary is not None:
            req.salary = salary
        if employment_type is not None:
            req.employment_type = employment_type
        if requirements is not None:
            req.requirements = requirements
        if start_date is not None:
            req.start_date = start_date
        if contact is not None:
            req.contact = contact
        if work_time is not None:
            req.work_time = work_time
        if requires_candidate_approval is not None:
            req.requires_candidate_approval = requires_candidate_approval
        await self.db.commit()
        await self.db.refresh(req)
        return req

    async def close(
        self,
        request_id: int,
        *,
        status: str = "closed",
        result_notes: str | None = None,
    ) -> Request | None:
        req = await self.get(request_id)
        if req is None:
            return None
        req.status = status if status in ("closed", "cancelled") else "closed"
        req.closed_at = datetime.utcnow()
        if result_notes is not None:
            req.result_notes = result_notes
        await self.db.commit()
        await self.db.refresh(req)
        return req


class CandidateRepo:
    model = Candidate
    __slots__ = ("db",)

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, candidate_id: int) -> Candidate | None:
        r = await self.db.execute(select(self.model).where(self.model.id == candidate_id))
        return r.scalar_one_or_none()

    async def get_by_sheet_row_index(self, sheet_row_index: int) -> Candidate | None:
        r = await self.db.execute(
            select(self.model).where(self.model.sheet_row_index == sheet_row_index)
        )
        return r.scalar_one_or_none()

    async def get_by_request_and_full_name(
        self,
        request_id: int | None,
        full_name: str,
    ) -> Candidate | None:
        if request_id is None or not (full_name or "").strip():
            return None
        r = await self.db.execute(
            select(self.model)
            .where(
                self.model.request_id == request_id,
                self.model.full_name == full_name.strip(),
            )
            .order_by(self.model.created_at.desc(), self.model.id.desc())
            .limit(1)
        )
        return r.scalar_one_or_none()

    async def create(
        self,
        full_name: str,
        contact: str,
        request_id: int | None = None,
        status: str | None = None,
        age: int | None = None,
        work_experience: str | None = None,
        resume_url: str | None = None,
        result_notes: str | None = None,
        hunting_date: datetime | None = None,
        interview_date: datetime | None = None,
        decision_date: datetime | None = None,
        sheet_row_index: int | None = None,
        approval_notified_at: datetime | None = None,
        approval_decided_at: datetime | None = None,
        interview_feedback_notified_at: datetime | None = None,
        interview_feedback_decided_at: datetime | None = None,
    ) -> Candidate:
        obj = self.model(
            full_name=full_name,
            contact=contact,
            request_id=request_id,
            status=status or "new",
            age=age,
            work_experience=work_experience,
            resume_url=resume_url,
            result_notes=result_notes,
            hunting_date=hunting_date,
            interview_date=interview_date,
            decision_date=decision_date,
            sheet_row_index=sheet_row_index,
            approval_notified_at=approval_notified_at,
            approval_decided_at=approval_decided_at,
            interview_feedback_notified_at=interview_feedback_notified_at,
            interview_feedback_decided_at=interview_feedback_decided_at,
        )
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def list_by_owner(self, owner_id: int) -> list[Candidate]:
        subq = select(Request.id).where(Request.owner_id == owner_id)
        r = await self.db.execute(
            select(self.model)
            .where(self.model.request_id.in_(subq))
            .options(selectinload(self.model.request))
            .order_by(self.model.created_at.desc())
        )
        return list(r.scalars().unique().all())

    async def list_all(self) -> list[Candidate]:
        r = await self.db.execute(
            select(self.model)
            .options(selectinload(self.model.request))
            .order_by(self.model.created_at.desc())
        )
        return list(r.scalars().unique().all())

    async def get_for_owner(self, candidate_id: int, owner_id: int) -> Candidate | None:
        r = await self.db.execute(
            select(self.model)
            .join(Request, Request.id == self.model.request_id)
            .where(
                self.model.id == candidate_id,
                Request.owner_id == owner_id,
            )
            .options(selectinload(self.model.request))
            .limit(1)
        )
        return r.scalar_one_or_none()

    async def has_active_approval_for_owner(self, owner_id: int) -> bool:
        """Есть ли уже показанный заказчику кандидат, по которому решение еще не принято."""
        r = await self.db.execute(
            select(self.model.id)
            .join(Request, Request.id == self.model.request_id)
            .where(
                Request.owner_id == owner_id,
                self.model.interview_date.is_(None),
                self.model.approval_notified_at.is_not(None),
                self.model.approval_decided_at.is_(None),
            )
            .limit(1)
        )
        return r.scalar_one_or_none() is not None

    async def get_next_pending_approval_for_owner(self, owner_id: int) -> Candidate | None:
        """Следующий кандидат на согласование, который еще не был отправлен заказчику."""
        r = await self.db.execute(
            select(self.model)
            .join(Request, Request.id == self.model.request_id)
            .where(
                Request.owner_id == owner_id,
                self.model.interview_date.is_(None),
                self.model.approval_notified_at.is_(None),
                self.model.approval_decided_at.is_(None),
            )
            .order_by(self.model.created_at.asc(), self.model.id.asc())
            .limit(1)
        )
        return r.scalar_one_or_none()

    async def has_active_interview_feedback_for_owner(self, owner_id: int) -> bool:
        r = await self.db.execute(
            select(self.model.id)
            .join(Request, Request.id == self.model.request_id)
            .where(
                Request.owner_id == owner_id,
                self.model.interview_feedback_notified_at.is_not(None),
                self.model.interview_feedback_decided_at.is_(None),
            )
            .limit(1)
        )
        return r.scalar_one_or_none() is not None

    def _pending_feedback_notified_condition(self, run_date: date | None):
        """Условие по уведомлению: если run_date задан — разрешаем повторную отправку на следующий день."""
        if run_date is None:
            return self.model.interview_feedback_notified_at.is_(None)
        return (
            self.model.interview_feedback_notified_at.is_(None)
            | (func.date(self.model.interview_feedback_notified_at) < str(run_date))
        )

    async def get_next_pending_interview_feedback_for_owner(
        self,
        owner_id: int,
        target_day: date,
        run_date: date | None = None,
    ) -> Candidate | None:
        r = await self.db.execute(
            select(self.model)
            .join(Request, Request.id == self.model.request_id)
            .where(
                Request.owner_id == owner_id,
                self.model.interview_date.is_not(None),
                func.date(self.model.interview_date) == str(target_day),
                self._pending_feedback_notified_condition(run_date),
                self.model.interview_feedback_decided_at.is_(None),
            )
            .order_by(self.model.interview_date.asc(), self.model.id.asc())
        )
        for cand in r.scalars().all():
            if not self._is_final_feedback_status(cand.status):
                return cand
        return None

    async def list_owner_ids_with_pending_interview_feedback(
        self, target_day: date, run_date: date | None = None
    ) -> list[int]:
        r = await self.db.execute(
            select(Request.owner_id, self.model.status)
            .join(self.model, self.model.request_id == Request.id)
            .where(
                Request.owner_id.is_not(None),
                self.model.interview_date.is_not(None),
                func.date(self.model.interview_date) == str(target_day),
                self._pending_feedback_notified_condition(run_date),
                self.model.interview_feedback_decided_at.is_(None),
            )
        )
        owner_ids: set[int] = set()
        for owner_id, status in r.all():
            if owner_id is None:
                continue
            if self._is_final_feedback_status(status):
                continue
            owner_ids.add(owner_id)
        return sorted(owner_ids)

    @staticmethod
    def _is_final_feedback_status(status: str | None) -> bool:
        s = (status or "").strip().lower()
        return s in {"принят", "hired", "отмена", "cancelled"}

    async def update(
        self,
        candidate_id: int,
        *,
        status: str | None = None,
        result_notes: str | None = None,
        interview_date: datetime | None = None,
        decision_date: datetime | None = None,
        approval_notified_at: datetime | None = None,
        approval_decided_at: datetime | None = None,
        interview_feedback_notified_at: datetime | None = None,
        interview_feedback_decided_at: datetime | None = None,
    ) -> Candidate | None:
        cand = await self.get(candidate_id)
        if cand is None:
            return None
        if status is not None:
            cand.status = status
        if result_notes is not None:
            cand.result_notes = result_notes
        if interview_date is not None:
            cand.interview_date = interview_date
        if decision_date is not None:
            cand.decision_date = decision_date
        if approval_notified_at is not None:
            cand.approval_notified_at = approval_notified_at
        if approval_decided_at is not None:
            cand.approval_decided_at = approval_decided_at
        if interview_feedback_notified_at is not None:
            cand.interview_feedback_notified_at = interview_feedback_notified_at
        if interview_feedback_decided_at is not None:
            cand.interview_feedback_decided_at = interview_feedback_decided_at
        await self.db.commit()
        await self.db.refresh(cand)
        return cand
