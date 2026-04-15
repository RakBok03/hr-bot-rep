import html

from utils.dates import format_date, format_datetime


def format_salary(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "—"
    digits = "".join(c for c in s if c.isdigit())
    if not digits:
        return s
    parts = []
    for i, c in enumerate(reversed(digits)):
        if i > 0 and i % 3 == 0:
            parts.append(" ")
        parts.append(c)
    return "".join(reversed(parts))


def format_approval(val: bool) -> str:
    return "Да" if val else "Нет"


def html_esc(s: str) -> str:
    return html.escape(str(s or "—"))


def build_hr_message(
    req_id: int,
    venue: str,
    position: str,
    headcount: int,
    schedule: str,
    salary: str,
    employment_type: str,
    requirements: str,
    start_date: str,
    contact: str,
    candidate_approval_required: bool = True,
    work_time: str | None = None,
) -> str:
    lines = [f"🆕 #Заявка | #ID_{req_id}\n"]
    lines.append(f"├─ Площадка: {venue}")
    lines.append(f"├─ Должность: {position}")
    lines.append(f"├─ Количество: {headcount} чел.")
    lines.append(f"├─ График: {schedule}")
    if work_time:
        lines.append(f"├─ Время работы: {work_time}")
    lines.extend(
        [
            f"├─ Оклад: {format_salary(salary)}",
            f"├─ Вид оформления: {employment_type}",
            f"├─ Требования: {requirements}",
            f"├─ Дата выхода: {format_date(start_date)}",
            f"├─ Контакт: {contact}",
            f"├─ Согласование кандидатов: {format_approval(candidate_approval_required)}",
        ]
    )
    return "\n".join(lines)


def build_hr_edit_message(
    req_id: int,
    old_venue: str,
    old_position: str,
    old_headcount: int,
    old_schedule: str,
    old_salary: str,
    old_employment_type: str,
    old_requirements: str,
    old_start_date: str,
    old_contact: str,
    old_work_time: str | None,
    old_candidate_approval_required: bool,
    new_venue: str,
    new_position: str,
    new_headcount: int,
    new_schedule: str,
    new_salary: str,
    new_employment_type: str,
    new_requirements: str,
    new_start_date: str,
    new_contact: str,
    new_work_time: str | None,
    new_candidate_approval_required: bool,
) -> str:
    lines = [f"✍🏻 #Заявка | #ID_{req_id} | Изменение заявки\n"]
    dash = "—"

    def row(label: str, old_val: str, new_val: str) -> None:
        if old_val != new_val:
            lines.append(f"├─ {label}: {html_esc(old_val)} → <b>{html_esc(new_val)}</b>")
        else:
            lines.append(f"├─ {label}: {html_esc(new_val)}")

    row("Площадка", old_venue or dash, new_venue or dash)
    row("Должность", old_position or dash, new_position or dash)
    row("Количество", f"{(old_headcount or 0)} чел.", f"{new_headcount} чел.")
    row("График", old_schedule or dash, new_schedule or dash)
    row("Время работы", old_work_time or dash, new_work_time or dash)
    row("Оклад", format_salary(old_salary) or dash, format_salary(new_salary) or dash)
    row("Вид оформления", old_employment_type or dash, new_employment_type or dash)
    row("Требования", old_requirements or dash, new_requirements or dash)
    row("Дата выхода", format_date(old_start_date) or dash, format_date(new_start_date) or dash)
    row("Контакт", old_contact or dash, new_contact or dash)
    row("Согласование кандидатов", format_approval(old_candidate_approval_required), format_approval(new_candidate_approval_required))

    return "\n".join(lines)


def request_to_detail(r) -> dict:
    return {
        "id": r.id,
        "venue": r.venue or "",
        "position": r.position or "",
        "status": r.status or "new",
        "headcount": r.headcount,
        "schedule": r.schedule or "",
        "salary": r.salary or "",
        "employment_type": r.employment_type or "",
        "requirements": r.requirements or "",
        "start_date": format_date(r.start_date or "") or "",
        "contact": r.contact or "",
        "work_time": getattr(r, "work_time", None) or "",
        "candidate_approval_required": getattr(r, "requires_candidate_approval", True),
        "created_at": format_datetime(r.created_at) if r.created_at else None,
        "closed_at": format_datetime(r.closed_at) if getattr(r, "closed_at", None) else None,
        "result_notes": getattr(r, "result_notes", None) or "",
    }


def candidate_to_dict(c, request_venue: str = "", request_position: str = "") -> dict:
    hunting = getattr(c, "hunting_date", None)
    return {
        "id": c.id,
        "request_id": c.request_id,
        "full_name": c.full_name or "",
        "age": c.age,
        "work_experience": getattr(c, "work_experience", None) or "",
        "contact": c.contact or "",
        "resume_url": getattr(c, "resume_url", None) or "",
        "hunting_date": format_datetime(hunting) if hunting else (format_datetime(c.created_at) if c.created_at else None),
        "interview_date": format_datetime(c.interview_date) if getattr(c, "interview_date", None) else None,
        "decision_date": format_datetime(c.decision_date) if getattr(c, "decision_date", None) else None,
        "status": c.status or "new",
        "result_notes": getattr(c, "result_notes", None) or "",
        "created_at": format_datetime(c.created_at) if c.created_at else None,
        "request_venue": request_venue,
        "request_position": request_position,
    }
