"""Клиент для записи данных в Google Таблицы (заявки, кандидаты)."""
from __future__ import annotations

import logging

from integrations.config import GoogleSheetsConfig

logger = logging.getLogger(__name__)

CANDIDATES_FIRST_ROW = 3
CANDIDATES_COL_L_1BASED = 12  # L: "Отправить"|"Отправленно"|"Ожидание"
COL_IDX_REQUEST_ID = 0   # A
COL_IDX_FULL_NAME = 1    # B
COL_IDX_AGE = 2          # C
COL_IDX_WORK_EXPERIENCE = 3  # D
COL_IDX_CONTACT = 4      # E
COL_IDX_RESUME_URL = 5   # F
COL_IDX_HUNTING_DATE = 6    # G
COL_IDX_INTERVIEW_DATE = 7   # H
COL_IDX_DECISION_DATE = 8    # I
COL_IDX_STATUS = 9       # J
COL_IDX_RESULT_NOTES = 10    # K
CANDIDATES_COL_ID_1BASED = 13  # M — не пишем; при отсутствии sheet_row_index строку ищем по M (обратная совместимость)


def _cell_int(cells: list, idx: int):
    """Приведение ячейки к int (для request_id и т.п.). Google может вернуть 1.0 или '1'."""
    if idx >= len(cells):
        return None
    val = cells[idx]
    if val is None:
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val) if val == int(val) else None
    s = str(val).strip()
    if not s:
        return None
    try:
        return int(float(s.replace(",", ".")))
    except (ValueError, TypeError):
        return None


