import asyncio
import logging
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Body, Header, HTTPException, Query
from sqlalchemy import case, func, select

from app.api.telegram_auth import validate_telegram_init_data
from app.api.utils import (
    build_hr_edit_message,
    build_hr_message,
    candidate_to_dict,
    format_approval,
    format_salary,
    html_esc,
    request_to_detail,
)
from app.config import get_settings
from db.repository import CandidateRepo, RequestRepo, UserRepo
from db.session import async_session_maker
from utils.dates import format_date, format_datetime, normalize_start_date, parse_date
from utils.telegram import safe_send_message as safe_send_tg_message

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["api"])

API_VERSION = "1.1.0"


@router.get("/health")
async def healthcheck() -> dict:
    return {"status": "ok", "api_version": API_VERSION}


@router.get("/version")
async def api_version() -> dict:
    return {"version": API_VERSION}


@router.get("/me")
async def me(x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data")) -> dict:
    init_data = x_telegram_init_data or ""
    settings = get_settings()
    payload = validate_telegram_init_data(init_data, settings.bot_token)
    if not payload:
        return {"from_telegram": False, "user": None, "registered": False}
    user_data = payload.get("user") or {}
    tg_id = user_data.get("id")
    if not tg_id:
        return {
            "from_telegram": True,
            "user": payload.get("user"),
            "auth_date": payload.get("auth_date"),
            "registered": False,
        }
    is_admin = int(tg_id) in set(settings.admin_tg_ids_list)
    async with async_session_maker() as db:
        user_repo = UserRepo(tg_id, db)
        user = await user_repo.get()
        registered = user is not None and (user.role or "unknown") != "unknown"
    return {
        "from_telegram": True,
        "user": payload.get("user"),
        "auth_date": payload.get("auth_date"),
        "registered": registered,
        "is_admin": is_admin,
    }


def _require_admin(settings, tg_id: int) -> None:
    if int(tg_id) not in set(settings.admin_tg_ids_list):
        raise HTTPException(status_code=403, detail="Недостаточно прав")


def _parse_iso_date(val: str) -> date:
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректная дата. Формат: YYYY-MM-DD")


def _cand_status_norm_expr():
    return func.lower(func.trim(func.coalesce(CandidateRepo.model.status, "")))


@router.get("/admin/dashboard")
async def admin_dashboard(
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"),
    from_: str = Query(..., alias="from"),
    to: str = Query(..., alias="to"),
    group_by: str = Query("day"),
) -> dict:
    settings = get_settings()
    payload = validate_telegram_init_data((x_telegram_init_data or ""), settings.bot_token)
    if not payload:
        logger.warning("admin_dashboard: no payload, unauthorized")
        raise HTTPException(status_code=401, detail="Необходимо открыть из Telegram")
    tg_user = payload.get("user") or {}
    tg_id = tg_user.get("id")
    if not tg_id:
        logger.warning("admin_dashboard: missing tg_id in payload=%r", tg_user)
        raise HTTPException(status_code=401, detail="Нет данных пользователя")
    _require_admin(settings, int(tg_id))

    logger.info("admin_dashboard: tg_id=%s from=%s to=%s group_by=%s", tg_id, from_, to, group_by)

    try:
        start = _parse_iso_date(from_)
        end_inclusive = _parse_iso_date(to)
        if end_inclusive < start:
            logger.warning("admin_dashboard: invalid period tg_id=%s from=%s to=%s", tg_id, from_, to)
            raise HTTPException(status_code=400, detail="Период задан неверно: to < from")
        end_exclusive = end_inclusive + timedelta(days=1)

        async with async_session_maker() as db:
            # KPI: requests
            req_created = (
                select(func.count(RequestRepo.model.id))
                .where(RequestRepo.model.created_at >= start, RequestRepo.model.created_at < end_exclusive)
            )
            req_closed = (
                select(func.count(RequestRepo.model.id))
                .where(
                    RequestRepo.model.closed_at.is_not(None),
                    RequestRepo.model.closed_at >= start,
                    RequestRepo.model.closed_at < end_exclusive,
                    RequestRepo.model.status == "closed",
                )
            )
            req_cancelled = (
                select(func.count(RequestRepo.model.id))
                .where(
                    RequestRepo.model.closed_at.is_not(None),
                    RequestRepo.model.closed_at >= start,
                    RequestRepo.model.closed_at < end_exclusive,
                    RequestRepo.model.status == "cancelled",
                )
            )

            # KPI: candidates
            cand_created = (
                select(func.count(CandidateRepo.model.id))
                .where(CandidateRepo.model.created_at >= start, CandidateRepo.model.created_at < end_exclusive)
            )

            st = func.lower(func.trim(func.coalesce(CandidateRepo.model.status, "")))
            hired_cond = st.in_(("hired", "принят"))
            rejected_cond = st.in_(("rejected", "отказ"))

            cand_hired = (
                select(func.count(CandidateRepo.model.id))
                .where(
                    CandidateRepo.model.decision_date.is_not(None),
                    CandidateRepo.model.decision_date >= start,
                    CandidateRepo.model.decision_date < end_exclusive,
                    hired_cond,
                )
            )
            cand_rejected = (
                select(func.count(CandidateRepo.model.id))
                .where(
                    CandidateRepo.model.decision_date.is_not(None),
                    CandidateRepo.model.decision_date >= start,
                    CandidateRepo.model.decision_date < end_exclusive,
                    rejected_cond,
                )
            )
            cand_interviews = (
                select(func.count(CandidateRepo.model.id))
                .where(
                    CandidateRepo.model.interview_date.is_not(None),
                    CandidateRepo.model.interview_date >= start,
                    CandidateRepo.model.interview_date < end_exclusive,
                )
            )

            kpi = {
                "requests_created": int((await db.execute(req_created)).scalar_one() or 0),
                "requests_closed": int((await db.execute(req_closed)).scalar_one() or 0),
                "requests_cancelled": int((await db.execute(req_cancelled)).scalar_one() or 0),
                "candidates_created": int((await db.execute(cand_created)).scalar_one() or 0),
                "interviews_scheduled": int((await db.execute(cand_interviews)).scalar_one() or 0),
                "hired": int((await db.execute(cand_hired)).scalar_one() or 0),
                "rejected": int((await db.execute(cand_rejected)).scalar_one() or 0),
            }

            # Timeseries (day): requests_created, interviews, hired, rejected
            day_expr_req = func.date(RequestRepo.model.created_at).label("d")
            day_expr_interview = func.date(CandidateRepo.model.interview_date).label("d")
            day_expr_decision = func.date(CandidateRepo.model.decision_date).label("d")

            req_ts = await db.execute(
                select(day_expr_req, func.count(RequestRepo.model.id))
                .where(RequestRepo.model.created_at >= start, RequestRepo.model.created_at < end_exclusive)
                .group_by(day_expr_req)
                .order_by(day_expr_req)
            )
            interview_ts = await db.execute(
                select(day_expr_interview, func.count(CandidateRepo.model.id))
                .where(
                    CandidateRepo.model.interview_date.is_not(None),
                    CandidateRepo.model.interview_date >= start,
                    CandidateRepo.model.interview_date < end_exclusive,
                )
                .group_by(day_expr_interview)
                .order_by(day_expr_interview)
            )
            hired_ts = await db.execute(
                select(day_expr_decision, func.count(CandidateRepo.model.id))
                .where(
                    CandidateRepo.model.decision_date.is_not(None),
                    CandidateRepo.model.decision_date >= start,
                    CandidateRepo.model.decision_date < end_exclusive,
                    hired_cond,
                )
                .group_by(day_expr_decision)
                .order_by(day_expr_decision)
            )
            rejected_ts = await db.execute(
                select(day_expr_decision, func.count(CandidateRepo.model.id))
                .where(
                    CandidateRepo.model.decision_date.is_not(None),
                    CandidateRepo.model.decision_date >= start,
                    CandidateRepo.model.decision_date < end_exclusive,
                    rejected_cond,
                )
                .group_by(day_expr_decision)
                .order_by(day_expr_decision)
            )

            def _to_map(rows):
                return {str(d): int(c) for d, c in rows if d is not None}

            req_map = _to_map(req_ts.all())
            interview_map = _to_map(interview_ts.all())
            hired_map = _to_map(hired_ts.all())
            rejected_map = _to_map(rejected_ts.all())

            dates: list[str] = []
            cur = start
            while cur <= end_inclusive:
                dates.append(cur.strftime("%Y-%m-%d"))
                cur += timedelta(days=1)

            timeseries = [
                {
                    "date": d,
                    "requests_created": req_map.get(d, 0),
                    "interviews_scheduled": interview_map.get(d, 0),
                    "hired": hired_map.get(d, 0),
                    "rejected": rejected_map.get(d, 0),
                }
                for d in dates
            ]

            # Breakdowns: top venues by requests created
            venue_rows = await db.execute(
                select(RequestRepo.model.venue, func.count(RequestRepo.model.id).label("cnt"))
                .where(RequestRepo.model.created_at >= start, RequestRepo.model.created_at < end_exclusive)
                .group_by(RequestRepo.model.venue)
                .order_by(func.count(RequestRepo.model.id).desc())
                .limit(10)
            )
            breakdowns = {
                "top_venues_requests": [
                    {"venue": v or "—", "count": int(c)} for v, c in venue_rows.all()
                ]
            }

        return {
            "from": start.strftime("%Y-%m-%d"),
            "to": end_inclusive.strftime("%Y-%m-%d"),
            "group_by": group_by,
            "kpi": kpi,
            "timeseries": timeseries,
            "breakdowns": breakdowns,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("admin_dashboard: unexpected error tg_id=%s from=%s to=%s", tg_id, from_, to)
        raise

@router.get("/admin/requests")
async def admin_list_requests(x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data")) -> dict:
    init_data = x_telegram_init_data or ""
    settings = get_settings()
    payload = validate_telegram_init_data(init_data, settings.bot_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Необходимо открыть из Telegram")
    tg_id = (payload.get("user") or {}).get("id")
    if not tg_id:
        raise HTTPException(status_code=401, detail="Нет данных пользователя")
    _require_admin(settings, int(tg_id))
    async with async_session_maker() as db:
        items = await RequestRepo(db).list_all()
    requests = [
        {
            "id": r.id,
            "venue": r.venue or "",
            "position": r.position or "",
            "status": r.status or "new",
            "headcount": r.headcount,
            "created_at": format_datetime(r.created_at) if r.created_at else None,
            "closed_at": format_datetime(r.closed_at) if r.closed_at else None,
            "start_date": format_date(r.start_date or "") or None,
        }
        for r in items
    ]
    return {"requests": requests}


@router.get("/admin/candidates")
async def admin_list_candidates(x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data")) -> dict:
    init_data = x_telegram_init_data or ""
    settings = get_settings()
    payload = validate_telegram_init_data(init_data, settings.bot_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Необходимо открыть из Telegram")
    tg_id = (payload.get("user") or {}).get("id")
    if not tg_id:
        raise HTTPException(status_code=401, detail="Нет данных пользователя")
    _require_admin(settings, int(tg_id))
    async with async_session_maker() as db:
        items = await CandidateRepo(db).list_all()
    candidates = [
        candidate_to_dict(
            c,
            request_venue=(c.request.venue or "") if c.request else "",
            request_position=(c.request.position or "") if c.request else "",
        )
        for c in items
    ]
    return {"candidates": candidates}


@router.get("/requests")
async def list_requests(x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data")) -> dict:
    init_data = x_telegram_init_data or ""
    settings = get_settings()
    payload = validate_telegram_init_data(init_data, settings.bot_token)
    if not payload:
        return {"requests": []}
    user_data = payload.get("user") or {}
    tg_id = user_data.get("id")
    if not tg_id:
        return {"requests": []}
    async with async_session_maker() as db:
        user_repo = UserRepo(tg_id, db)
        user = await user_repo.get()
        if not user:
            return {"requests": []}
        req_repo = RequestRepo(db)
        items = await req_repo.list_by_owner(user.id)
    requests = [
        {
            "id": r.id,
            "venue": r.venue or "",
            "position": r.position or "",
            "status": r.status or "new",
            "headcount": r.headcount,
            "created_at": format_datetime(r.created_at) if r.created_at else None,
            "closed_at": format_datetime(r.closed_at) if r.closed_at else None,
            "start_date": format_date(r.start_date or "") or None,
        }
        for r in items
    ]
    return {"requests": requests}


@router.get("/requests/{request_id}")
async def get_request(
    request_id: int,
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"),
) -> dict:
    init_data = x_telegram_init_data or ""
    settings = get_settings()
    payload = validate_telegram_init_data(init_data, settings.bot_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Необходимо открыть из Telegram")
    user_data = payload.get("user") or {}
    tg_id = user_data.get("id")
    if not tg_id:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    async with async_session_maker() as db:
        user_repo = UserRepo(tg_id, db)
        user = await user_repo.get()
        if not user:
            raise HTTPException(status_code=404, detail="Заявка не найдена")
        req_repo = RequestRepo(db)
        req = await req_repo.get(request_id)
        if not req or req.owner_id != user.id:
            raise HTTPException(status_code=404, detail="Заявка не найдена")
    return request_to_detail(req)


@router.get("/candidates")
async def list_candidates(
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"),
) -> dict:
    init_data = x_telegram_init_data or ""
    payload = validate_telegram_init_data(init_data, get_settings().bot_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Необходимо открыть из Telegram")
    tg_id = (payload.get("user") or {}).get("id")
    if not tg_id:
        raise HTTPException(status_code=401, detail="Нет данных пользователя")
    async with async_session_maker() as db:
        user_repo = UserRepo(tg_id, db)
        user = await user_repo.get()
        if not user:
            return {"candidates": []}
        candidate_repo = CandidateRepo(db)
        items = await candidate_repo.list_by_owner(user.id)
    candidates = [
        candidate_to_dict(
            c,
            request_venue=(c.request.venue or "") if c.request else "",
            request_position=(c.request.position or "") if c.request else "",
        )
        for c in items
    ]
    return {"candidates": candidates}


@router.get("/candidates/{candidate_id}")
async def get_candidate_route(
    candidate_id: int,
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"),
) -> dict:
    init_data = x_telegram_init_data or ""
    payload = validate_telegram_init_data(init_data, get_settings().bot_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Необходимо открыть из Telegram")
    tg_id = (payload.get("user") or {}).get("id")
    if not tg_id:
        raise HTTPException(status_code=404, detail="Не найдено")
    async with async_session_maker() as db:
        user_repo = UserRepo(tg_id, db)
        user = await user_repo.get()
        if not user:
            raise HTTPException(status_code=404, detail="Не найдено")
        candidate_repo = CandidateRepo(db)
        items = await candidate_repo.list_by_owner(user.id)
        cand = next((c for c in items if c.id == candidate_id), None)
        if not cand:
            raise HTTPException(status_code=404, detail="Кандидат не найден")
        req = cand.request
        venue = (req.venue or "") if req else ""
        position = (req.position or "") if req else ""
    return candidate_to_dict(cand, request_venue=venue, request_position=position)


@router.patch("/candidates/{candidate_id}")
async def patch_candidate(candidate_id: int, body: dict = Body(...), x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data")) -> dict:
    init_data = x_telegram_init_data or ""
    settings = get_settings()
    payload = validate_telegram_init_data(init_data, settings.bot_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Необходимо открыть из Telegram")
    tg_id = (payload.get("user") or {}).get("id")
    if not tg_id:
        raise HTTPException(status_code=401, detail="Нет данных пользователя")

    def _resume_line(cand) -> str:
        resume_url = (getattr(cand, "resume_url", None) or "").strip()
        return f'<a href="{html_esc(resume_url)}">ссылка</a>' if resume_url else "—"

    async def _notify_hr(text: str, warn_ctx: str) -> None:
        hr_chat_id = (settings.hr_chat_id or "").strip()
        if not (hr_chat_id and settings.bot_token):
            return
        ok = await safe_send_tg_message(
            settings.bot_token,
            hr_chat_id,
            text,
            parse_mode="HTML",
            logger=logger,
        )
        if not ok:
            logger.warning("HR notify (%s): отправка не удалась candidate_id=%s", warn_ctx, candidate_id)

    async def _sheets_update(fn_name: str, *args) -> None:
        try:
            from integrations.client import GoogleSheetsClient
            from integrations.config import GoogleSheetsConfig

            config = GoogleSheetsConfig()
            if not config.is_configured:
                return
            client = GoogleSheetsClient(config)
            fn = getattr(client, fn_name)
            await asyncio.to_thread(fn, *args)
        except Exception:
            logger.exception("Google Sheets: не удалось обновить кандидата candidate_id=%s (%s)", candidate_id, fn_name)

    async with async_session_maker() as db:
        user_repo = UserRepo(tg_id, db)
        user = await user_repo.get()
        if not user:
            raise HTTPException(status_code=404, detail="Не найдено")
        candidate_repo = CandidateRepo(db)
        cand_ref = await candidate_repo.get_for_owner(candidate_id, user.id)
        if not cand_ref:
            raise HTTPException(status_code=404, detail="Кандидат не найден")
        req = cand_ref.request
        venue = (req.venue or "") if req else ""
        position = (req.position or "") if req else ""
        full_name = (cand_ref.full_name or "") if cand_ref else ""
        status = body.get("status")
        result_notes = body.get("result_notes")
        interview_date_raw = body.get("interview_date") or body.get("interviewDate")
        interview_date = parse_date(interview_date_raw)
        if interview_date_raw is not None and interview_date is None:
            logger.warning("PATCH candidate: не удалось распарсить interview_date candidate_id=%s raw=%r", candidate_id, interview_date_raw)
        decision_date = datetime.utcnow() if status in ("hired", "rejected") else None
        cand = await candidate_repo.update(
            candidate_id,
            status=status,
            result_notes=result_notes if result_notes is not None else None,
            interview_date=interview_date,
            decision_date=decision_date,
        )
    if not cand:
        raise HTTPException(status_code=404, detail="Кандидат не найден")
    if status == "hired":
        decision_str = format_datetime(cand.decision_date) if cand.decision_date else ""
        lines = [
            "✅ <b>Кандидат принят</b>",
            "",
            f"#Результат #ID_{getattr(req, 'id', '')} | {html_esc(venue or '—')} · {html_esc(position or '—')}",
            f"├─ Кандидат: {html_esc(full_name)}",
            f"├─ Дата решения: {decision_str}",
            f"├─ Резюме: {_resume_line(cand)}",
        ]
        await _notify_hr("\n".join(lines), "candidate hired")

        await _sheets_update(
            "update_candidate_decision",
            candidate_id,
            format_datetime(cand.decision_date) if cand.decision_date else "",
            "Принят",
            None,
            getattr(cand, "sheet_row_index", None),
            getattr(req, "id", None),
            full_name,
        )
    if status == "rejected":
        decision_str = format_datetime(cand.decision_date) if cand.decision_date else ""
        notes = (cand.result_notes or "").strip()
        lines = [
            "❌ <b>Кандидат — отказ</b>",
            "",
            f"#Результат #ID_{getattr(req, 'id', '')} | {html_esc(venue or '—')} · {html_esc(position or '—')}",
            f"├─ Кандидат: {html_esc(full_name)}",
            f"├─ Дата решения: {decision_str}",
            f"├─ Резюме: {_resume_line(cand)}",
        ]
        if notes:
            lines.extend(["", "Причина:", f"<blockquote>{html_esc(notes)}</blockquote>"])
        await _notify_hr("\n".join(lines), "candidate rejected")

        await _sheets_update(
            "update_candidate_decision",
            candidate_id,
            format_datetime(cand.decision_date) if cand.decision_date else "",
            "Отказ",
            cand.result_notes or "",
            getattr(cand, "sheet_row_index", None),
            getattr(req, "id", None),
            full_name,
        )
    if interview_date is not None:
        interview_str = format_datetime(cand.interview_date) if cand.interview_date else ""
        lines = [
            "✍🏻 <b>Перенос собеседования</b>",
            "",
            f"#Заявка #ID_{getattr(req, 'id', '')} | {html_esc(venue or '—')} · {html_esc(position or '—')}",
            f"├─ Кандидат: {html_esc(full_name)}",
            f"├─ Новая дата собеседования: {interview_str}",
            f"├─ Резюме: {_resume_line(cand)}",
        ]
        await _notify_hr("\n".join(lines), "reschedule")

        await _sheets_update(
            "update_candidate_interview",
            candidate_id,
            format_datetime(cand.interview_date) if cand.interview_date else "",
            getattr(cand, "sheet_row_index", None),
            getattr(req, "id", None),
            full_name,
        )
    return candidate_to_dict(cand, request_venue=venue, request_position=position)


@router.post("/requests/{request_id}/close")
async def close_request(request_id: int, body: dict, x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data")) -> dict:
    def _normalize_close_status(val) -> str:
        s = (val or "closed").strip().lower()
        return s if s in ("closed", "cancelled") else "closed"

    init_data = x_telegram_init_data or ""
    settings = get_settings()
    payload = validate_telegram_init_data(init_data, settings.bot_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Необходимо открыть из Telegram")
    user_data = payload.get("user") or {}
    tg_id = user_data.get("id")
    if not tg_id:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    result_notes = (body.get("result_notes") or body.get("reason") or "").strip()
    if not result_notes:
        raise HTTPException(status_code=400, detail="Укажите комментарий")
    status = _normalize_close_status(body.get("status"))
    async with async_session_maker() as db:
        user_repo = UserRepo(tg_id, db)
        user = await user_repo.get()
        if not user:
            raise HTTPException(status_code=404, detail="Заявка не найдена")
        req_repo = RequestRepo(db)
        req = await req_repo.get(request_id)
        if not req or req.owner_id != user.id:
            raise HTTPException(status_code=404, detail="Заявка не найдена")
        req = await req_repo.close(request_id, status=status, result_notes=result_notes)

    hr_chat_id = (settings.hr_chat_id or "").strip()
    if hr_chat_id and settings.bot_token:
        approval = getattr(req, "requires_candidate_approval", True)
        header = (
            f"❌ #Заявка | #ID_{req.id} | Отменена"
            if status == "cancelled"
            else f"✅ #Заявка | #ID_{req.id} | Закрыта"
        )
        lines = [
            header,
            "",
            f"├─ Площадка: {html_esc(req.venue or '—')}",
            f"├─ Должность: {html_esc(req.position or '—')}",
            f"├─ Количество: {req.headcount} чел.",
            f"├─ График: {html_esc(req.schedule or '—')}",
        ]
        if getattr(req, "work_time", None):
            lines.append(f"├─ Время работы: {html_esc(req.work_time or '—')}")
        lines.extend([
            f"├─ Оклад: {html_esc(format_salary(req.salary or '') or '—')}",
            f"├─ Вид оформления: {html_esc(req.employment_type or '—')}",
            f"├─ Требования: {html_esc(req.requirements or '—')}",
            f"├─ Дата выхода: {html_esc(format_date(req.start_date or '') or '—')}",
            f"├─ Контакт: {html_esc(req.contact or '—')}",
            f"├─ Согласование кандидатов: {format_approval(approval)}",
        ])
        lines.extend(["", "Причина:", f"<blockquote>{html_esc(result_notes)}</blockquote>"])
        text = "\n".join(lines)
        ok = await safe_send_tg_message(
            settings.bot_token,
            hr_chat_id,
            text,
            parse_mode="HTML",
            logger=logger,
        )
        if not ok:
            logger.warning("HR notify (close): отправка не удалась request_id=%s hr_chat_id=%s", req.id, hr_chat_id)

    try:
        from integrations.client import GoogleSheetsClient
        from integrations.config import GoogleSheetsConfig

        config = GoogleSheetsConfig()
        if config.is_configured:
            status_display = "Закрыто" if status == "closed" else "Отмена"
            closed_at_str = format_datetime(req.closed_at) if req.closed_at else ""
            client = GoogleSheetsClient(config)
            await asyncio.to_thread(
                client.update_request_on_close,
                req.id,
                status_display,
                closed_at_str,
                req.result_notes or "",
            )
            logger.info("Google Sheets: заявка request_id=%s обновлена (закрытие/отмена)", req.id)
    except Exception:
        logger.exception(
            "Google Sheets: не удалось обновить заявку request_id=%s при закрытии",
            req.id,
        )

    return {"id": req.id, "status": req.status}


@router.patch("/requests/{request_id}")
async def update_request(request_id: int, body: dict, x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data")) -> dict:
    init_data = x_telegram_init_data or ""
    settings = get_settings()
    payload = validate_telegram_init_data(init_data, settings.bot_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Необходимо открыть из Telegram")
    user_data = payload.get("user") or {}
    tg_id = user_data.get("id")
    if not tg_id:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    def _parse_bool(val) -> bool | None:
        if val is None:
            return None
        if val is True or val is False:
            return bool(val)
        if isinstance(val, str):
            return val.strip().lower() in ("true", "1", "yes", "да")
        return bool(val)

    def _parse_headcount(val) -> int | None:
        if val is None:
            return None
        try:
            return max(1, int(val) if val else 1)
        except (TypeError, ValueError):
            return 1

    async with async_session_maker() as db:
        user_repo = UserRepo(tg_id, db)
        user = await user_repo.get()
        if not user:
            raise HTTPException(status_code=404, detail="Заявка не найдена")
        req_repo = RequestRepo(db)
        req = await req_repo.get(request_id)
        if not req or req.owner_id != user.id:
            raise HTTPException(status_code=404, detail="Заявка не найдена")
        if req.status == "closed":
            raise HTTPException(status_code=400, detail="Закрытую заявку нельзя редактировать")

        old = {
            "venue": req.venue or "",
            "position": req.position or "",
            "headcount": req.headcount or 1,
            "schedule": req.schedule or "",
            "salary": req.salary or "",
            "employment_type": req.employment_type or "",
            "requirements": req.requirements or "",
            "start_date": req.start_date or "",
            "contact": req.contact or "",
            "work_time": getattr(req, "work_time", None) or "",
            "requires_candidate_approval": getattr(req, "requires_candidate_approval", True),
        }

        new = {
            "venue": (body.get("venue") or "").strip(),
            "position": (body.get("position") or "").strip(),
            "headcount": _parse_headcount(body.get("headcount")),
            "schedule": (body.get("schedule") or "").strip(),
            "salary": (body.get("salary") or "").strip(),
            "employment_type": (body.get("employment_type") or "").strip(),
            "requirements": (body.get("requirements") or "").strip(),
            "start_date": normalize_start_date(body.get("start_date") or "") or None,
            "contact": (body.get("contact") or "").strip(),
            "work_time": (body.get("work_time") or "").strip() or None,
            "requires_candidate_approval": _parse_bool(body.get("candidate_approval_required")),
        }

        req = await req_repo.update(
            request_id,
            venue=new["venue"],
            position=new["position"],
            headcount=new["headcount"],
            schedule=new["schedule"],
            salary=new["salary"],
            employment_type=new["employment_type"],
            requirements=new["requirements"],
            start_date=new["start_date"],
            contact=new["contact"],
            work_time=new["work_time"],
            requires_candidate_approval=new["requires_candidate_approval"],
        )

    hr_chat_id = (settings.hr_chat_id or "").strip()
    if hr_chat_id and settings.bot_token:
        text = build_hr_edit_message(
            request_id,
            old["venue"],
            old["position"],
            old["headcount"],
            old["schedule"],
            old["salary"],
            old["employment_type"],
            old["requirements"],
            old["start_date"],
            old["contact"],
            old["work_time"],
            old["requires_candidate_approval"],
            new["venue"],
            new["position"],
            new["headcount"],
            new["schedule"],
            new["salary"],
            new["employment_type"],
            new["requirements"],
            new["start_date"] or "",
            new["contact"],
            (new["work_time"] or ""),
            new["requires_candidate_approval"]
            if new["requires_candidate_approval"] is not None
            else getattr(req, "requires_candidate_approval", True),
        )
        ok = await safe_send_tg_message(
            settings.bot_token,
            hr_chat_id,
            text,
            parse_mode="HTML",
            logger=logger,
        )
        if not ok:
            logger.warning("HR notify (edit): отправка не удалась request_id=%s hr_chat_id=%s", request_id, hr_chat_id)

    try:
        from integrations.client import GoogleSheetsClient
        from integrations.config import GoogleSheetsConfig

        config = GoogleSheetsConfig()
        if config.is_configured:
            _status_label = {"new": "Новая", "in_progress": "В работе", "closed": "Закрыто", "cancelled": "Отмена"}
            status_display = _status_label.get(req.status or "new", req.status or "Новая")
            client = GoogleSheetsClient(config)
            await asyncio.to_thread(
                client.update_request_on_edit,
                req.id,
                status_display,
                req.venue or "",
                req.position or "",
                req.headcount or 0,
                req.schedule or "",
                getattr(req, "work_time", None) or "",
                req.salary or "",
                req.employment_type or "",
                req.requirements or "",
                req.start_date or "",
                req.contact or "",
                "Да" if getattr(req, "requires_candidate_approval", True) else "Нет",
            )
            logger.info("Google Sheets: заявка request_id=%s обновлена (редактирование)", req.id)
    except Exception:
        logger.exception(
            "Google Sheets: не удалось обновить заявку request_id=%s при редактировании",
            req.id,
        )

    return request_to_detail(req)


@router.post("/requests")
async def create_request(body: dict, x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data")) -> dict:
    init_data = x_telegram_init_data or ""
    settings = get_settings()
    payload = validate_telegram_init_data(init_data, settings.bot_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Необходимо открыть из Telegram")
    user_data = payload.get("user") or {}
    tg_id = user_data.get("id")
    if not tg_id:
        raise HTTPException(status_code=400, detail="Нет данных пользователя")

    def _parse_bool(val) -> bool:
        if val is True or val is False:
            return bool(val)
        if isinstance(val, str):
            return val.strip().lower() in ("true", "1", "yes", "да")
        return bool(val)

    def _parse_headcount(val) -> int:
        try:
            return max(1, int(val) if val else 1)
        except (TypeError, ValueError):
            return 1

    def _strip_or_dash(val) -> str:
        return (val or "").strip() or "—"

    candidate_approval_required = _parse_bool(body.get("candidate_approval_required", True))
    payload_new = {
        "venue": _strip_or_dash(body.get("venue")),
        "position": _strip_or_dash(body.get("position")),
        "headcount": _parse_headcount(body.get("headcount", 1)),
        "schedule": _strip_or_dash(body.get("schedule")),
        "salary": _strip_or_dash(body.get("salary")),
        "employment_type": _strip_or_dash(body.get("employment_type")),
        "requirements": _strip_or_dash(body.get("requirements")),
        "start_date": normalize_start_date(body.get("start_date") or "") or "—",
        "contact": _strip_or_dash(body.get("contact")),
        "work_time": (body.get("work_time") or "").strip() or None,
        "requires_candidate_approval": candidate_approval_required,
    }

    async with async_session_maker() as db:
        user_repo = UserRepo(tg_id, db)
        full_name = " ".join(
            part for part in [user_data.get("first_name", ""), user_data.get("last_name", "")] if (part or "").strip()
        ).strip()
        user = await user_repo.get_or_create(
            full_name=full_name,
            username=user_data.get("username"),
        )
        req_repo = RequestRepo(db)
        req = await req_repo.create(
            venue=payload_new["venue"],
            position=payload_new["position"],
            headcount=payload_new["headcount"],
            schedule=payload_new["schedule"],
            salary=payload_new["salary"],
            employment_type=payload_new["employment_type"],
            requirements=payload_new["requirements"],
            start_date=payload_new["start_date"],
            contact=payload_new["contact"],
            requires_candidate_approval=payload_new["requires_candidate_approval"],
            work_time=payload_new["work_time"],
            owner_id=user.id,
        )

    hr_chat_id = (settings.hr_chat_id or "").strip()
    if hr_chat_id and settings.bot_token:
        text = build_hr_message(
            req.id,
            payload_new["venue"],
            payload_new["position"],
            req.headcount,
            payload_new["schedule"],
            payload_new["salary"],
            payload_new["employment_type"],
            payload_new["requirements"],
            payload_new["start_date"],
            payload_new["contact"],
            candidate_approval_required=getattr(req, "requires_candidate_approval", True),
            work_time=getattr(req, "work_time", None),
        )
        ok = await safe_send_tg_message(
            settings.bot_token,
            hr_chat_id,
            text,
            parse_mode="HTML",
            logger=logger,
        )
        if not ok:
            logger.warning("HR notify (create): отправка не удалась request_id=%s hr_chat_id=%s", req.id, hr_chat_id)

    try:
        from integrations.client import GoogleSheetsClient
        from integrations.config import GoogleSheetsConfig

        config = GoogleSheetsConfig()
        if config.is_configured:
            created_at = format_datetime(req.created_at) if req.created_at else ""
            _status_label = {"new": "Новая", "in_progress": "В работе", "closed": "Закрыто", "cancelled": "Отмена"}
            status_display = _status_label.get(req.status or "new", req.status or "Новая")

            row = [
                req.id,
                status_display,
                req.venue or "",
                req.position or "",
                req.headcount or 0,
                req.schedule or "",
                getattr(req, "work_time", None) or "",
                req.salary or "",
                req.employment_type or "",
                req.requirements or "",
                format_date(req.start_date or "") or "",
                req.contact or "",
                "Да" if getattr(req, "requires_candidate_approval", True) else "Нет",
                created_at,
                "",
                "",
            ]
            client = GoogleSheetsClient(config)
            await asyncio.to_thread(client.append_request_row, row)
            logger.info("Google Sheets: заявка request_id=%s добавлена в таблицу", req.id)
    except Exception:
        logger.exception(
            "Google Sheets: не удалось добавить заявку request_id=%s в таблицу",
            req.id,
        )

    return {"id": req.id, "status": req.status}
