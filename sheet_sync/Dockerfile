FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV PYTHONPATH=/app

COPY db ./db
COPY utils ./utils
COPY integrations ./integrations

COPY sheet_sync/requirements.txt sheet_sync/requirements.txt
RUN pip install -r sheet_sync/requirements.txt

COPY sheet_sync ./sheet_sync

ENV DATABASE_URL=sqlite:///./data/bot.db
RUN mkdir -p /app/data

CMD ["sh", "-c", "PYTHONPATH=/app exec python -m sheet_sync.run"]
