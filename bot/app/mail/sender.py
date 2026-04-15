import smtplib
from email.mime.text import MIMEText

from app.config import get_settings


def send_verification_email(to: str, code: str) -> bool:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_password:
        return False

    msg = MIMEText(f"Код подтверждения регистрации в HR-боте: {code}\n\nВведите его в чат с ботом.")
    msg["Subject"] = "Код подтверждения — HR Bot"
    msg["From"] = settings.mail_from or settings.smtp_user
    msg["To"] = to

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        return True
    except Exception:
        return False
