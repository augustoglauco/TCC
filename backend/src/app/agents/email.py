"""Envio de e-mail ao administrador por SMTP (R13).

# MVP: SMTP simples (smtplib numa thread), sem fila, reenvio nem HTML —
# o resultado do envio fica em `mensagens_agentes.email_status`.
"""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.config import Settings

logger = logging.getLogger("assistente.agents.email")


def email_configurado(settings: Settings) -> bool:
    return bool(settings.smtp_host and settings.admin_alert_email)


def _enviar_sync(settings: Settings, assunto: str, corpo: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = settings.smtp_from or settings.smtp_user or settings.admin_alert_email
    msg["To"] = settings.admin_alert_email
    msg.set_content(corpo)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)


async def enviar_email_admin(settings: Settings, assunto: str, corpo: str) -> str:
    """Devolve o `email_status`: `enviado`, `nao_configurado` ou `falhou`."""
    if not email_configurado(settings):
        return "nao_configurado"
    try:
        await asyncio.to_thread(_enviar_sync, settings, assunto, corpo)
        return "enviado"
    except Exception:  # noqa: BLE001 - e-mail nunca pode quebrar o agente
        logger.exception("Falha ao enviar e-mail de alerta ao administrador")
        return "falhou"
