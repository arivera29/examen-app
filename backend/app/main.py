import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.infrastructure.database.models import init_db
from app.infrastructure.services.email_service import log_email_configuration
from app.presentation.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

app = FastAPI(title=settings.app_name, version="1.0.0")

_cors_origins = {
    origin.strip()
    for origin in settings.cors_origins.split(",")
    if origin.strip()
}
_cors_origins.add(settings.frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(_cors_origins),
    allow_origin_regex=(
        r"https://.*\.ngrok(-free)?\.(app|dev)" if settings.cors_allow_ngrok else None
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

app.include_router(router, prefix="/api/v1")


@app.on_event("startup")
def startup():
    log_email_configuration()
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}
