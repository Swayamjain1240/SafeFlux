"""Authentication + authorization coverage (Part 2, rule 23).

Covers every required case: signup success/duplicate/invalid-email/weak
password, hash storage (no plaintext), login success/wrong password,
logout, /auth/me authenticated + unauthenticated, expired + tampered
tokens, protected access with/without auth, rate limiting, cookie
hardening, and object-level ownership helpers.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

from app.auth.ownership import ensure_owner, get_owned_or_404
from app.auth.session import SESSION_COOKIE_NAME
from app.auth.tokens import ALGORITHM, ISSUER
from app.database import Base, get_session_factory
from app.models import User

TEST_SECRET = "unit-test-secret-0123456789abcdef0123456789abcdef"

SIGNUP_PATH = "/api/v1/auth/signup"
LOGIN_PATH = "/api/v1/auth/login"
LOGOUT_PATH = "/api/v1/auth/logout"
ME_PATH = "/api/v1/auth/me"

VALID_PASSWORD = "correct-horse-battery-staple"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _signup(client, **overrides):
    payload = {
        "fullName": "Ada Lovelace",
        "email": "ada@example.com",
        "password": VALID_PASSWORD,
    }
    payload.update(overrides)
    return client.post(SIGNUP_PATH, json=payload)


def _login(client, **overrides):
    payload = {"email": "ada@example.com", "password": VALID_PASSWORD}
    payload.update(overrides)
    return client.post(LOGIN_PATH, json=payload)


def _craft_token(user_id: str, *, expired: bool, secret: str = TEST_SECRET) -> str:
    now = datetime.now(timezone.utc)
    if expired:
        issued, expires = now - timedelta(hours=2), now - timedelta(hours=1)
    else:
        issued, expires = now, now + timedelta(minutes=30)
    return jwt.encode(
        {
            "sub": user_id,
            "iat": issued,
            "exp": expires,
            "iss": ISSUER,
            "typ": "session",
        },
        secret,
        algorithm=ALGORITHM,
    )


def _stored_user(email: str = "ada@example.com") -> User | None:
    with get_session_factory()() as db:
        return db.query(User).filter(User.email == email).one_or_none()


# A minimal owned model so object-level authorization is exercised for real.
# Defined at import time so the autouse DB fixture creates its table.
class OwnedResource(Base):
    __tablename__ = "test_owned_resources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)


# --------------------------------------------------------------------------
# signup
# --------------------------------------------------------------------------


def test_signup_creates_account_and_returns_session(client):
    response = _signup(client)

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    user = body["data"]["user"]
    assert user["fullName"] == "Ada Lovelace"
    assert user["email"] == "ada@example.com"
    assert user["id"]

    cookie = response.cookies.get(SESSION_COOKIE_NAME)
    assert cookie  # a session was issued


def test_signup_cookie_is_hardened(client):
    response = _signup(client)

    set_cookie = response.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Path=/" in set_cookie
    # Development runs over http://localhost, so Secure must be absent.
    assert "Secure" not in set_cookie


def test_signup_rejects_duplicate_email_case_insensitively(client):
    assert _signup(client, email="ada@example.com").status_code == 201
    response = _signup(client, email="ADA@Example.com")

    assert response.status_code == 409
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "CONFLICT"


def test_signup_rejects_invalid_email(client):
    response = _signup(client, email="not-an-email")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    # The submitted value must never be echoed back.
    assert "not-an-email" not in response.text


def test_signup_rejects_weak_password(client):
    response = _signup(client, password="short")

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    fields = {detail["field"] for detail in body["error"]["details"]}
    assert "password" in fields
    assert "short" not in response.text


def test_signup_rejects_unknown_fields(client):
    response = _signup(client, isAdmin=True)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_signup_rejects_short_name(client):
    response = _signup(client, fullName="A")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_password_hash_stored_and_plaintext_absent(client):
    _signup(client)

    stored = _stored_user()
    assert stored is not None
    assert stored.password_hash.startswith("$argon2")
    assert VALID_PASSWORD not in stored.password_hash


def test_signup_response_never_exposes_password_hash(client):
    response = _signup(client)

    assert "password" not in response.text.lower()
    assert "$argon2" not in response.text


# --------------------------------------------------------------------------
# login
# --------------------------------------------------------------------------


def test_login_succeeds_with_correct_credentials(client):
    _signup(client)
    response = _login(client)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["user"]["email"] == "ada@example.com"
    assert response.cookies.get(SESSION_COOKIE_NAME)


def test_login_rejects_wrong_password(client):
    _signup(client)
    response = _login(client, password="wrong-password-entirely")

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert body["error"]["message"] == "Invalid email or password."


def test_login_unknown_email_is_indistinguishable(client):
    response = _login(client, email="nobody@example.com")

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password."


# --------------------------------------------------------------------------
# session / me
# --------------------------------------------------------------------------


def test_me_returns_current_user(client):
    _signup(client)
    response = client.get(ME_PATH)

    assert response.status_code == 200
    assert response.json()["data"]["user"]["email"] == "ada@example.com"


def test_me_requires_authentication(client):
    response = client.get(ME_PATH)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_session_alias_matches_me(client):
    _signup(client)
    response = client.get("/api/v1/auth/session")

    assert response.status_code == 200
    assert response.json()["data"]["user"]["email"] == "ada@example.com"


def test_me_rejects_expired_token(client):
    _signup(client)
    stored = _stored_user()
    client.cookies.set(SESSION_COOKIE_NAME, _craft_token(stored.id, expired=True))

    response = client.get(ME_PATH)

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Your session has expired. Please sign in again."


def test_me_rejects_tampered_token(client):
    _signup(client)
    stored = _stored_user()
    client.cookies.set(
        SESSION_COOKIE_NAME,
        _craft_token(stored.id, expired=False, secret="a-completely-different-secret-value"),
    )

    response = client.get(ME_PATH)

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Your session is invalid. Please sign in again."


def test_me_rejects_malformed_token(client):
    client.cookies.set(SESSION_COOKIE_NAME, "not.a.jwt")

    response = client.get(ME_PATH)

    assert response.status_code == 401


def test_me_rejects_token_for_unknown_user(client):
    client.cookies.set(SESSION_COOKIE_NAME, _craft_token("no-such-user-id", expired=False))

    response = client.get(ME_PATH)

    assert response.status_code == 401


def test_logout_clears_session(client):
    _signup(client)
    assert client.get(ME_PATH).status_code == 200

    response = client.post(LOGOUT_PATH)
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Cookie is deleted (empty value) and the session no longer resolves.
    assert client.get(ME_PATH).status_code == 401


# --------------------------------------------------------------------------
# protected endpoint with / without auth
# --------------------------------------------------------------------------


def test_protected_endpoint_requires_auth_then_allows(client):
    # Unauthenticated request is rejected by the backend (authoritative).
    assert client.get(ME_PATH).status_code == 401

    _signup(client)
    assert client.get(ME_PATH).status_code == 200


# --------------------------------------------------------------------------
# rate limiting
# --------------------------------------------------------------------------


def test_login_is_rate_limited(settings_factory, build_client):
    app_client = build_client(
        settings_factory(AUTH_RATE_LIMIT_ATTEMPTS=2, AUTH_RATE_LIMIT_WINDOW_SECONDS=60)
    )
    with app_client:
        first = _login(app_client)
        second = _login(app_client)
        third = _login(app_client)

    assert first.status_code == 401
    assert second.status_code == 401
    assert third.status_code == 429
    body = third.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert "Retry-After" in third.headers


# --------------------------------------------------------------------------
# object-level authorization foundation
# --------------------------------------------------------------------------


def test_get_owned_or_404_returns_owned_resource():
    with get_session_factory()() as db:
        owner = User(
            full_name="Owner",
            email="owner@example.com",
            password_hash="$argon2id$placeholder",
        )
        db.add(owner)
        db.flush()  # populate the server-assigned id before building the FK
        resource = OwnedResource(id="res-1", owner_id=owner.id)
        db.add(resource)
        db.commit()

        loaded = get_owned_or_404(db, OwnedResource, "res-1", owner)
        assert loaded.id == "res-1"


def test_get_owned_or_404_hides_foreign_resource():
    from fastapi import HTTPException

    with get_session_factory()() as db:
        owner = User(
            full_name="Owner",
            email="owner@example.com",
            password_hash="$argon2id$placeholder",
        )
        other = User(
            full_name="Other",
            email="other@example.com",
            password_hash="$argon2id$placeholder",
        )
        db.add_all([owner, other])
        db.commit()
        db.add(OwnedResource(id="res-2", owner_id=owner.id))
        db.commit()

        # A non-owner must not learn the object exists: 404, never 403.
        with pytest.raises(HTTPException) as excinfo:
            get_owned_or_404(db, OwnedResource, "res-2", other)
        assert excinfo.value.status_code == 404

        with pytest.raises(HTTPException) as excinfo:
            get_owned_or_404(db, OwnedResource, "missing", owner)
        assert excinfo.value.status_code == 404


def test_ensure_owner_compares_verified_identity():
    from fastapi import HTTPException

    user = SimpleNamespace(id="user-1")
    owned = SimpleNamespace(owner_id="user-1")
    foreign = SimpleNamespace(owner_id="user-2")

    ensure_owner(owned, user)  # no raise
    with pytest.raises(HTTPException) as excinfo:
        ensure_owner(foreign, user)
    assert excinfo.value.status_code == 404


# --------------------------------------------------------------------------
# request-size guard (rule 6)
# --------------------------------------------------------------------------


def test_oversized_request_body_is_rejected(client):
    huge = "x" * 100_000
    response = client.post(
        SIGNUP_PATH,
        json={"fullName": "Ada", "email": "ada@example.com", "password": huge},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
