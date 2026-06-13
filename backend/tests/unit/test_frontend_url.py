from unittest.mock import MagicMock

from app.presentation.frontend_url import (
    is_allowed_frontend_origin,
    resolve_frontend_url,
    resolve_invitation_base_url,
)


def test_resolve_frontend_url_uses_x_frontend_url_header():
    request = MagicMock()
    request.headers.get.side_effect = lambda key: {
        "x-frontend-url": "https://abc.ngrok-free.app",
    }.get(key)

    assert resolve_frontend_url(request) == "https://abc.ngrok-free.app"


def test_resolve_frontend_url_falls_back_to_settings():
    request = MagicMock()
    request.headers.get.return_value = None

    assert resolve_frontend_url(request).endswith("4200")


def test_is_allowed_frontend_origin_allows_ngrok():
    assert is_allowed_frontend_origin("https://abc.ngrok-free.app") is True


def test_resolve_invitation_base_url_uses_env_when_configured(monkeypatch):
    monkeypatch.setattr(
        "app.presentation.frontend_url.settings.invitation_base_url",
        "https://exam.midominio.com/",
    )
    monkeypatch.setattr(
        "app.presentation.frontend_url.settings.frontend_url",
        "http://localhost:4200",
    )

    assert resolve_invitation_base_url() == "https://exam.midominio.com"


def test_resolve_invitation_base_url_falls_back_to_frontend_url(monkeypatch):
    monkeypatch.setattr("app.presentation.frontend_url.settings.invitation_base_url", "")
    monkeypatch.setattr(
        "app.presentation.frontend_url.settings.frontend_url",
        "http://localhost:4200",
    )

    assert resolve_invitation_base_url() == "http://localhost:4200"
