"""Minimal transactional email sender (currently just password reset).

Uses plain ``smtplib`` against whatever relay is configured via ``.env``. If
no SMTP host is configured — the default, so local dev works with zero mail
infrastructure — the email is never silently dropped: its content is logged
instead, so a developer can still complete the flow (copy the reset link out
of the server log) without a mail server on hand. Delivery failures are
caught and logged rather than raised, so a flaky mail relay can never turn
into a 500 on an auth endpoint.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger("email")


def send_email(to: str, subject: str, body: str) -> bool:
    """Returns True if actually handed to an SMTP server, False if only logged."""
    if not settings.smtp_host:
        logger.info("SMTP not configured — email to %s logged instead of sent.\nSubject: %s\n%s",
                    to, subject, body)
        return False

    msg = EmailMessage()
    msg["From"] = settings.smtp_from or settings.smtp_user or "no-reply@credit-yetu.local"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001 — email delivery must never break the request
        logger.warning("Failed to send email to %s: %s", to, exc)
        return False
