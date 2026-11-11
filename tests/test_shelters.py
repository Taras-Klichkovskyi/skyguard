"""SG-10: публічний реєстр укриттів без автентифікації, 403 при відсутності прав."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.models import AuditLog
from app.models.enums import AuditOutcome, DataClassification, RoleCode, ShelterStatus

URL = "/api/v1/shelters"


def audit_count(db) -> int:
    return db.scalar(select(func.count()).select_from(AuditLog))


# ---------- публічний реєстр ----------


def test_registry_is_public_geojson(client, make_shelter):
    s = make_shelter(lat="49.841000", lon="24.031500", current_occupancy=30, has_water=True)
    r = client.get(URL)  # без токена
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "FeatureCollection"
    feature = next(f for f in body["features"] if f["id"] == str(s.id))
    assert feature["type"] == "Feature"
    # RFC 7946: [довгота, широта]
    assert feature["geometry"] == {"type": "Point", "coordinates": [24.0315, 49.841]}
    props = feature["properties"]
    assert props["status"] == "OPEN"
    assert props["free_places"] == 70
    assert props["resources"] == {
        "ramp": False,
        "generator": False,
        "starlink": False,
        "water": True,
    }


def test_registry_never_exposes_commander_contacts(client, make_shelter):
    s = make_shelter(commander_name="Іван Петренко", commander_phone="+380501234567")
    listing = client.get(URL).text
    single = client.get(f"{URL}/{s.id}").text
    for text in (listing, single):
        assert "Петренко" not in text
        assert "+380501234567" not in text
        assert "commander" not in text


def test_public_read_is_not_audited(client, make_shelter, db):
    make_shelter()
    before = audit_count(db)
    client.get(URL)
    assert audit_count(db) == before


def test_registry_filters(client, make_shelter):
    inside = make_shelter(lat="49.840000", lon="24.030000", is_accessible=True)
    closed = make_shelter(lat="49.840500", lon="24.030500", current_status=ShelterStatus.CLOSED)
    far = make_shelter(lat="50.450000", lon="30.520000", is_accessible=True)  # Київ
    hidden = make_shelter(is_active=False)

    def ids(params):
        r = client.get(URL, params=params)
        assert r.status_code == 200
        return {f["id"] for f in r.json()["features"]}

    lviv = ids({"bbox": "23.9,49.78,24.1,49.9"})
    assert {str(inside.id), str(closed.id)} <= lviv
    assert str(far.id) not in lviv
    assert str(hidden.id) not in ids({})
    assert str(closed.id) not in ids({"status": "OPEN"})
    assert str(closed.id) not in ids({"ramp": "true"})
    assert {str(inside.id), str(far.id)} <= ids({"ramp": "true"})


def test_registry_rejects_bad_bbox(client):
    for bbox in ("1,2,3", "a,b,c,d", "24.1,49.9,23.9,49.78", "0,0,0,95"):
        r = client.get(URL, params={"bbox": bbox})
        assert r.status_code == 422, bbox
        assert r.json()["error"] == "VALIDATION_ERROR"


def test_status_freshness_flag_dq2(client, make_shelter):
    now = datetime.now(UTC)
    fresh = make_shelter(status_updated_at=now - timedelta(minutes=5))
    stale = make_shelter(status_updated_at=now - timedelta(minutes=45))
    never = make_shelter()
    def flag(s):
        return client.get(f"{URL}/{s.id}").json()["properties"]["status_is_fresh"]
    assert flag(fresh) is True
    assert flag(stale) is False
    assert flag(never) is False


def test_unknown_shelter_is_404(client):
    r = client.get(f"{URL}/{uuid.uuid4()}")
    assert r.status_code == 404
    assert r.json()["error"] == "SHELTER_NOT_FOUND"


# ---------- контакти коменданта (CONFIDENTIAL) ----------


def test_contacts_without_token_is_401(client, make_shelter):
    s = make_shelter(commander_phone="+380501234567")
    r = client.get(f"{URL}/{s.id}/contacts")
    assert r.status_code == 401
    assert "+380501234567" not in r.text


def test_citizen_reading_contacts_gets_403_and_audit_record(
    client, make_shelter, make_user, auth, db
):
    """Обов'язковий негативний сценарій: 403 + запис DENIED у журналі аудиту."""
    s = make_shelter(commander_name="Іван Петренко", commander_phone="+380501234567")
    citizen = make_user(RoleCode.CITIZEN)
    r = client.get(f"{URL}/{s.id}/contacts", headers=auth(citizen))
    assert r.status_code == 403
    body = r.json()
    assert body["error"] == "DENIED_403_RBAC"
    assert body["role"] == "CITIZEN"
    assert body["required_roles"] == ["DSNS_OPERATOR", "SHELTER_MANAGER"]
    assert body["data_classification"] == "CONFIDENTIAL"
    assert "+380501234567" not in r.text and "Петренко" not in r.text

    entry = db.get(AuditLog, body["audit_entry_id"])
    assert entry.action == "DENIED_403_RBAC"
    assert entry.outcome == AuditOutcome.DENIED
    assert entry.http_status == 403
    assert entry.actor_user_id == citizen.id
    assert entry.actor_role == RoleCode.CITIZEN
    assert entry.data_classification == DataClassification.CONFIDENTIAL
    assert entry.details["policy"] == "SHELTER_READ_CONTACTS"
    assert entry.request_id == body["request_id"]
    assert len(entry.hash) == 64
    assert db.scalar(select(func.audit_log_verify())) is None  # ланцюжок цілий


