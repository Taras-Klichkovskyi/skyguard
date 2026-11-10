"""SG-21: статус від коменданта, краудсорс-звіт, правила DQ-1..DQ-3, WebSocket."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.models import AuditLog, StatusReport
from app.models.enums import AuditOutcome, RoleCode, ShelterStatus, ValidationStatus
from app.services import dq, notify
from app.services import status as status_service

SHELTERS = "/api/v1/shelters"
CONSENTS = "/api/v1/consents"
WS = "/ws/v1/shelters"
# Укриття у фікстурі стоїть у точці 49.8397, 24.0297
AT_DOOR = {"latitude": 49.83975, "longitude": 24.02975}  # ≈ 7 м
NEAR_90M = {"latitude": 49.84051, "longitude": 24.0297}  # ≈ 90 м
FAR_1200M = {"latitude": 49.8505, "longitude": 24.0297}  # ≈ 1,2 км


@pytest.fixture
def reporter(make_user, auth, client):
    """Користувач із наданою згодою REPORT_GEOFENCE: повертає (user, headers)."""

    def _make(role: RoleCode = RoleCode.CITIZEN):
        user = make_user(role)
        headers = auth(user)
        r = client.post(CONSENTS, json={"purpose": "REPORT_GEOFENCE"}, headers=headers)
        assert r.status_code == 201
        return user, headers

    return _make


def report(client, shelter, headers, status="CLOSED", where=AT_DOOR, **extra):
    return client.post(
        f"{SHELTERS}/{shelter.id}/reports",
        json={"status": status, **where, **extra},
        headers=headers,
    )


def public_status(client, shelter) -> str:
    return client.get(f"{SHELTERS}/{shelter.id}").json()["properties"]["status"]


def last_audit(db, action: str) -> AuditLog:
    return db.scalars(
        select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id.desc()).limit(1)
    ).one()


# ---------- офіційний статус (комендант, оператор ДСНС) ----------


def test_manager_updates_own_shelter_immediately(client, make_shelter, make_user, auth, db):
    shelter = make_shelter(capacity=200)
    manager = make_user(RoleCode.SHELTER_MANAGER, assigned_shelter_id=shelter.id)
    r = client.post(
        f"{SHELTERS}/{shelter.id}/status",
        json={"status": "FULL", "occupancy": 200, "comment": "Місць немає"},
        headers=auth(manager),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["applied"] is True
    assert body["validation_status"] == "ACCEPTED"
    assert body["quorum"] is None
    props = body["shelter"]["properties"]
    assert (props["status"], props["occupancy"], props["free_places"]) == ("FULL", 200, 0)
    assert props["status_is_fresh"] is True
    assert public_status(client, shelter) == "FULL"

    entry = last_audit(db, "UPDATE_STATUS_VERIFIED")
    assert entry.outcome == AuditOutcome.SUCCESS
    assert entry.actor_user_id == manager.id
    assert entry.details["from"] == "OPEN" and entry.details["to"] == "FULL"
    stored = db.get(StatusReport, uuid.UUID(body["report_id"]))
    assert stored.report_type == "OFFICIAL" and stored.weight == 3
    assert stored.reporter_latitude is None


def test_manager_cannot_update_foreign_shelter(client, make_shelter, make_user, auth, db):
    own, other = make_shelter(), make_shelter()
    manager = make_user(RoleCode.SHELTER_MANAGER, assigned_shelter_id=own.id)
    r = client.post(
        f"{SHELTERS}/{other.id}/status", json={"status": "CLOSED"}, headers=auth(manager)
    )
    assert r.status_code == 403
    assert r.json()["reason"] == "not_resource_owner"
    assert db.get(AuditLog, r.json()["audit_entry_id"]).action == "DENIED_403_RBAC"
    assert public_status(client, other) == "OPEN"


def test_dsns_operator_updates_any_shelter(client, make_shelter, make_user, auth):
    shelter = make_shelter()
    r = client.post(
        f"{SHELTERS}/{shelter.id}/status",
        json={"status": "CLOSED"},
        headers=auth(make_user(RoleCode.DSNS_OPERATOR)),
    )
    assert r.status_code == 200
    assert r.json()["shelter"]["properties"]["status"] == "CLOSED"


def test_official_status_is_forbidden_for_other_roles(client, make_shelter, make_user, auth):
    shelter = make_shelter()
    url = f"{SHELTERS}/{shelter.id}/status"
    assert client.post(url, json={"status": "CLOSED"}).status_code == 401
    for role in (RoleCode.CITIZEN, RoleCode.VERIFIED_VOLUNTEER, RoleCode.SECURITY_AUDITOR):
        r = client.post(url, json={"status": "CLOSED"}, headers=auth(make_user(role)))
        assert r.status_code == 403, role
        assert r.json()["error"] == "DENIED_403_RBAC"
    assert public_status(client, shelter) == "OPEN"


def test_official_status_validation(client, make_shelter, make_user, auth):
    shelter = make_shelter(capacity=100)
    headers = auth(make_user(RoleCode.DSNS_OPERATOR))
    url = f"{SHELTERS}/{shelter.id}/status"
    assert client.post(url, json={"status": "UNKNOWN"}, headers=headers).status_code == 422
    assert (
        client.post(url, json={"status": "OPEN", "occupancy": -1}, headers=headers).status_code
        == 422
    )
    too_many = client.post(url, json={"status": "OPEN", "occupancy": 101}, headers=headers)
    assert too_many.status_code == 422 and "місткість" in too_many.json()["message"]
    missing = client.post(
        f"{SHELTERS}/{uuid.uuid4()}/status", json={"status": "OPEN"}, headers=headers
    )
    assert missing.status_code == 404


def test_reopening_clears_stale_full_occupancy(client, make_shelter, make_user, auth):
    shelter = make_shelter(capacity=50)
    headers = auth(make_user(RoleCode.DSNS_OPERATOR))
    url = f"{SHELTERS}/{shelter.id}/status"
    full = client.post(url, json={"status": "FULL"}, headers=headers).json()
    assert full["shelter"]["properties"]["occupancy"] == 50
    reopened = client.post(url, json={"status": "OPEN"}, headers=headers).json()
    assert reopened["shelter"]["properties"]["occupancy"] is None
    assert reopened["shelter"]["properties"]["free_places"] is None


# ---------- доступ до краудсорс-звіту ----------


def test_report_requires_token_role_and_consent(client, make_shelter, make_user, auth, db):
    shelter = make_shelter()
    url = f"{SHELTERS}/{shelter.id}/reports"
    payload = {"status": "CLOSED", **AT_DOOR}
    assert client.post(url, json=payload).status_code == 401

    no_consent = client.post(url, json=payload, headers=auth(make_user()))
    assert no_consent.status_code == 403
    assert no_consent.json()["error"] == "DENIED_403_CONSENT"
    assert no_consent.json()["required_consent"] == "REPORT_GEOFENCE"

    # Згода на іншу ціль звітів не відкриває
    user = make_user()
    headers = auth(user)
    client.post(CONSENTS, json={"purpose": "ROUTE_GPS"}, headers=headers)
    assert client.post(url, json=payload, headers=headers).status_code == 403

    # Комендант користується офіційним ендпоінтом, а не краудсорсом
    manager = client.post(url, json=payload, headers=auth(make_user(RoleCode.SHELTER_MANAGER)))
    assert manager.status_code == 403 and manager.json()["error"] == "DENIED_403_RBAC"

    assert db.scalar(select(func.count()).select_from(StatusReport)) == 0


# ---------- DQ-1: геоприв'язка ----------


def test_dq1_report_from_1200m_is_rejected_with_422(client, make_shelter, reporter, db):
    """TC-04: звіт з відстані 1,2 км → 422 GEOLOCATION_OUT_OF_BOUNDS."""
    shelter = make_shelter()
    user, headers = reporter()
    r = report(client, shelter, headers, where=FAR_1200M)
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "GEOLOCATION_OUT_OF_BOUNDS"
    assert body["rule"] == "DQ-1"
    assert 1190 < body["distance_m"] < 1210
    assert body["max_distance_m"] == 100
    assert "підійдіть ближче" in body["message"]
    assert public_status(client, shelter) == "OPEN"

    stored = db.get(StatusReport, uuid.UUID(body["report_id"]))
    assert stored.validation_status == ValidationStatus.REJECTED
    assert stored.rejection_code == "GEOLOCATION_OUT_OF_BOUNDS"
    assert stored.reporter_latitude is None and stored.reporter_longitude is None

    entry = db.get(AuditLog, body["audit_entry_id"])
    assert entry.action == "FAILED_DQ_422"
    assert entry.outcome == AuditOutcome.DENIED and entry.http_status == 422
    assert entry.actor_user_id == user.id
    assert entry.details["rule"] == "DQ-1"
    assert "49.85" not in str(entry.details)  # координат у журналі немає


def test_dq1_boundary_90m_passes_110m_fails(client, make_shelter, reporter):
    shelter = make_shelter()
    _, headers = reporter()
    ok = report(client, shelter, headers, where=NEAR_90M)
    assert ok.status_code == 200
    assert 85 < ok.json()["distance_m"] < 95
    _, other = reporter()
    too_far = report(client, shelter, other, where={"latitude": 49.84069, "longitude": 24.0297})
    assert too_far.status_code == 422
    assert 105 < too_far.json()["distance_m"] < 115


# ---------- DQ-2: свіжість ----------


def test_dq2_stale_observation_is_rejected(client, make_shelter, reporter, db):
    shelter = make_shelter()
    _, headers = reporter()
    old = (datetime.now(UTC) - timedelta(minutes=45)).isoformat()
    r = report(client, shelter, headers, observed_at=old)
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "STALE_DATA"
    assert body["rule"] == "DQ-2"
    assert body["age_min"] == 45 and body["max_age_min"] == 30
    assert db.get(AuditLog, body["audit_entry_id"]).details["rule"] == "DQ-2"
    assert public_status(client, shelter) == "OPEN"


def test_dq2_recent_observation_passes_and_future_is_refused(client, make_shelter, reporter):
    shelter = make_shelter()
    _, headers = reporter()
    recent = (datetime.now(UTC) - timedelta(minutes=20)).isoformat()
    assert report(client, shelter, headers, observed_at=recent).status_code == 200
    future = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
    r = report(client, shelter, headers, observed_at=future)
    assert r.status_code == 422 and r.json()["error"] == "VALIDATION_ERROR"
    naive = report(client, shelter, headers, observed_at="2026-11-11T10:00:00")
    assert naive.status_code == 422  # без часового поясу час неоднозначний


# ---------- DQ-3: кворум ----------


def test_dq3_three_citizens_reach_quorum(client, make_shelter, reporter, db):
    shelter = make_shelter()
    first = report(client, shelter, reporter()[1])
    assert first.status_code == 200
    assert first.json()["applied"] is False
    assert first.json()["validation_status"] == "QUORUM_PENDING"
    assert first.json()["quorum"] == {"collected": 1, "required": 3, "window_min": 15}
    assert public_status(client, shelter) == "OPEN"
    assert last_audit(db, "UPDATE_STATUS_PENDING").details["quorum_collected"] == 1

    second = report(client, shelter, reporter()[1])
    assert second.json()["quorum"]["collected"] == 2
    assert public_status(client, shelter) == "OPEN"

    third = report(client, shelter, reporter()[1])
    assert third.json()["applied"] is True
    assert third.json()["validation_status"] == "ACCEPTED"
    assert third.json()["shelter"]["properties"]["status"] == "CLOSED"
    assert public_status(client, shelter) == "CLOSED"

    states = db.scalars(
        select(StatusReport.validation_status).where(StatusReport.shelter_id == shelter.id)
    ).all()
    assert states == ["ACCEPTED"] * 3


def test_dq3_same_user_cannot_confirm_own_report(client, make_shelter, reporter, db):
    shelter = make_shelter()
    _, headers = reporter()
    for expected in (1, 1, 1):
        r = report(client, shelter, headers)
        assert r.status_code == 200
        assert r.json()["quorum"]["collected"] == expected
        assert r.json()["applied"] is False
    assert public_status(client, shelter) == "OPEN"
    states = sorted(
        db.scalars(
            select(StatusReport.validation_status).where(StatusReport.shelter_id == shelter.id)
        )
    )
    assert states == ["EXPIRED", "EXPIRED", "QUORUM_PENDING"]


def test_dq3_volunteer_applies_immediately(client, make_shelter, reporter):
    shelter = make_shelter()
    r = report(client, shelter, reporter(RoleCode.VERIFIED_VOLUNTEER)[1], status="FULL")
    assert r.status_code == 200
    assert r.json()["applied"] is True
    assert r.json()["quorum"] == {"collected": 3, "required": 3, "window_min": 15}
    props = r.json()["shelter"]["properties"]
    assert props["status"] == "FULL" and props["free_places"] == 0


def test_dq3_citizen_plus_volunteer_confirms_both(client, make_shelter, reporter, db):
    shelter = make_shelter()
    report(client, shelter, reporter()[1])
    r = report(client, shelter, reporter(RoleCode.VERIFIED_VOLUNTEER)[1])
    assert r.json()["applied"] is True and r.json()["quorum"]["collected"] == 4
    assert set(
        db.scalars(
            select(StatusReport.validation_status).where(StatusReport.shelter_id == shelter.id)
        )
    ) == {"ACCEPTED"}


def test_dq3_conflicting_reports_do_not_add_up(client, make_shelter, reporter, db):
    shelter = make_shelter()
    assert (
        report(client, shelter, reporter()[1], status="CLOSED").json()["quorum"]["collected"] == 1
    )
    assert report(client, shelter, reporter()[1], status="FULL").json()["quorum"]["collected"] == 1
    assert (
        report(client, shelter, reporter()[1], status="CLOSED").json()["quorum"]["collected"] == 2
    )
    assert public_status(client, shelter) == "OPEN"
    won = report(client, shelter, reporter()[1], status="CLOSED")
    assert won.json()["applied"] is True
    assert public_status(client, shelter) == "CLOSED"
    by_status = dict(
        db.execute(
            select(StatusReport.reported_status, StatusReport.validation_status).where(
                StatusReport.shelter_id == shelter.id, StatusReport.reported_status == "FULL"
            )
        ).all()
    )
    assert by_status == {"FULL": "EXPIRED"}  # протилежне твердження програло


def test_dq3_reports_outside_window_expire(client, make_shelter, reporter, db):
    shelter = make_shelter()
    for _ in range(2):
        report(client, shelter, reporter()[1])
    # Два звіти «зістарюємо» на 16 хв: вікно кворуму — 15 хв
    db.execute(
        StatusReport.__table__.update()
        .where(StatusReport.shelter_id == shelter.id)
        .values(
            received_at=StatusReport.received_at - timedelta(minutes=16),
            observed_at=StatusReport.observed_at - timedelta(minutes=16),
        )
    )
    late = report(client, shelter, reporter()[1])
    assert late.json()["applied"] is False
    assert late.json()["quorum"]["collected"] == 1
    assert public_status(client, shelter) == "OPEN"
    states = sorted(
        db.scalars(
            select(StatusReport.validation_status).where(StatusReport.shelter_id == shelter.id)
        )
    )
    assert states == ["EXPIRED", "EXPIRED", "QUORUM_PENDING"]


def test_expire_pending_sweeps_all_shelters(make_shelter, make_user, db):
    now = datetime.now(UTC)
    old, fresh = make_shelter(), make_shelter()
    for shelter, age in ((old, 20), (fresh, 5)):
        db.add(
            StatusReport(
                shelter_id=shelter.id,
                reporter_id=make_user().id,
                report_type="CROWDSOURCE",
                reported_status="CLOSED",
                distance_m=10,
                weight=1,
                observed_at=now - timedelta(minutes=age),
                received_at=now - timedelta(minutes=age),
                validation_status="QUORUM_PENDING",
            )
        )
    db.flush()
    assert status_service.expire_pending(db, now) == 1
    remaining = db.scalars(
        select(StatusReport.shelter_id).where(StatusReport.validation_status == "QUORUM_PENDING")
    ).all()
    assert remaining == [fresh.id]


def test_official_status_overrides_pending_reports(
    client, make_shelter, make_user, reporter, auth, db
):
    shelter = make_shelter()
    report(client, shelter, reporter()[1], status="CLOSED")
    report(client, shelter, reporter()[1], status="CLOSED")
    client.post(
        f"{SHELTERS}/{shelter.id}/status",
        json={"status": "OPEN", "occupancy": 10},
        headers=auth(make_user(RoleCode.DSNS_OPERATOR)),
    )
    # Третій звіт уже не добирає старий кворум: рахунок почато заново
    third = report(client, shelter, reporter()[1], status="CLOSED")
    assert third.json()["applied"] is False and third.json()["quorum"]["collected"] == 1
    assert public_status(client, shelter) == "OPEN"


# ---------- обмеження частоти ----------


def test_rate_limit_three_reports_per_five_minutes(client, make_shelter, reporter, db):
    """UC-02 EX4: четвертий звіт за 5 хв → 429."""
    shelters = [make_shelter() for _ in range(4)]
    user, headers = reporter()
    for shelter in shelters[:3]:
        assert report(client, shelter, headers).status_code == 200
    blocked = report(client, shelters[3], headers)
    assert blocked.status_code == 429
    assert blocked.json()["error"] == "RATE_LIMITED"
    assert blocked.headers["Retry-After"] == "300"
    assert db.get(AuditLog, blocked.json()["audit_entry_id"]).action == "RATE_LIMITED_429"
    # Обмеження особисте: інший користувач звітує вільно
    assert report(client, shelters[3], reporter()[1]).status_code == 200
    # Через 5 хв ліміт знімається
    db.execute(
        StatusReport.__table__.update()
        .where(StatusReport.reporter_id == user.id)
        .values(
            received_at=StatusReport.received_at - timedelta(minutes=6),
            observed_at=StatusReport.observed_at - timedelta(minutes=6),
        )
    )
    assert report(client, shelters[3], headers).status_code == 200


def test_rejected_reports_count_towards_rate_limit(client, make_shelter, reporter):
    shelter = make_shelter()
    _, headers = reporter()
    for _ in range(3):
        assert report(client, shelter, headers, where=FAR_1200M).status_code == 422
    assert report(client, shelter, headers).status_code == 429


def test_report_for_unknown_shelter_is_404(client, reporter):
    r = client.post(
        f"{SHELTERS}/{uuid.uuid4()}/reports",
        json={"status": "OPEN", **AT_DOOR},
        headers=reporter()[1],
    )
    assert r.status_code == 404


# ---------- WebSocket ----------


def test_ws_greets_and_answers_ping(client):
    with client.websocket_connect(WS) as ws:
        hello = ws.receive_json()
        assert hello["type"] == "connected"
        assert hello["events"] == ["shelter.updated"]
        ws.send_text("ping")
        assert ws.receive_json() == {"type": "pong"}
    assert notify.hub.subscribers == 0


def test_ws_pushes_official_status_update(client, make_shelter, make_user, auth):
    shelter = make_shelter(commander_phone="+380501234567")
    headers = auth(make_user(RoleCode.DSNS_OPERATOR))
    with client.websocket_connect(WS) as first, client.websocket_connect(WS) as second:
        first.receive_json(), second.receive_json()
        client.post(f"{SHELTERS}/{shelter.id}/status", json={"status": "CLOSED"}, headers=headers)
        for ws in (first, second):
            event = ws.receive_json()
            assert event["type"] == "shelter.updated"
            assert event["source"] == "OFFICIAL"
            assert event["shelter"]["id"] == str(shelter.id)
            assert event["shelter"]["properties"]["status"] == "CLOSED"
            assert event["shelter"]["geometry"]["type"] == "Point"
            # Подія публічна: ні контактів коменданта, ні даних репортера
            assert "+380501234567" not in str(event) and "reporter" not in str(event)


def test_ws_pushes_only_when_quorum_is_reached(client, make_shelter, reporter):
    shelter = make_shelter()
    with client.websocket_connect(WS) as ws:
        ws.receive_json()
        report(client, shelter, reporter()[1])
        report(client, shelter, reporter()[1])
        ws.send_text("ping")
        assert ws.receive_json() == {"type": "pong"}  # подій до кворуму не було
        report(client, shelter, reporter()[1])
        event = ws.receive_json()
        assert event["type"] == "shelter.updated" and event["source"] == "CROWDSOURCE"
        assert event["shelter"]["properties"]["status"] == "CLOSED"


def test_ws_does_not_push_rejected_report(client, make_shelter, reporter):
    shelter = make_shelter()
    with client.websocket_connect(WS) as ws:
        ws.receive_json()
        report(client, shelter, reporter(RoleCode.VERIFIED_VOLUNTEER)[1], where=FAR_1200M)
        ws.send_text("ping")
        assert ws.receive_json() == {"type": "pong"}


# ---------- правила як такі ----------


def test_rule_pipeline_checks_freshness_before_distance():
    now = datetime.now(UTC)
    both_bad = dq.Evidence(distance_m=5000, observed_at=now - timedelta(hours=2), received_at=now)
    assert dq.first_violation(both_bad).rule == "DQ-2"
    assert dq.first_violation(dq.Evidence(100.0, now - timedelta(minutes=30), now)) is None
    assert dq.first_violation(dq.Evidence(100.1, now, now)).rule == "DQ-1"


def test_quorum_rule():
    rule = dq.QuorumRule()
    assert rule.evaluate([1, 1]).reached is False
    assert rule.evaluate([1, 1, 1]).reached is True
    assert rule.evaluate([3]).reached is True


def test_role_weights_seeded(db):
    from app.models import Role

    weights = dict(db.execute(select(Role.code, Role.report_weight)).all())
    assert weights == {
        "ANONYMOUS": 0,
        "CITIZEN": 1,
        "VERIFIED_VOLUNTEER": 3,
        "SHELTER_MANAGER": 3,
        "DSNS_OPERATOR": 3,
        "SECURITY_AUDITOR": 0,
    }


def test_shelter_status_enum_untouched():
    assert {s.value for s in ShelterStatus} == {"OPEN", "FULL", "CLOSED", "UNKNOWN"}