class GoogleSheetsClient:
    """Синхронный клиент: добавление строк в листы заявок и кандидатов."""

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    def __init__(self, config: GoogleSheetsConfig | None = None) -> None:
        self._config = config or GoogleSheetsConfig()
        self._client = None
        self._spreadsheet = None

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        if not self._config.is_configured:
            raise RuntimeError(
                "Google Sheets не настроен: задайте GOOGLE_CREDENTIALS_PATH и GOOGLE_SPREADSHEET_ID"
            )
        import gspread
        from google.oauth2.service_account import Credentials

        creds = Credentials.from_service_account_file(
            self._config.credentials_path,
            scopes=self.SCOPES,
        )
        self._client = gspread.authorize(creds)
        self._spreadsheet = self._client.open_by_key(self._config.spreadsheet_id)

    def _worksheet(self, sheet_name: str):
        self._ensure_client()
        return self._spreadsheet.worksheet(sheet_name)

    def append_row(self, sheet_name: str, values: list) -> bool:
        ws = self._worksheet(sheet_name)
        ws.append_row(values, value_input_option="USER_ENTERED")
        return True

    def append_request_row(self, values: list) -> bool:
        return self.append_row(self._config.sheet_requests, values)

    def append_candidate_row(self, values: list) -> bool:
        return self.append_row(self._config.sheet_candidates, values)

    def update_request_on_close(
        self,
        request_id: int,
        status_display: str,
        closed_at: str,
        result_notes: str,
    ) -> bool:
        """Обновить строку заявки при закрытии/отмене: B=status, O=closed_at, P=result_notes."""
        ws = self._worksheet(self._config.sheet_requests)
        col_a = ws.col_values(1)
        row_index = None
        for i, val in enumerate(col_a):
            try:
                if int(val) == request_id:
                    row_index = i + 1
                    break
            except (TypeError, ValueError):
                if val == str(request_id):
                    row_index = i + 1
                    break
        if row_index is None:
            return False
        ws.update_acell(f"B{row_index}", status_display)
        ws.update_acell(f"O{row_index}", closed_at)
        ws.update_acell(f"P{row_index}", result_notes)
        return True

    def update_request_on_edit(
        self,
        request_id: int,
        status_display: str,
        venue: str,
        position: str,
        headcount: int,
        schedule: str,
        work_time: str,
        salary: str,
        employment_type: str,
        requirements: str,
        start_date: str,
        contact: str,
        candidate_approval_display: str,
    ) -> bool:
        """Обновить строку заявки при редактировании: B..M (как при создании)."""
        ws = self._worksheet(self._config.sheet_requests)
        col_a = ws.col_values(1)
        row_index = None
        for i, val in enumerate(col_a):
            try:
                if int(val) == request_id:
                    row_index = i + 1
                    break
            except (TypeError, ValueError):
                if val == str(request_id):
                    row_index = i + 1
                    break
        if row_index is None:
            return False
        range_b_m = f"B{row_index}:M{row_index}"
        values = [
            [
                status_display,
                venue,
                position,
                headcount,
                schedule,
                work_time or "",
                salary,
                employment_type,
                requirements,
                start_date,
                contact,
                candidate_approval_display,
            ]
        ]
        ws.update(range_b_m, values, value_input_option="USER_ENTERED")
        return True

    def fetch_new_candidates_from_sheet(self) -> list[tuple[int, dict]]:
        """
        Читает лист «Кандидаты» с 3-й строки.
        Строки где L = «Отправить» считаются новыми кандидатами на отправку.
        После взятия в работу L меняется на «Отправленно».
        Поддерживается обратная совместимость: ИСТИНА/TRUE также воспринимаются как «Отправить».
        """
        ws = self._worksheet(self._config.sheet_candidates)
        col_l = ws.col_values(CANDIDATES_COL_L_1BASED)
        first_idx = CANDIDATES_FIRST_ROW - 1
        if first_idx >= len(col_l):
            return []
        new_vals = ("отправить", "истина", "true")
        rows_to_process = []
        for i in range(first_idx, len(col_l)):
            v = col_l[i]
            if isinstance(v, bool) and v:
                rows_to_process.append(i + 1)
            elif isinstance(v, str) and v.strip().lower() in new_vals:
                rows_to_process.append(i + 1)
        out = []
        for row_index in rows_to_process:
            raw = ws.get(f"A{row_index}:L{row_index}")
            if not raw or not raw[0]:
                continue
            cells = (raw[0] + [""] * 12)[:12]
            request_id = _cell_int(cells, COL_IDX_REQUEST_ID)
            full_name = (cells[COL_IDX_FULL_NAME] or "").strip() if len(cells) > COL_IDX_FULL_NAME else ""
            contact = (cells[COL_IDX_CONTACT] or "").strip() if len(cells) > COL_IDX_CONTACT else ""
            age = _cell_int(cells, COL_IDX_AGE)
            work_experience = (cells[COL_IDX_WORK_EXPERIENCE] or "").strip() if len(cells) > COL_IDX_WORK_EXPERIENCE else None
            resume_url = (cells[COL_IDX_RESUME_URL] or "").strip() if len(cells) > COL_IDX_RESUME_URL else None
            status = (cells[COL_IDX_STATUS] or "").strip() if len(cells) > COL_IDX_STATUS else "new"
            result_notes = (cells[COL_IDX_RESULT_NOTES] or "").strip() if len(cells) > COL_IDX_RESULT_NOTES else None
            hunting_date_raw = cells[COL_IDX_HUNTING_DATE] if len(cells) > COL_IDX_HUNTING_DATE else None
            interview_date_raw = cells[COL_IDX_INTERVIEW_DATE] if len(cells) > COL_IDX_INTERVIEW_DATE else None
            decision_date_raw = cells[COL_IDX_DECISION_DATE] if len(cells) > COL_IDX_DECISION_DATE else None
            logger.info(
                "Кандидаты строка %s: A(request_id)=%r -> %s, B(full_name)=%r",
                row_index, cells[COL_IDX_REQUEST_ID] if len(cells) > COL_IDX_REQUEST_ID else None, request_id, full_name
            )
            if not full_name:
                continue
            ws.update_acell(f"L{row_index}", "Отправленно")
            out.append((
                row_index,
                {
                    "request_id": request_id,
                    "full_name": full_name,
                    "contact": contact or "—",
                    "age": age,
                    "work_experience": work_experience,
                    "resume_url": resume_url,
                    "hunting_date": hunting_date_raw,
                    "interview_date": interview_date_raw,
                    "decision_date": decision_date_raw,
                    "status": status or "new",
                    "result_notes": result_notes,
                },
            ))
        return out

    def update_candidate_sheet_row_id(self, row_index: int, candidate_id: int) -> bool:
        """Раньше записывал id в колонку M; по требованию в M ничего не пишем."""
        return True

    def update_candidate_decision(
        self,
        candidate_id: int,
        decision_date: str,
        status: str,
        result_notes: str | None = None,
        row_index: int | None = None,
        request_id: int | None = None,
        full_name: str | None = None,
    ) -> bool:
        """Обновить I=decision_date, J=status, при наличии K=result_notes. Строка: row_index или поиск по колонке M (id)."""
        ws = self._worksheet(self._config.sheet_candidates)
        if row_index is not None:
            r = row_index
        else:
            col_m = ws.col_values(CANDIDATES_COL_ID_1BASED)
            r = None
            for i, val in enumerate(col_m):
                try:
                    if int(float(str(val).strip())) == candidate_id:
                        r = i + 1
                        break
                except (TypeError, ValueError):
                    continue
            if r is None:
                r = self._find_candidate_row_by_request_and_name(ws, request_id, full_name)
            if r is None:
                return False
        ws.update_acell(f"I{r}", decision_date)
        ws.update_acell(f"J{r}", status)
        if result_notes is not None:
            ws.update_acell(f"K{r}", result_notes)
        return True

    def update_candidate_interview(
        self,
        candidate_id: int,
        interview_date: str,
        row_index: int | None = None,
        request_id: int | None = None,
        full_name: str | None = None,
    ) -> bool:
        """Обновить H=interview_date. Строка: row_index или поиск по колонке M (id)."""
        ws = self._worksheet(self._config.sheet_candidates)
        if row_index is not None:
            r = row_index
        else:
            col_m = ws.col_values(CANDIDATES_COL_ID_1BASED)
            r = None
            for i, val in enumerate(col_m):
                try:
                    if int(float(str(val).strip())) == candidate_id:
                        r = i + 1
                        break
                except (TypeError, ValueError):
                    continue
            if r is None:
                r = self._find_candidate_row_by_request_and_name(ws, request_id, full_name)
            if r is None:
                return False
        ws.update_acell(f"H{r}", interview_date)
        return True

    def update_candidate_send_flag(
        self,
        candidate_id: int,
        send_flag: str,
        row_index: int | None = None,
        request_id: int | None = None,
        full_name: str | None = None,
    ) -> bool:
        """Обновить L=флаг отправки (например, «Ожидание»)."""
        ws = self._worksheet(self._config.sheet_candidates)
        if row_index is not None:
            r = row_index
        else:
            col_m = ws.col_values(CANDIDATES_COL_ID_1BASED)
            r = None
            for i, val in enumerate(col_m):
                try:
                    if int(float(str(val).strip())) == candidate_id:
                        r = i + 1
                        break
                except (TypeError, ValueError):
                    continue
            if r is None:
                r = self._find_candidate_row_by_request_and_name(ws, request_id, full_name)
            if r is None:
                return False
        ws.update_acell(f"L{r}", send_flag)
        return True

    def _find_candidate_row_by_request_and_name(
        self,
        ws,
        request_id: int | None,
        full_name: str | None,
    ) -> int | None:
        """Fallback-поиск строки кандидата по A=request_id и B=full_name."""
        if request_id is None or not (full_name or "").strip():
            return None
        values = ws.get(f"A{CANDIDATES_FIRST_ROW}:B")
        target_name = (full_name or "").strip().lower()
        for idx, row in enumerate(values, start=CANDIDATES_FIRST_ROW):
            if not row:
                continue
            a = row[0] if len(row) > 0 else ""
            b = row[1] if len(row) > 1 else ""
            try:
                a_id = int(float(str(a).strip()))
            except (TypeError, ValueError):
                continue
            if a_id == request_id and (str(b).strip().lower() == target_name):
                return idx
        return None

    def is_available(self) -> bool:
        if not self._config.is_configured:
            return False
        try:
            self._ensure_client()
            return True
        except Exception:
            return False
