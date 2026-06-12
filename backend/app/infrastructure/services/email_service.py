import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from app.config import settings
from app.domain.services import EmailService

logger = logging.getLogger(__name__)


def _mask_token(token: str) -> str:
    if not token:
        return "(vacío)"
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


def log_email_configuration() -> None:
    provider = settings.email_provider.lower().strip()
    logger.info("Configuración de correo: provider=%s", provider)
    if provider == "mailtrap":
        logger.info(
            "Mailtrap: url=%s from=%s <%s> token=%s",
            settings.mailtrap_api_url,
            settings.mailtrap_from_name,
            settings.mailtrap_from_email,
            _mask_token(settings.mailtrap_api_token),
        )
    elif provider == "smtp":
        logger.info(
            "SMTP: host=%s port=%s from=%s user=%s",
            settings.smtp_host,
            settings.smtp_port,
            settings.smtp_from,
            settings.smtp_user or "(sin autenticación)",
        )
    else:
        logger.info("Proveedor mock: no se envían correos reales")


def build_exam_invitation_content(
    exam_title: str, invite_link: str, mode: str
) -> tuple[str, str, str]:
    mode_label = "Simulacro" if mode == "simulation" else "Prueba real"
    subject = f"Invitación al examen: {exam_title}"
    text = (
        f"Has sido invitado a un examen.\n\n"
        f"Examen: {exam_title}\n"
        f"Modo: {mode_label}\n\n"
        f"Accede con el siguiente enlace:\n{invite_link}"
    )
    html = f"""
    <html>
    <body>
        <h2>Has sido invitado a un examen</h2>
        <p><strong>Examen:</strong> {exam_title}</p>
        <p><strong>Modo:</strong> {mode_label}</p>
        <p>Haz clic en el siguiente enlace para acceder:</p>
        <p><a href="{invite_link}">{invite_link}</a></p>
    </body>
    </html>
    """
    return subject, text, html


class SmtpEmailService(EmailService):
    async def send_exam_invitation(
        self, to_email: str, exam_title: str, invite_link: str, mode: str
    ) -> bool:
        subject, _, html = build_exam_invitation_content(exam_title, invite_link, mode)
        logger.info(
            "Enviando invitación SMTP: to=%s exam=%s host=%s:%s",
            to_email,
            exam_title,
            settings.smtp_host,
            settings.smtp_port,
        )
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.smtp_from
            msg["To"] = to_email
            msg.attach(MIMEText(html, "html"))
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                if settings.smtp_user:
                    server.starttls()
                    server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(settings.smtp_from, to_email, msg.as_string())
            logger.info("Invitación SMTP enviada correctamente a %s", to_email)
            return True
        except Exception as e:
            logger.error("Error SMTP al enviar a %s: %s", to_email, e, exc_info=True)
            return False


class MailtrapEmailService(EmailService):
    async def send_exam_invitation(
        self, to_email: str, exam_title: str, invite_link: str, mode: str
    ) -> bool:
        if not settings.mailtrap_api_token:
            logger.error(
                "MAILTRAP_API_TOKEN no configurado. Define la variable en backend/.env"
            )
            return False

        subject, text, html = build_exam_invitation_content(exam_title, invite_link, mode)
        payload = {
            "from": {
                "email": settings.mailtrap_from_email,
                "name": settings.mailtrap_from_name,
            },
            "to": [{"email": to_email}],
            "subject": subject,
            "text": text,
            "html": html,
            "category": settings.mailtrap_category,
        }

        logger.info(
            "Enviando invitación Mailtrap: to=%s exam=%s from=%s url=%s",
            to_email,
            exam_title,
            settings.mailtrap_from_email,
            settings.mailtrap_api_url,
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    settings.mailtrap_api_url,
                    headers={
                        "Authorization": f"Bearer {settings.mailtrap_api_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                logger.info(
                    "Respuesta Mailtrap: status=%s body=%s",
                    response.status_code,
                    response.text[:500],
                )
                response.raise_for_status()
            logger.info("Invitación Mailtrap enviada correctamente a %s", to_email)
            return True
        except httpx.HTTPStatusError as e:
            logger.error(
                "Mailtrap rechazó el envío a %s: HTTP %s — %s",
                to_email,
                e.response.status_code,
                e.response.text,
            )
            return False
        except Exception as e:
            logger.error(
                "Error inesperado Mailtrap al enviar a %s: %s",
                to_email,
                e,
                exc_info=True,
            )
            return False


class MockEmailService(EmailService):
    sent_emails: list[dict] = []

    async def send_exam_invitation(
        self, to_email: str, exam_title: str, invite_link: str, mode: str
    ) -> bool:
        logger.info("Mock email: to=%s exam=%s link=%s", to_email, exam_title, invite_link)
        self.sent_emails.append(
            {"to": to_email, "title": exam_title, "link": invite_link, "mode": mode}
        )
        return True


def get_email_service() -> EmailService:
    provider = settings.email_provider.lower().strip()
    if provider == "mailtrap":
        logger.debug("Seleccionado proveedor Mailtrap")
        return MailtrapEmailService()
    if provider == "mock" or settings.smtp_host == "mock":
        logger.debug("Seleccionado proveedor Mock")
        return MockEmailService()
    logger.debug("Seleccionado proveedor SMTP")
    return SmtpEmailService()
