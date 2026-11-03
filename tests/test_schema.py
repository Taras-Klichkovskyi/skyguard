"""Перевірка гарантій схеми, що закладені на рівні БД (SG-19)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models import AuditLog, ConsentRecord, Role, Shelter, StatusReport, User
from app.models.enums import (
    AuditOutcome,
    ConsentPurpose,
    RejectionCode,
    ReportType,
    RoleCode,
    ShelterStatus,
    ShelterType,
    ValidationStatus,
)

# ---------- фабрики ----------


def make_shelter(db, **kw) -> Shelter:
    s = Shelter(
        registry_id=kw.pop("registry_id", "LV-0001"),
        name="Укриття школи №1",
        address="вул. Зелена, 1, Львів",
        latitude=Decimal("49.839700"),
        longitude=Decimal("24.029700"),
        shelter_type=ShelterType.PROTECTIVE_STRUCTURE,
        capacity=200,
        **kw,
    )
    db.add(s)
    db.flush()
    return s


def make_user(db, role: RoleCode = RoleCode.CITIZEN, email="user@example.com") -> User:
    role_id = db.scalar(select(Role.id).where(Role.code == role))
    u = User(role_id=role_id, email=email, password_hash="x")
    db.add(u)
    db.flush()
    return u


def make_report(db, shelter, user, **kw) -> StatusReport:
    now = datetime.now(UTC)
    defaults = dict(
        shelter_id=shelter.id,
        reporter_id=user.id,
        report_type=ReportType.CROWDSOURCE,
        reported_status=ShelterStatus.OPEN,
        reporter_latitude=Decimal("49.839800"),
        reporter_longitude=Decimal("24.029800"),
        observed_at=now,
        received_at=now,
    )
    defaults.update(kw)
    r = StatusReport(**defaults)
    db.add(r)
    db.flush()
    return r


# ---------- Role ----------


def test_six_roles_seeded(db):
    codes = set(db.scalars(select(Role.code)))
    assert codes == set(RoleCode)


# ---------- Shelter / User ----------


def test_shelter_defaults(db):
    s = make_shelter(db)
    db.refresh(s)
    assert s.current_status == ShelterStatus.UNKNOWN
    assert s.classification.value == "PUBLIC"


def test_shelter_latitude_out_of_range_rejected(db):
    db.add(
        Shelter(
            registry_id="BAD-LAT",
            name="x",
            address="x",
            latitude=Decimal("95"),
            longitude=Decimal("24"),
            shelter_type=ShelterType.SIMPLE_SHELTER,
            capacity=1,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_user_email_unique_case_insensitive(db):
    make_user(db, email="Taras@Example.com")
    with pytest.raises(IntegrityError):
        make_user(db, email="taras@example.com")


# ---------- ConsentRecord ----------


def test_only_one_active_consent_per_purpose(db):
    u = make_user(db)
    db.add(ConsentRecord(user_id=u.id, purpose=ConsentPurpose.GEOLOCATION, policy_version="1.0"))
    db.flush()
    with pytest.raises(IntegrityError):
        db.add(
            ConsentRecord(user_id=u.id, purpose=ConsentPurpose.GEOLOCATION, policy_version="1.0")
        )
        db.flush()


def test_consent_can_be_regranted_after_revoke(db):
    u = make_user(db)
    c = ConsentRecord(user_id=u.id, purpose=ConsentPurpose.GEOLOCATION, policy_version="1.0")
    db.add(c)
    db.flush()
    c.revoked_at = datetime.now(UTC) + timedelta(seconds=1)
    db.flush()
    db.add(ConsentRecord(user_id=u.id, purpose=ConsentPurpose.GEOLOCATION, policy_version="1.1"))
    db.flush()


# ---------- StatusReport: DQ-1 / DQ-2 ----------


def test_dq1_accepted_report_must_be_within_100m(db):
    s, u = make_shelter(db), make_user(db)
    make_report(db, s, u, distance_m=Decimal("15.2"), validation_status=ValidationStatus.ACCEPTED)
    with pytest.raises(IntegrityError):
        make_report(
            db, s, u, distance_m=Decimal("150"), validation_status=ValidationStatus.ACCEPTED
        )


def test_dq1_far_report_can_be_stored_as_rejected(db):
    s, u = make_shelter(db), make_user(db)
    make_report(
        db,
        s,
        u,
        distance_m=Decimal("150"),
        validation_status=ValidationStatus.REJECTED,
        rejection_code=RejectionCode.GEOLOCATION_OUT_OF_BOUNDS,
    )


def test_dq2_accepted_report_must_be_fresh(db):
    s, u = make_shelter(db), make_user(db)
    now = datetime.now(UTC)
    with pytest.raises(IntegrityError):
        make_report(
            db,
            s,
            u,
            distance_m=Decimal("10"),
            validation_status=ValidationStatus.ACCEPTED,
            observed_at=now - timedelta(minutes=45),
            received_at=now,
        )


def test_rejected_report_requires_code(db):
    s, u = make_shelter(db), make_user(db)
    with pytest.raises(IntegrityError):
        make_report(db, s, u, validation_status=ValidationStatus.REJECTED)


# ---------- AuditLog ----------


def write_audit(db, action="ACCESS_DENIED", outcome=AuditOutcome.DENIED) -> AuditLog:
    a = AuditLog(
        action=action,
        outcome=outcome,
        actor_role=RoleCode.CITIZEN,
        http_status=403,
        details={"path": "/api/v1/audit"},
    )
    db.add(a)
    db.flush()
    return a


def test_audit_hash_chain_is_built_by_db(db):
    a1 = write_audit(db)
    a2 = write_audit(db, action="STATUS_REPORT_CREATE", outcome=AuditOutcome.SUCCESS)
    assert len(a1.hash) == 64
    assert a2.prev_hash == a1.hash
    assert a2.id > a1.id
    assert db.scalar(select(func.audit_log_verify())) is None


@pytest.mark.parametrize(
    "stmt",
    [
        "UPDATE audit_log SET action = 'TAMPERED'",
        "DELETE FROM audit_log",
        "TRUNCATE audit_log",
    ],
)
def test_audit_log_is_append_only(db, stmt):
    write_audit(db)
    with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
        db.execute(text(stmt))


def test_audit_verify_detects_tampering(db):
    write_audit(db)
    a = write_audit(db)
    write_audit(db)
    # Імітуємо зловмисника з правами суперкористувача, що обійшов тригер
    db.execute(text("ALTER TABLE audit_log DISABLE TRIGGER trg_audit_log_no_modify"))
    db.execute(text("UPDATE audit_log SET action = 'TAMPERED' WHERE id = :id"), {"id": a.id})
    db.execute(text("ALTER TABLE audit_log ENABLE TRIGGER trg_audit_log_no_modify"))
    assert db.scalar(select(func.audit_log_verify())) == a.id
