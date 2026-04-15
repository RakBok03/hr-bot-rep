# Сборка из корня репозитория: docker build -f webApp/Dockerfile .
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY db ./db
RUN pip install ./db

COPY utils ./utils

COPY integrations ./integrations

COPY webApp/requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY webApp/app ./app

RUN mkdir -p /app/data
ENV DATABASE_URL=sqlite:///./data/bot.db

CMD ["uvicorn", "app.api.webapp:app", "--host", "0.0.0.0", "--port", "8000"]
