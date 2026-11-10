"""Згода суб'єкта даних на обробку GPS: видача, відкликання, перевірка."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ConsentRecord
from app.models.enums import ConsentPurpose, ConsentStatus


def status_of(record: ConsentRecord | None, now: datetime | None = None) -> ConsentStatus:
    if record is None:
        return ConsentStatus.NOT_GRANTED
    now = now or datetime.now(UTC)
    if record.revoked_at is not None:
        return ConsentStatus.REVOKED
    if record.expires_at is not None and record.expires_at <= now:
        return ConsentStatus.EXPIRED
    return ConsentStatus.ACTIVE


def latest(db: Session, user_id: uuid.UUID, purpose: ConsentPurpose) -> ConsentRecord | None:
    return db.scalars(
        select(ConsentRecord)
        .where(ConsentRecord.user_id == user_id, ConsentRecord.purpose == purpose)
        .order_by(ConsentRecord.granted_at.desc(), ConsentRecord.id.desc())
        .limit(1)
    ).first()


def is_active(db: Session, user_id: uuid.UUID, purpose: ConsentPurpose) -> bool:
    return status_of(latest(db, user_id, purpose)) is ConsentStatus.ACTIVE


def grant(db: Session, user_id: uuid.UUID, purpose: ConsentPurpose) -> tuple[ConsentRecord, bool]:
    """Повертає (запис, чи створено новий). Повторна видача активної згоди нічого не змінює."""
    now = datetime.now(UTC)
    current = latest(db, user_id, purpose)
    state = status_of(current, now)
    if state is ConsentStatus.ACTIVE:
        return current, False
    if state is ConsentStatus.EXPIRED:
        # Закриваємо прострочений запис: активним на ціль може бути лише один
        current.revoked_at = now
        db.flush()
    record = ConsentRecord(
        user_id=user_id,
        purpose=purpose,
        policy_version=get_settings().consent_policy_version,
        granted_at=now,
    )
    db.add(record)
    db.flush()
    return record, True


def revoke(db: Session, user_id: uuid.UUID, purpose: ConsentPurpose) -> ConsentRecord | None:
    """Відкликає активну згоду. Історія зберігається: запис не видаляється."""
    current = latest(db, user_id, purpose)
    if status_of(current) is not ConsentStatus.ACTIVE:
        return None
    current.revoked_at = datetime.now(UTC)
    db.flush()
    return current
