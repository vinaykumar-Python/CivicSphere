import os
import smtplib
import ssl
from email.message import EmailMessage


class EmailDeliveryError(RuntimeError):
    pass


def email_delivery_configured() -> bool:
    host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    port_value = os.getenv("SMTP_PORT", "587").strip()
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").replace(" ", "")
    sender = os.getenv("SMTP_FROM_EMAIL", username).strip()

    if not host or not username or not password or not sender:
        return False

    try:
        port = int(port_value)
    except ValueError:
        return False

    return 1 <= port <= 65535


def send_verification_email(recipient: str, code: str) -> None:
    host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    port_value = os.getenv("SMTP_PORT", "587").strip()
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").replace(" ", "")
    sender = os.getenv("SMTP_FROM_EMAIL", username).strip()

    if not email_delivery_configured():
        raise EmailDeliveryError(
            "Email delivery is not configured. Set SMTP_USERNAME, "
            "SMTP_PASSWORD, and SMTP_FROM_EMAIL."
        )

    port = int(port_value)

    message = EmailMessage()
    message["Subject"] = "Your CivicCare verification code"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "Use this code to verify your CivicCare email address:\n\n"
        f"{code}\n\n"
        "This code expires in 10 minutes. If you did not create an account, "
        "you can ignore this message."
    )

    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(username, password)
            refused = smtp.send_message(message)
            if refused:
                raise EmailDeliveryError(
                    "The email server did not accept the recipient address."
                )
    except EmailDeliveryError:
        raise
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError(
            "The verification email could not be sent. Check the SMTP settings."
        ) from exc
