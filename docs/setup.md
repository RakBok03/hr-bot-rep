# Подготовка проекта к запуску

Документ описывает полный путь подготовки окружения и запуск сервисов.

## 1) Требования

- Docker + Docker Compose
- Доступ к Telegram
- SMTP для отправки кода регистрации
- Google Cloud + Google Sheets для синхронизации кандидатов

## 2) Подготовка `.env`

Скопируйте пример:

```bash
cp .env.example .env
```

Далее заполните переменные из `.env` по разделам ниже.

## 3) Telegram

### 3.1) `BOT_TOKEN`

1. Откройте `@BotFather`.
2. Создайте бота командой `/newbot`.
3. Скопируйте токен и укажите в `.env`:

```text
BOT_TOKEN=123456:ABC-DEF...
```

### 3.2) `HR_CHAT_ID` (куда бот пишет о всех заявках и изменениях)

1. Создайте группу/супергруппу (или используйте существующую).
2. Добавьте бота в чат и дайте право **отправлять сообщения**.
3. Получите `chat_id` (ID чата):
   - напишите в этом чате боту команду `/get_id` и возьмите значение **ID чата**, либо
   - добавьте `@RawDataBot` в этот чат и посмотрите поле `chat.id`.
4. Укажите в `.env`:

```text
HR_CHAT_ID=-1001234567890
```

### 3.3) `ADMIN_TG_IDS`

Список Telegram user id админов через запятую. Узнать свой user id можно командой `/get_id` в личном чате с ботом.

```text
ADMIN_TG_IDS=123456789,987654321
```

## 4) Регистрация пользователей

### 4.1) `ALLOWED_EMAIL_DOMAINS`

Ограничивает регистрацию корпоративными доменами. Доступ к боту будет осуществляться только при наличии корпоративной почты. 

Пример:

```text
ALLOWED_EMAIL_DOMAINS=example.com,company.com
```

## 5) SMTP (отправка кода подтверждения)

### 5.1) Режимы

- `SMTP=true` — бот отправляет код подтверждения на email.
- `SMTP=false` — режим без SMTP (ТОЛЬКО для тестов): бот принимает только код `1111`.

### 5.2) Переменные

```text
SMTP=true|false
SMTP_HOST=...
SMTP_PORT=...
SMTP_USER=...
SMTP_PASSWORD=...
MAIL_FROM=...
```

Что именно нужно указать и где это брать:

1. `SMTP_HOST` — SMTP-сервер (outgoing mail) вашего почтового провайдера.
   - Обычно это значение видно в настройках домена/почты в панели провайдера (раздел `SMTP`, `Outgoing mail`, `Relay`).
   - Для Gmail/Google Workspace и многих корпоративных почт это стандартные адреса (см. пример в `5.3`).

2. `SMTP_PORT` — порт SMTP.
   - В коде перед логином выполняется `STARTTLS`, поэтому в типовых случаях используйте порт `587`.
   - Если у провайдера другой порт — проверьте, что на нём действительно поддерживается `STARTTLS`.

3. `SMTP_USER` — логин для SMTP-аутентификации.
   - Чаще всего это полный email адрес (например `hr-bot@company.com`).
   - Иногда можно/нужно создать отдельного SMTP-пользователя (это обычно безопаснее, чем использовать главный аккаунт).

4. `SMTP_PASSWORD` — пароль для SMTP-аутентификации.
   - Для почт с 2FA часто требуется не обычный пароль, а **App password** (или SMTP-token в админ-панели).
   - Для Gmail/Google Workspace это как раз `App passwords` (см. пример ниже в `5.3`).

5. `MAIL_FROM` — адрес в заголовке `From:` при отправке письма.
   - Обычно он должен совпадать с `SMTP_USER` (или как минимум быть почтовым адресом, которому провайдер разрешает отправку).

### 5.3) Пример (Gmail / Google Workspace)

```text
SMTP=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=hr-bot@company.com
SMTP_PASSWORD=...  # пароль приложения (App password), если включена 2FA
MAIL_FROM=hr-bot@company.com
```

## 6) Google Sheets и синхронизация кандидатов

Синхронизация использует сервисный аккаунт Google.

