import re
from urllib.parse import urlparse

from fastapi import Request

from app.config import settings

_NGROK_ORIGIN_PATTERN = re.compile(r"^https://.*\.ngrok(-free)?\.(app|dev)$")


def _normalize_origin(url: str) -> str:
    return url.rstrip("/")


def _allowed_origins() -> set[str]:
    origins = {
        _normalize_origin(settings.frontend_url),
        *(_normalize_origin(origin) for origin in settings.cors_origins.split(",") if origin.strip()),
    }
    return origins


def is_allowed_frontend_origin(origin: str) -> bool:
    normalized = _normalize_origin(origin)
    if normalized in _allowed_origins():
        return True
    return settings.cors_allow_ngrok and bool(_NGROK_ORIGIN_PATTERN.match(normalized))


def resolve_frontend_url(request: Request | None = None) -> str:
    if request is not None:
        custom = request.headers.get("x-frontend-url")
        if custom and is_allowed_frontend_origin(custom):
            return _normalize_origin(custom)

        origin = request.headers.get("origin")
        if origin and is_allowed_frontend_origin(origin):
            return _normalize_origin(origin)

        referer = request.headers.get("referer")
        if referer:
            parsed = urlparse(referer)
            if parsed.scheme and parsed.netloc:
                referer_origin = _normalize_origin(f"{parsed.scheme}://{parsed.netloc}")
                if is_allowed_frontend_origin(referer_origin):
                    return referer_origin

    return _normalize_origin(settings.frontend_url)


def resolve_invitation_base_url() -> str:
    configured = (settings.invitation_base_url or "").strip()
    if configured:
        return _normalize_origin(configured)
    return _normalize_origin(settings.frontend_url)
