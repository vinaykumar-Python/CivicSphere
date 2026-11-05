from collections import defaultdict
import logging
from threading import Lock
from time import monotonic
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import register_citizen, verify_password
from app.dependencies import get_db
from app.email_service import (
    EmailDeliveryError,
    email_delivery_configured,
    send_verification_email,
)
from app.email_verification import (
    MAX_CODE_ATTEMPTS,
    allow_immediate_resend,
    can_resend,
    create_verification_code,
    get_pending_verification,
    is_expired,
    matches_code,
    resend_seconds_remaining,
)
from app.models import EmailVerification, User
from app.schemas.auth import RegisterRequest
from app.schemas.email_verification import (
    EmailAddressRequest,
    VerifyEmailRequest,
)
from app.security import create_access_token


logger = logging.getLogger("civiccare.auth")

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


# --------------------------------------------------
# LOGIN RATE LIMITING
# --------------------------------------------------

MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 15 * 60

login_attempts = defaultdict(list)
login_attempts_lock = Lock()


def get_client_ip(request: Request) -> str:
    if request.client:
        return request.client.host
    return "unknown"


def check_login_rate_limit(client_ip: str):
    current_time = monotonic()

    with login_attempts_lock:
        attempts = login_attempts[client_ip]

        attempts[:] = [
            attempt
            for attempt in attempts
            if current_time - attempt < LOGIN_WINDOW_SECONDS
        ]

        if len(attempts) >= MAX_LOGIN_ATTEMPTS:
            retry_after = max(
                1,
                int(LOGIN_WINDOW_SECONDS - (current_time - attempts[0]))
            )

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )


def record_failed_login(client_ip: str):
    current_time = monotonic()

    with login_attempts_lock:
        attempts = login_attempts[client_ip]

        attempts[:] = [
            attempt
            for attempt in attempts
            if current_time - attempt < LOGIN_WINDOW_SECONDS
        ]

        attempts.append(current_time)

        expired_ips = [
            ip for ip, values in login_attempts.items()
            if not values
        ]

        for ip in expired_ips:
            login_attempts.pop(ip, None)


def clear_failed_logins(client_ip: str):
    with login_attempts_lock:
        login_attempts.pop(client_ip, None)


# --------------------------------------------------
# CITIZEN REGISTRATION
# --------------------------------------------------

@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    email = str(data.email).strip().lower()
    existing_user = db.scalar(
        select(User.id).where(User.email == email)
    )
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    if not email_delivery_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Email verification is not configured. Please contact the "
                "CivicCare administrator before creating an account."
            ),
        )

    try:
        user = register_citizen(data, db)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from None

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from None

    except Exception:
        db.rollback()
        raise

    code = create_verification_code(db, user)
    try:
        send_verification_email(user.email, code)
    except EmailDeliveryError as exc:
        pending = db.get(EmailVerification, user.id)
        if pending is not None:
            allow_immediate_resend(db, pending)
        logger.error("Verification email delivery failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Your account was created, but the verification email could "
                "not be sent. Please request a new code."
            ),
        ) from exc

    return {
        "message": "A verification code has been sent to your email address.",
        "email": user.email,
    }


@router.post("/verify-email")
def verify_email(
    data: VerifyEmailRequest,
    db: Session = Depends(get_db),
):
    email = str(data.email).strip().lower()
    pending = get_pending_verification(db, email)

    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The verification code is invalid or expired.",
        )

    user, verification = pending
    now = datetime.now(timezone.utc)

    if is_expired(verification, now):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The verification code is invalid or expired.",
        )

    if verification.attempts >= MAX_CODE_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many incorrect codes. Request a new code and try again.",
        )

    if not matches_code(user, verification, data.code):
        verification.attempts += 1
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The verification code is incorrect.",
        )

    db.delete(verification)
    db.commit()
    return {"message": "Email verified. You can now sign in."}


@router.post("/resend-verification")
def resend_verification(
    data: EmailAddressRequest,
    db: Session = Depends(get_db),
):
    email = str(data.email).strip().lower()
    pending = get_pending_verification(db, email)

    if pending is None:
        return {
            "message": "If this account needs verification, a new code will be sent."
        }

    user, verification = pending
    now = datetime.now(timezone.utc)

    if not can_resend(verification, now):
        retry_after = resend_seconds_remaining(verification, now)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {retry_after} seconds before requesting another code.",
        )

    code = create_verification_code(db, user)
    try:
        send_verification_email(user.email, code)
    except EmailDeliveryError as exc:
        pending = db.get(EmailVerification, user.id)
        if pending is not None:
            allow_immediate_resend(db, pending)
        logger.error("Verification email delivery failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The verification email could not be sent. Please try again later.",
        ) from exc

    return {
        "message": "If this account needs verification, a new code will be sent."
    }


# --------------------------------------------------
# USER LOGIN
# --------------------------------------------------

@router.post("/login")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    client_ip = get_client_ip(request)

    check_login_rate_limit(client_ip)

    email = form_data.username.strip().lower()

    user = db.scalar(
        select(User).where(User.email == email)
    )

    if not user or not verify_password(
        form_data.password,
        user.password_hash if user else "",
    ):
        record_failed_login(client_ip)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive.",
        )

    pending_verification = db.get(EmailVerification, user.id)
    if pending_verification is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email address before signing in.",
        )

    clear_failed_logins(client_ip)

    token = create_access_token(
        user.id,
        user.role,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 1800,
    }