### 6.1) Сервисный аккаунт и ключ

1. Откройте Google Cloud Console и создайте проект (или выберите существующий):
   - https://console.cloud.google.com/projectcreate
2. Включите API:
   - **Google Sheets API**: https://console.cloud.google.com/apis/library/sheets.googleapis.com
   - (опционально) **Google Drive API**: https://console.cloud.google.com/apis/library/drive.googleapis.com
3. Создайте **Service Account**:
   - https://console.cloud.google.com/iam-admin/serviceaccounts/create
4. Скачайте **JSON‑ключ** для сервисного аккаунта:
   - откройте сервисный аккаунт → вкладка **Keys** → **Add key** → **Create new key** → **JSON**
   - прямой раздел ключей: https://console.cloud.google.com/iam-admin/serviceaccounts
5. Положите скачанный файл в репозиторий (пример):
   - создайте папку `credentials/` в корне проекта (рядом с `.env`)
   - сохраните ключ как `credentials/google-service.json`

```text
./credentials/google-service.json
```

### 6.2) Таблица

В репозитории есть пример шаблона таблицы: `docs/examples/HR база данных.xlsx`.
Его можно загрузить в Google Drive и открыть как Google Spreadsheet.

1. Создайте Google Spreadsheet:
   - https://docs.google.com/spreadsheets/u/0/
   - **Blank spreadsheet** → задайте название, например **HR Task Bot**
2. Создайте лист (вкладку) **«Кандидаты»** (ровно так, как написано). Если лист уже есть — переименуйте.
3. Поделитесь таблицей с сервисным аккаунтом:
   - откройте таблицу → кнопка **Share** → вставьте email сервисного аккаунта из JSON (поле `client_email`)
   - выставьте права **Editor** → **Send**
4. Скопируйте `spreadsheet_id` из URL.
   Пример URL:
   - `https://docs.google.com/spreadsheets/d/1abcDEFgHiJkLmNoPqRsTuVwXyZ1234567890/edit#gid=0`
   Здесь `spreadsheet_id` = `1abcDEFgHiJkLmNoPqRsTuVwXyZ1234567890`.

### 6.3) `.env`

```text
GOOGLE_CREDENTIALS_PATH=./credentials/google-service.json
GOOGLE_SPREADSHEET_ID=1abc...xyz
```

### 6.4) Лист “Кандидаты”

- Таблица должна содержать лист **«Кандидаты»** (имя по умолчанию).
- `sheet_sync` читает лист, создаёт/обновляет кандидатов в БД и уведомляет владельца заявки в Telegram.

## 7) `WEBAPP_URL`

Переменная указывает публичный HTTPS‑URL WebApp, который открывается внутри Telegram.

Что нужно:
1. Доменное имя (пример: `hr-taskbot.company.com`) — именно его Telegram должен открывать по HTTPS.
2. DNS-запись типа `A` для вашего домена (или поддомена) — она должна указывать на **публичный IPv4** вашего сервера.
   - В панели домена создайте запись `A`: `hr-taskbot.company.com` → `IP_ВАШЕГО_СЕРВЕРА`
   - Если у сервера есть IPv6, дополнительно можно создать `AAAA`.

Дальше поднимаем HTTPS:
- Вариант A: обычный **Nginx**
  - Nginx принимает запросы на `https://ваш-домен` и проксирует их на `webapp` (порт `8000`).
  - Сертификат получаем через **Let’s Encrypt**.
- Вариант B: **Nginx Proxy Manager (NPM)**
  - В интерфейсе NPM добавьте “Proxy Host”.
  - Укажите домен, схему `http` и целевой адрес/порт для `webapp` (обычно `webapp:8000` или `127.0.0.1:8000`).
  - Включите “SSL” / “Force SSL” и выберите сертификат **Let’s Encrypt**.

После того как домен доступен по HTTPS, пропишите в `.env` публичный адрес:

```text
WEBAPP_URL=https://your-domain.example
```

## 8) Запуск (Docker Compose)

```bash
docker compose up -d --build
```

Сервисы:
- `bot` — Telegram bot (polling)
- `webapp` — WebApp на `:8000`
- `sheet_sync` — синхронизация Google Sheets → DB

