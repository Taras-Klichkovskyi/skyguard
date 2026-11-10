"""SG-10: JWT із роллю, 401 без токена."""

from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import ACCESS, create_token, decode_token
from app.models import AuditLog
from app.models.enums import AuditOutcome, RoleCode
from tests.conftest import PASSWORD

ME = "/api/v1/auth/me"


def last_audit(db) -> AuditLog:
    return db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).one()


def test_register_creates_citizen_and_never_returns_password(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "Olena@Example.com", "password": "long-enough-pass", "full_name": "Олена"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "CITIZEN"
    assert "password" not in str(body)


def test_register_cannot_choose_role(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "x@example.com", "password": "long-enough-pass", "role": "DSNS_OPERATOR"},
    )
    assert r.json()["role"] == "CITIZEN"


def test_register_duplicate_email_is_case_insensitive(client, make_user):
    make_user(email="taken@example.com")
    r = client.post(
        "/api/v1/auth/register", json={"email": "TAKEN@example.com", "password": "long-enough-pass"}
    )
    assert r.status_code == 409
    assert r.json()["error"] == "EMAIL_TAKEN"


def test_register_validates_input(client):
    r = client.post("/api/v1/auth/register", json={"email": "not-an-email", "password": "short"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "VALIDATION_ERROR"
    assert {d["field"] for d in body["details"]} == {"email", "password"}


def test_login_returns_jwt_with_role(client, make_user):
    user = make_user(RoleCode.DSNS_OPERATOR)
    r = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["role"] == "DSNS_OPERATOR"
    assert body["expires_in"] == 15 * 60
    payload = decode_token(body["access_token"], ACCESS)
    assert payload["role"] == "DSNS_OPERATOR"
    assert payload["sub"] == user.id


def test_login_wrong_password_and_unknown_email_look_the_same(client, make_user, db):
    user = make_user()
    wrong = client.post("/api/v1/auth/login", json={"email": user.email, "password": "nope-nope"})
    unknown = client.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": PASSWORD}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"] == unknown.json()["error"] == "DENIED_401_AUTH"
    assert wrong.json()["reason"] == unknown.json()["reason"] == "bad_credentials"
    entry = last_audit(db)
    assert entry.outcome == AuditOutcome.DENIED
    assert "ghost@example.com" not in str(entry.details)  # email у журнал не пишемо


def test_login_blocked_for_deactivated_user(client, make_user):
    user = make_user(is_active=False)
    r = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.status_code == 401


def test_me_returns_current_user(client, make_user, auth):
    user = make_user(RoleCode.VERIFIED_VOLUNTEER)
    r = client.get(ME, headers=auth(user))
    assert r.status_code == 200
    assert r.json() == {
        "id": str(user.id),
        "email": user.email,
        "full_name": None,
        "role": "VERIFIED_VOLUNTEER",
        "assigned_shelter_id": None,
    }


def test_no_token_gives_401_and_audit_record(client, db):
    r = client.get(ME)
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"
    body = r.json()
    assert body["error"] == "DENIED_401_AUTH"
    assert body["reason"] == "token_missing"
    assert body["request_id"] == r.headers["X-Request-ID"]
    entry = db.get(AuditLog, body["audit_entry_id"])
    assert entry.action == "DENIED_401_AUTH"
    assert entry.outcome == AuditOutcome.DENIED
    assert entry.http_status == 401
    assert entry.actor_role == RoleCode.ANONYMOUS
    assert entry.request_id == body["request_id"]
    assert entry.details["path"] == ME
    assert len(entry.ip_hash) == 64 and "testclient" not in entry.ip_hash


def test_garbage_token_gives_401(client):
    r = client.get(ME, headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401
    assert r.json()["reason"] == "token_invalid"


def test_token_signed_with_other_key_gives_401(client, make_user):
    user = make_user()
    forged = jwt.encode(
        {
            "sub": str(user.id),
            "role": "DSNS_OPERATOR",
            "type": "access",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        "attacker-key-attacker-key-attacker-key",
        algorithm="HS256",
    )
    r = client.get(ME, headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401
    assert r.json()["reason"] == "token_invalid"


def test_expired_token_gives_401(client, make_user):
    user = make_user()
    settings = get_settings()
    expired = jwt.encode(
        {
            "sub": str(user.id),
            "role": "CITIZEN",
            "type": "access",
            "exp": datetime.now(UTC) - timedelta(seconds=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    r = client.get(ME, headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401
    assert r.json()["reason"] == "token_expired"


def test_refresh_token_is_not_accepted_as_access_token(client, make_user):
    user = make_user()
    tokens = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}
    ).json()
    r = client.get(ME, headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert r.status_code == 401
    assert r.json()["reason"] == "token_wrong_type"


def test_refresh_issues_new_pair_and_rejects_access_token(client, make_user):
    user = make_user()
    tokens = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}
    ).json()
    ok = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert ok.status_code == 200
    assert (
        client.get(ME, headers={"Authorization": f"Bearer {ok.json()['access_token']}"}).status_code
        == 200
    )
    bad = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert bad.status_code == 401


def test_token_of_deactivated_user_stops_working(client, make_user, auth, db):
    user = make_user()
    headers = auth(user)
    user.is_active = False
    db.flush()
    r = client.get(ME, headers=headers)
    assert r.status_code == 401
    assert r.json()["reason"] == "user_inactive"


def test_role_change_applies_to_already_issued_token(client, make_user, db):
    """Роль беремо з БД: понижений користувач не зберігає права до кінця життя токена."""
    user = make_user(RoleCode.DSNS_OPERATOR)
    token, _ = create_token(user.id, "DSNS_OPERATOR", ACCESS)
    user.role_id = 1  # CITIZEN
    db.flush()
    db.expire(user)
    r = client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert r.json()["role"] == "CITIZEN"


def test_unknown_path_uses_common_error_format(client):
    r = client.get("/api/v1/nope")
    assert r.status_code == 404
    assert r.json()["error"] == "NOT_FOUND"
    assert r.json()["request_id"] == r.headers["X-Request-ID"]