def test_volunteer_and_auditor_also_get_403(client, make_shelter, make_user, auth):
    s = make_shelter()
    for role in (RoleCode.VERIFIED_VOLUNTEER, RoleCode.SECURITY_AUDITOR):
        r = client.get(f"{URL}/{s.id}/contacts", headers=auth(make_user(role)))
        assert r.status_code == 403, role


def test_dsns_operator_reads_any_contacts_and_it_is_audited(
    client, make_shelter, make_user, auth, db
):
    s = make_shelter(commander_name="Іван Петренко", commander_phone="+380501234567")
    operator = make_user(RoleCode.DSNS_OPERATOR)
    r = client.get(f"{URL}/{s.id}/contacts", headers=auth(operator))
    assert r.status_code == 200
    assert r.json() == {
        "shelter_id": str(s.id),
        "commander_name": "Іван Петренко",
        "commander_phone": "+380501234567",
        "data_classification": "CONFIDENTIAL",
    }
    entry = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).one()
    assert entry.action == "SHELTER_READ_CONTACTS"
    assert entry.outcome == AuditOutcome.SUCCESS
    assert entry.entity_id == str(s.id)


def test_manager_reads_only_own_shelter(client, make_shelter, make_user, auth, db):
    own = make_shelter(commander_phone="+380501111111")
    other = make_shelter(commander_phone="+380502222222")
    manager = make_user(RoleCode.SHELTER_MANAGER, assigned_shelter_id=own.id)
    headers = auth(manager)

    assert client.get(f"{URL}/{own.id}/contacts", headers=headers).status_code == 200

    r = client.get(f"{URL}/{other.id}/contacts", headers=headers)
    assert r.status_code == 403
    assert r.json()["reason"] == "not_resource_owner"
    assert "+380502222222" not in r.text
    entry = db.get(AuditLog, r.json()["audit_entry_id"])
    assert entry.entity_id == str(other.id)


def test_manager_without_assignment_gets_403(client, make_shelter, make_user, auth):
    s = make_shelter()
    r = client.get(f"{URL}/{s.id}/contacts", headers=auth(make_user(RoleCode.SHELTER_MANAGER)))
    assert r.status_code == 403


def test_contacts_of_unknown_shelter(client, make_user, auth):
    missing = uuid.uuid4()
    operator = client.get(
        f"{URL}/{missing}/contacts", headers=auth(make_user(RoleCode.DSNS_OPERATOR))
    )
    assert operator.status_code == 404
    # Сторонній не дізнається, чи існує укриття: відмова за роллю йде першою
    citizen = client.get(f"{URL}/{missing}/contacts", headers=auth(make_user()))
    assert citizen.status_code == 403
