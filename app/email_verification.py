import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EmailVerification, User
from app.security import JWT_SECRET_KEY

CODE_LENGTH = 6
CODE_LIFETIME = timedelta(minutes=10)
RESEND_INTERVAL = timedelta(seconds=60)
MAX_CODE_ATTEMPTS = 5


def _hash_code(email: str, code: str) -> str:
    message = f"{email}:{code}".encode("utf-8")
    return hmac.new(
        JWT_SECRET_KEY.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def create_verification_code(
    db: Session,
    user: User,
) -> str:
    code = f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"
    now = datetime.now(timezone.utc)
    verification = db.get(EmailVerification, user.id)

    if verification is None:
        verification = EmailVerification(
            user_id=user.id,
            code_hash=_hash_code(user.email, code),
            expires_at=now + CODE_LIFETIME,
            sent_at=now,
            attempts=0,
        )
        db.add(verification)
    else:
        verification.code_hash = _hash_code(user.email, code)
        verification.expires_at = now + CODE_LIFETIME
        verification.sent_at = now
        verification.attempts = 0

    db.commit()
    return code


def allow_immediate_resend(
    db: Session,
    verification: EmailVerification,
) -> None:
    verification.sent_at = datetime.now(timezone.utc) - RESEND_INTERVAL
    db.commit()


def get_pending_verification(
    db: Session,
    email: str,
) -> tuple[User, EmailVerification] | None:
    result = db.execute(
        select(User, EmailVerification)
        .join(EmailVerification, EmailVerification.user_id == User.id)
        .where(User.email == email)
        .with_for_update()
    ).one_or_none()

    return result


def can_resend(verification: EmailVerification, now: datetime) -> bool:
    return now - _utc(verification.sent_at) >= RESEND_INTERVAL


def resend_seconds_remaining(
    verification: EmailVerification,
    now: datetime,
) -> int:
    remaining = RESEND_INTERVAL - (now - _utc(verification.sent_at))
    return max(1, int(remaining.total_seconds()))


def is_expired(verification: EmailVerification, now: datetime) -> bool:
    return now >= _utc(verification.expires_at)


def matches_code(user: User, verification: EmailVerification, code: str) -> bool:
    expected = _hash_code(user.email, code)
    return hmac.compare_digest(verification.code_hash, expected)
