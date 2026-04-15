import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from db.session import ensure_database

from app.api.routes import router as api_router
from random import randint

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="HR Bot WebApp")


@app.on_event("startup")
def _ensure_db() -> None:
    ensure_database()

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(api_router)
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    static_version = os.environ.get("APP_STATIC_VERSION") or str(randint(1, 999))
    return templates.TemplateResponse(
        "index.html", {"request": request, "static_version": static_version}
    )
