import asyncio
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Optional
from pydantic import BaseModel, EmailStr
from .common import ActionResult

logger = logging.getLogger("execution-sandbox")


class SendEmailParams(BaseModel):
    to: Optional[EmailStr] = None   # None = use account's own registered email (DEFAULT_NOTIFY_EMAIL)
    subject: str
    body: str


def _send_smtp_sync(to_addr: str, subject: str, body: str) -> None:
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")
    username = os.getenv("SMTP_USERNAME", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_name = os.getenv("SMTP_FROM_NAME", "NL-Automation Platform")
    from_email = os.getenv("SMTP_FROM_EMAIL", username)

    msg = MIMEMultipart()
    msg["From"] = formataddr((from_name, from_email))
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    server = smtplib.SMTP(host, port, timeout=15)
    try:
        server.ehlo()
        if use_tls:
            server.starttls()
            server.ehlo()
        if username and password:
            server.login(username, password)
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:
            pass


async def send_email(params: SendEmailParams) -> ActionResult:
    host = os.getenv("SMTP_HOST", "").strip()
    username = os.getenv("SMTP_USERNAME", "").strip()

    # Determine recipient
    recipient = params.to
    if not recipient:
        fallback = os.getenv("DEFAULT_NOTIFY_EMAIL", "").strip() or username
        if fallback:
            recipient = fallback

    if not recipient:
        return ActionResult(
            success=False,
            error="Recipient email not specified and DEFAULT_NOTIFY_EMAIL is not set",
            message="Email sending failed: missing recipient address"
        )

    # Check if SMTP configured
    if not host or not username:
        logger.warning("SMTP is not configured (SMTP_HOST or SMTP_USERNAME is empty)")
        return ActionResult(
            success=False,
            error="email not configured: SMTP_HOST and SMTP_USERNAME must be set in environment",
            message="Email sending failed: SMTP not configured"
        )

    try:
        await asyncio.to_thread(_send_smtp_sync, str(recipient), params.subject, params.body)
        logger.info(f"Email successfully delivered to {recipient} via {host}:{os.getenv('SMTP_PORT', '587')}")
        return ActionResult(
            success=True,
            data={"to": str(recipient), "subject": params.subject, "host": host},
            message=f"Email sent successfully to {recipient}"
        )
    except Exception as e:
        logger.error(f"SMTP delivery failed: {e}", exc_info=True)
        return ActionResult(
            success=False,
            error=str(e),
            message=f"SMTP transmission failed: {e}"
        )
