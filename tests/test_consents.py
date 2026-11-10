"""SG-10: видача й відкликання згоди; доступ до геосервісу лише за активної згоди."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import AuditLog, ConsentRecord
from app.models.enums import AuditOutcome, ConsentPurpose, DataClassification, RoleCode

URL = "/api/v1/consents"
NEARBY = "/api/v1/shelters/nearby"
HERE = {"latitude": 49.8397, "longitude": 24.0297}


def statuses(client, headers) -> dict[str, str]:
    r = client.get(URL, headers=headers)
    assert r.status_code == 200
    return {c["purpose"]: c["status"] for c in r.json()}


def audit_actions(db) -> list[str]:
    return list(db.scalars(select(AuditLog.action).order_by(AuditLog.id)))


def test_consent_endpoints_require_token(client):
    assert client.get(URL).status_code == 401
    assert client.post(URL, json={"purpose": "ROUTE_GPS"}).status_code == 401
    assert client.delete(f"{URL}/ROUTE_GPS").status_code == 401


def test_nothing_is_granted_by_default(client, make_user, auth):
    assert statuses(client, auth(make_user())) == {
        "ROUTE_GPS": "NOT_GRANTED",
        "REPORT_GEOFENCE": "NOT_GRANTED",
        "SOS": "NOT_GRANTED",
    }


def test_grant_is_granular_and_audited(client, make_user, auth, db):
    user = make_user()
    headers = auth(user)
    r = client.post(URL, json={"purpose": "ROUTE_GPS"}, headers=headers)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "ACTIVE"
    assert body["policy_version"] == "1.0"
    assert body["granted_at"] is not None and body["revoked_at"] is None
    # Згода на одну ціль не поширюється на інші
    assert statuses(client, headers) == {
        "ROUTE_GPS": "ACTIVE",
        "REPORT_GEOFENCE": "NOT_GRANTED",
        "SOS": "NOT_GRANTED",
    }
    entry = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).one()
    assert entry.action == "CONSENT_GRANTED"
    assert entry.outcome == AuditOutcome.SUCCESS
    assert entry.actor_user_id == user.id
    assert entry.data_classification == DataClassification.SENSITIVE
    assert entry.details["purpose"] == "ROUTE_GPS"


def test_repeated_grant_is_idempotent(client, make_user, auth, db):
    user = make_user()
    headers = auth(user)
    first = client.post(URL, json={"purpose": "SOS"}, headers=headers)
    again = client.post(URL, json={"purpose": "SOS"}, headers=headers)
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json()["granted_at"] == first.json()["granted_at"]
    assert (
        db.scalars(select(ConsentRecord).where(ConsentRecord.user_id == user.id)).all().__len__()
        == 1
    )
    assert audit_actions(db).count("CONSENT_GRANTED") == 1


def test_unknown_purpose_is_rejected(client, make_user, auth):
    r = client.post(URL, json={"purpose": "MARKETING"}, headers=auth(make_user()))
    assert r.status_code == 422


def test_revoke_keeps_history_and_allows_regrant(client, make_user, auth, db):
    user = make_user()
    headers = auth(user)
    client.post(URL, json={"purpose": "ROUTE_GPS"}, headers=headers)

    r = client.delete(f"{URL}/ROUTE_GPS", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "REVOKED"
    assert r.json()["revoked_at"] is not None
    assert statuses(client, headers)["ROUTE_GPS"] == "REVOKED"

    assert client.post(URL, json={"purpose": "ROUTE_GPS"}, headers=headers).status_code == 201
    assert statuses(client, headers)["ROUTE_GPS"] == "ACTIVE"

    records = db.scalars(select(ConsentRecord).where(ConsentRecord.user_id == user.id)).all()
    assert len(records) == 2  # відкликаний запис не видалено
    assert sum(r.revoked_at is None for r in records) == 1
    assert [a for a in audit_actions(db) if a.startswith("CONSENT")] == [
        "CONSENT_GRANTED",
        "CONSENT_REVOKED",
        "CONSENT_GRANTED",
    ]


def test_revoke_without_active_consent_is_404(client, make_user, auth):
    r = client.delete(f"{URL}/SOS", headers=auth(make_user()))
    assert r.status_code == 404
    assert r.json()["error"] == "CONSENT_NOT_ACTIVE"


def test_users_manage_only_their_own_consents(client, make_user, auth):
    alice, bob = make_user(), make_user()
    client.post(URL, json={"purpose": "ROUTE_GPS"}, headers=auth(alice))
    assert statuses(client, auth(bob))["ROUTE_GPS"] == "NOT_GRANTED"
    assert client.delete(f"{URL}/ROUTE_GPS", headers=auth(bob)).status_code == 404
    assert statuses(client, auth(alice))["ROUTE_GPS"] == "ACTIVE"


def test_expired_consent_is_not_active_and_can_be_renewed(client, make_user, auth, db):
    user = make_user()
    past = datetime.now(UTC) - timedelta(days=2)
    db.add(
        ConsentRecord(
            user_id=user.id,
            purpose=ConsentPurpose.ROUTE_GPS,
            policy_version="0.9",
            granted_at=past,
            expires_at=past + timedelta(days=1),
        )
    )
    db.flush()
    headers = auth(user)
    assert statuses(client, headers)["ROUTE_GPS"] == "EXPIRED"
    assert client.post(NEARBY, json=HERE, headers=headers).status_code == 403
    assert client.post(URL, json={"purpose": "ROUTE_GPS"}, headers=headers).status_code == 201
    assert statuses(client, headers)["ROUTE_GPS"] == "ACTIVE"


# ---------- геосервіс за згодою (TC-05) ----------


def test_nearby_without_token_is_401(client):
    assert client.post(NEARBY, json=HERE).status_code == 401


def test_nearby_without_consent_is_403_with_audit(client, make_user, make_shelter, auth, db):
    make_shelter()
    user = make_user()
    r = client.post(NEARBY, json=HERE, headers=auth(user))
    assert r.status_code == 403
    body = r.json()
    assert body["error"] == "DENIED_403_CONSENT"
    assert body["required_consent"] == "ROUTE_GPS"
    assert "features" not in body
    entry = db.get(AuditLog, body["audit_entry_id"])
    assert entry.action == "DENIED_403_CONSENT"
    assert entry.outcome == AuditOutcome.DENIED
    assert entry.actor_user_id == user.id
    assert entry.details["purpose"] == "ROUTE_GPS"


def test_consent_for_another_purpose_does_not_unlock_nearby(client, make_user, auth):
    headers = auth(make_user())
    client.post(URL, json={"purpose": "SOS"}, headers=headers)
    assert client.post(NEARBY, json=HERE, headers=headers).status_code == 403


def test_nearby_with_consent_sorts_by_distance(client, make_user, make_shelter, auth, db):
    near = make_shelter(lat="49.840000", lon="24.030000")  # ≈ 40 м
    mid = make_shelter(lat="49.848700", lon="24.029700")  # ≈ 1 км на північ
    kyiv = make_shelter(lat="50.450000", lon="30.520000")
    closed = make_shelter(lat="49.839700", lon="24.029700", current_status="CLOSED")
    headers = auth(make_user())
    client.post(URL, json={"purpose": "ROUTE_GPS"}, headers=headers)

    r = client.post(NEARBY, json={**HERE, "limit": 2}, headers=headers)
    assert r.status_code == 200
    features = r.json()["features"]
    assert [f["id"] for f in features] == [str(near.id), str(mid.id)]
    assert 30 < features[0]["properties"]["distance_m"] < 50
    assert 990 < features[1]["properties"]["distance_m"] < 1010
    assert features[0]["properties"]["walk_minutes"] == 1
    assert str(kyiv.id) not in r.text and str(closed.id) not in r.text

    everything = client.post(
        NEARBY, json={**HERE, "only_open": False, "limit": 20}, headers=headers
    )
    assert everything.json()["features"][0]["id"] == str(closed.id)

    # У журналі — факт пошуку, але не координати користувача
    entry = db.scalars(
        select(AuditLog).where(AuditLog.action == "SHELTER_NEARBY_SEARCH").limit(1)
    ).one()
    assert "49.8397" not in str(entry.details) and "24.0297" not in str(entry.details)


def test_revoking_consent_blocks_nearby_immediately(client, make_user, make_shelter, auth):
    make_shelter()
    headers = auth(make_user())
    client.post(URL, json={"purpose": "ROUTE_GPS"}, headers=headers)
    assert client.post(NEARBY, json=HERE, headers=headers).status_code == 200
    client.delete(f"{URL}/ROUTE_GPS", headers=headers)
    assert client.post(NEARBY, json=HERE, headers=headers).status_code == 403


def test_auditor_is_denied_by_role_before_consent_is_checked(client, make_user, auth):
    r = client.post(NEARBY, json=HERE, headers=auth(make_user(RoleCode.SECURITY_AUDITOR)))
    assert r.status_code == 403
    assert r.json()["error"] == "DENIED_403_RBAC"


def test_nearby_validates_coordinates(client, make_user, auth):
    headers = auth(make_user())
    client.post(URL, json={"purpose": "ROUTE_GPS"}, headers=headers)
    r = client.post(NEARBY, json={"latitude": 120, "longitude": 24}, headers=headers)
    assert r.status_code == 422
