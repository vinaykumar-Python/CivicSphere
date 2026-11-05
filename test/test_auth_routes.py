from datetime import timedelta

import pytest

from app.models import EmailVerification, User


@pytest.fixture
def email_sender(monkeypatch):
    sent = []

    def send(email, code):
        sent.append((email, code))

    monkeypatch.setattr("app.routes.send_verification_email", send)
    monkeypatch.setattr("app.routes.email_delivery_configured", lambda: True)
    return sent


def test_citizen_registration_success(client_for_user, email_sender):
    client = client_for_user()

    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Test Citizen",
            "email": "newcitizen@example.com",
            "password": "SecurePass123",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "newcitizen@example.com"
    assert "verification code" in response.json()["message"].lower()
    assert email_sender[0][0] == "newcitizen@example.com"
    assert len(email_sender[0][1]) == 6


def test_registration_does_not_create_account_without_mail_configuration(
    client_for_user,
    test_database,
    monkeypatch,
):
    db, _ = test_database
    client = client_for_user()
    monkeypatch.setattr("app.routes.email_delivery_configured", lambda: False)

    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Unconfigured Citizen",
            "email": "unconfigured@example.com",
            "password": "SecurePass123",
        },
    )

    assert response.status_code == 503
    assert "Email verification is not configured" in response.json()["detail"]
    assert db.query(User).filter_by(
        email="unconfigured@example.com"
    ).one_or_none() is None


def test_registration_requires_email_verification(
    client_for_user,
    email_sender,
    test_database,
):
    db, _ = test_database
    client = client_for_user()

    registration = client.post(
        "/api/auth/register",
        json={
            "full_name": "Verify Citizen",
            "email": "verify@example.com",
            "password": "SecurePass123",
        },
    )

    user = db.query(User).filter_by(email="verify@example.com").one()
    assert user.is_active is True
    assert db.get(EmailVerification, user.id) is not None

    login = client.post(
        "/api/auth/login",
        data={
            "username": "verify@example.com",
            "password": "SecurePass123",
        },
    )
    assert login.status_code == 403
    assert "verify your email" in login.json()["detail"].lower()

    verified = client.post(
        "/api/auth/verify-email",
        json={
            "email": "verify@example.com",
            "code": email_sender[-1][1],
        },
    )
    assert verified.status_code == 200
    assert db.get(EmailVerification, user.id) is None

    login_after_verification = client.post(
        "/api/auth/login",
        data={
            "username": "verify@example.com",
            "password": "SecurePass123",
        },
    )
    assert login_after_verification.status_code == 200


def test_verification_limits_attempts_and_supports_resend(
    client_for_user,
    email_sender,
    test_database,
):
    db, _ = test_database
    client = client_for_user()

    client.post(
        "/api/auth/register",
        json={
            "full_name": "Code Citizen",
            "email": "code@example.com",
            "password": "SecurePass123",
        },
    )

    incorrect_code = f"{(int(email_sender[-1][1]) + 1) % 1_000_000:06d}"
    for _ in range(5):
        response = client.post(
            "/api/auth/verify-email",
            json={"email": "code@example.com", "code": incorrect_code},
        )
        assert response.status_code == 400

    locked = client.post(
        "/api/auth/verify-email",
        json={
            "email": "code@example.com",
            "code": email_sender[-1][1],
        },
    )
    assert locked.status_code == 429

    user = db.query(User).filter_by(email="code@example.com").one()
    verification = db.get(EmailVerification, user.id)
    verification.sent_at -= timedelta(minutes=2)
    db.commit()

    resent = client.post(
        "/api/auth/resend-verification",
        json={"email": "code@example.com"},
    )
    assert resent.status_code == 200
    assert len(email_sender) == 2

    verified = client.post(
        "/api/auth/verify-email",
        json={
            "email": "code@example.com",
            "code": email_sender[-1][1],
        },
    )
    assert verified.status_code == 200


def test_duplicate_email_registration_rejected(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user()

    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Another Citizen",
            "email": data["citizen_one"].email,
            "password": "SecurePass123",
        },
    )

    assert response.status_code == 409


def test_registration_rejects_short_password(client_for_user):
    client = client_for_user()

    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Test Citizen",
            "email": "shortpass@example.com",
            "password": "123",
        },
    )

    assert response.status_code == 422


def test_registration_rejects_whitespace_name(client_for_user):
    client = client_for_user()

    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "   ",
            "email": "whitespace@example.com",
            "password": "SecurePass123",
        },
    )

    assert response.status_code == 422


def test_registration_rejects_whitespace_password(client_for_user):
    client = client_for_user()

    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Test Citizen",
            "email": "spaces@example.com",
            "password": "        ",
        },
    )

    assert response.status_code == 422


def test_login_success(client_for_user, email_sender):
    client = client_for_user()

    registration = client.post(
        "/api/auth/register",
        json={
            "full_name": "Login Citizen",
            "email": "login@example.com",
            "password": "SecurePass123",
        },
    )

    assert registration.status_code == 201

    verification = client.post(
        "/api/auth/verify-email",
        json={
            "email": "login@example.com",
            "code": email_sender[-1][1],
        },
    )
    assert verification.status_code == 200

    response = client.post(
        "/api/auth/login",
        data={
            "username": "login@example.com",
            "password": "SecurePass123",
        },
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["expires_in"] == 1800
    assert response.json()["access_token"]


def test_login_rejects_wrong_password(client_for_user, email_sender):
    client = client_for_user()

    client.post(
        "/api/auth/register",
        json={
            "full_name": "Login Citizen",
            "email": "wrongpass@example.com",
            "password": "SecurePass123",
        },
    )

    response = client.post(
        "/api/auth/login",
        data={
            "username": "wrongpass@example.com",
            "password": "IncorrectPass123",
        },
    )

    assert response.status_code == 401


def test_login_rejects_inactive_user(
    client_for_user,
    test_database,
):
    db, data = test_database
    user = data["citizen_one"]

    client = client_for_user()

    from app.auth import hash_password

    user.password_hash = hash_password("SecurePass123")
    user.is_active = False
    db.commit()

    response = client.post(
        "/api/auth/login",
        data={
            "username": user.email,
            "password": "SecurePass123",
        },
    )

    assert response.status_code == 403
