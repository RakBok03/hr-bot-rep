# Сборка из корня репозитория: docker build -f bot/Dockerfile .
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY db ./db
RUN pip install ./db

COPY utils ./utils
COPY integrations ./integrations

COPY bot/requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY bot/app ./app

RUN mkdir -p /app/data
ENV DATABASE_URL=sqlite:///./data/bot.db

CMD ["python", "-m", "app.main"]

