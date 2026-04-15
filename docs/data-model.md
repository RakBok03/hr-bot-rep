# Модель данных (таблицы и связи)

Файл описывает структуру БД и связи между таблицами.

## Форматы дат

- `Request.start_date` хранится строкой в формате **`dd.mm.yyyy`**
- при отсутствии значения в форме может храниться как строка `—`
- `created_at/closed_at` и поля дат кандидатов — `datetime`
- В JSON-ответах API эти даты форматируются функциями проекта:
  - `format_date(...)` → `dd.mm.yyyy`
  - `format_datetime(...)` → `dd.mm.yyyy HH:MM`
  - пустые значения → строка `—`

## Таблицы

### `users` — пользователи

| Поле | Тип | Примечание |
|---|---|---|
| `id` | int | PK |
| `tg_id` | int | Telegram user id, UNIQUE |
| `full_name` | str | имя из Telegram |
| `username` | str\|null | `@username` |
| `email` | str\|null | корпоративная почта после регистрации, UNIQUE |
| `role` | str | `hr`\|`admin`\|`employee`\|`unknown` |

Пример:

```json
{
  "id": 3,
  "tg_id": 123456789,
  "full_name": "Иванов Иван",
  "username": "ivanov",
  "email": "ivanov@company.com",
  "role": "employee"
}
```

### `requests` — заявки на подбор

| Поле | Тип | Примечание |
|---|---|---|
| `id` | int | PK |
| `status` | str | `new`\|`in_progress`\|`closed`\|`cancelled` |
| `created_at` | datetime | дата создания |
| `closed_at` | datetime\|null | дата закрытия/отмены |
| `result_notes` | str\|null | комментарий при закрытии |
| `venue` | str | площадка |
| `position` | str | должность |
| `headcount` | int | количество человек |
| `schedule` | str | график |
| `salary` | str | оклад/ставка (строкой) |
| `employment_type` | str | вид оформления |
| `requirements` | str | требования/обязанности |
| `start_date` | str | **`dd.mm.yyyy`** |
| `contact` | str | контактное лицо |
| `work_time` | str\|null | время работы |
| `requires_candidate_approval` | bool | нужно ли согласование кандидатов |
| `owner_id` | int\|null | FK → `users.id` (автор заявки) |

Пример:

```json
{
  "id": 5,
  "status": "new",
  "created_at": "2026-03-09T16:56:52Z",
  "closed_at": null,
  "result_notes": null,
  "venue": "LOFT #4",
  "position": "Кондитер",
  "headcount": 1,
  "schedule": "2/2",
  "salary": "120 000",
  "employment_type": "ТК",
  "requirements": "Опыт от 1 года",
  "start_date": "11.03.2026",
  "contact": "Владислав @cas220",
  "work_time": "09:00–18:00",
  "requires_candidate_approval": true,
  "owner_id": 3
}
```

### `candidates` — кандидаты

| Поле | Тип | Примечание |
|---|---|---|
| `id` | int | PK |
| `request_id` | int\|null | FK → `requests.id` |
| `full_name` | str | ФИО |
| `age` | int\|null | возраст |
| `work_experience` | str\|null | опыт |
| `contact` | str | телефон/контакт |
| `resume_url` | str\|null | ссылка |
| `hunting_date` | datetime\|null | дата “в подборе” |
| `interview_date` | datetime\|null | дата собеседования |
| `decision_date` | datetime\|null | дата решения |
| `status` | str | фактические значения приходят из источников (WebApp/Sheet) |
| `result_notes` | str\|null | комментарий/результат |
| `created_at` | datetime | дата создания записи |
| `sheet_row_index` | int\|null | строка в Google Sheet “Кандидаты” |
| `approval_notified_at` | datetime\|null | когда отправили согласование |
| `approval_decided_at` | datetime\|null | когда приняли решение по согласованию |
| `interview_feedback_notified_at` | datetime\|null | когда отправили запрос ОС по собесу |
| `interview_feedback_decided_at` | datetime\|null | когда зафиксировали ОС |

Пример:

```json
{
  "id": 8,
  "request_id": 5,
  "full_name": "Иванов Иван Иванович",
  "age": 30,
  "work_experience": "10",
  "contact": "8908875356",
  "resume_url": "https://natribu.org/",
  "hunting_date": "2026-03-06T00:00:00Z",
  "interview_date": "2026-03-09T00:00:00Z",
  "decision_date": null,
  "status": "Собес",
  "result_notes": "",
  "created_at": "2026-03-09T16:58:23Z",
  "sheet_row_index": 11,
  "approval_notified_at": null,
  "approval_decided_at": null,
  "interview_feedback_notified_at": "2026-03-09T16:58:31Z",
  "interview_feedback_decided_at": null
}
```

## Связи между таблицами

Кардинальности:

- `users (1) ── (N) requests` через `requests.owner_id`
- `requests (1) ── (N) candidates` через `candidates.request_id`

Схема:

```text
users.id 1 ──── * requests.owner_id
requests.id 1 ──── * candidates.request_id
```

