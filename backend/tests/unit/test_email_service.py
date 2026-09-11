from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.infrastructure.services.email_service import (
    MailtrapEmailService,
    build_exam_invitation_content,
    format_invitation_datetime,
    get_email_service,
)


def test_build_exam_invitation_content_includes_schedule():
    starts_at = datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc)
    closes_at = datetime(2026, 9, 15, 16, 30, tzinfo=timezone.utc)

    subject, text, html = build_exam_invitation_content(
        "Matemáticas",
        "https://app.test/exam/take/abc",
        "simulation",
        starts_at=starts_at,
        closes_at=closes_at,
    )

    assert subject == "Invitación al examen: Matemáticas"
    assert "Matemáticas" in text
    assert "Simulacro" in text
    assert "Inicio:" in text
    assert "Finalización:" in text
    assert format_invitation_datetime(starts_at) in text
    assert format_invitation_datetime(closes_at) in html
    assert "https://app.test/exam/take/abc" in html


def test_format_invitation_datetime_converts_to_colombia():
    value = datetime(2026, 9, 15, 19, 0, tzinfo=timezone.utc)
    assert format_invitation_datetime(value) == "15/09/2026 14:00 (hora Colombia)"


@pytest.mark.asyncio
async def test_mailtrap_email_service_sends_invitation():
    service = MailtrapEmailService()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "ok"

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    starts_at = datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc)
    closes_at = datetime(2026, 9, 15, 16, 30, tzinfo=timezone.utc)

    with patch("app.infrastructure.services.email_service.httpx.AsyncClient", return_value=mock_client):
        with patch("app.infrastructure.services.email_service.settings") as mock_settings:
            mock_settings.mailtrap_api_token = "test-token"
            mock_settings.mailtrap_api_url = "https://send.api.mailtrap.io/api/send"
            mock_settings.mailtrap_from_email = "hello@demomailtrap.com"
            mock_settings.mailtrap_from_name = "Examen App"
            mock_settings.mailtrap_category = "Examen App"

            sent = await service.send_exam_invitation(
                "aimer.rivera@are-soluciones.com",
                "Examen demo",
                "https://app.test/exam/take/token",
                "real",
                starts_at=starts_at,
                closes_at=closes_at,
            )

    assert sent is True
    mock_client.post.assert_awaited_once()
    call_kwargs = mock_client.post.await_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer test-token"
    payload = call_kwargs["json"]
    assert payload["from"]["email"] == "hello@demomailtrap.com"
    assert payload["to"] == [{"email": "aimer.rivera@are-soluciones.com"}]
    assert payload["category"] == "Examen App"
    assert "Examen demo" in payload["subject"]
    assert format_invitation_datetime(starts_at) in payload["text"]
    assert format_invitation_datetime(closes_at) in payload["html"]


@pytest.mark.asyncio
async def test_mailtrap_email_service_returns_false_without_token():
    service = MailtrapEmailService()

    with patch("app.infrastructure.services.email_service.settings") as mock_settings:
        mock_settings.mailtrap_api_token = ""

        sent = await service.send_exam_invitation(
            "aimer.rivera@are-soluciones.com",
            "Examen demo",
            "https://app.test/exam/take/token",
            "real",
        )

    assert sent is False


@pytest.mark.asyncio
async def test_mailtrap_email_service_handles_http_error():
    service = MailtrapEmailService()
    request = httpx.Request("POST", "https://send.api.mailtrap.io/api/send")
    response = httpx.Response(401, request=request, text="Unauthorized")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        side_effect=httpx.HTTPStatusError("Unauthorized", request=request, response=response)
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.infrastructure.services.email_service.httpx.AsyncClient", return_value=mock_client):
        with patch("app.infrastructure.services.email_service.settings") as mock_settings:
            mock_settings.mailtrap_api_token = "bad-token"
            mock_settings.mailtrap_api_url = "https://send.api.mailtrap.io/api/send"
            mock_settings.mailtrap_from_email = "hello@demomailtrap.com"
            mock_settings.mailtrap_from_name = "Examen App"
            mock_settings.mailtrap_category = "Examen App"

            sent = await service.send_exam_invitation(
                "aimer.rivera@are-soluciones.com",
                "Examen demo",
                "https://app.test/exam/take/token",
                "real",
            )

    assert sent is False


def test_get_email_service_selects_mailtrap():
    with patch("app.infrastructure.services.email_service.settings") as mock_settings:
        mock_settings.email_provider = "mailtrap"
        mock_settings.smtp_host = "localhost"

        service = get_email_service()

    assert isinstance(service, MailtrapEmailService)
