"""Зміна статусу укриття: офіційне оновлення і краудсорс-звіт із кворумом."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Shelter, StatusReport, User
from app.models.enums import ReportType, ShelterStatus, ValidationStatus
from app.services import dq

V = ValidationStatus


@dataclass(frozen=True)
class Submission:
    report: StatusReport
    applied: bool
    quorum: dq.Quorum | None = None
    violation: dq.Violation | None = None


def lock_shelter(db: Session, shelter_id: uuid.UUID) -> Shelter | None:
    """Блокує рядок укриття: одночасні звіти про одне укриття обробляються по черзі,

    інакше два звіти могли б порахувати кворум, не побачивши один одного.
    """
    shelter = db.scalars(select(Shelter).where(Shelter.id == shelter_id).with_for_update()).first()
    return shelter if shelter is not None and shelter.is_active else None


def recent_reports(db: Session, user_id: uuid.UUID, now: datetime) -> int:
    """Скільки краудсорс-звітів користувач подав за вікно обмеження частоти."""
    window = timedelta(minutes=get_settings().report_rate_window_min)
    return db.scalar(
        select(func.count())
        .select_from(StatusReport)
        .where(
            StatusReport.reporter_id == user_id,
            StatusReport.report_type == ReportType.CROWDSOURCE,
            StatusReport.received_at > now - window,
        )
    )


def expire_pending(db: Session, now: datetime, shelter_id: uuid.UUID | None = None) -> int:
    """Анулює звіти, що не зібрали кворум за відведене вікно (DQ-3)."""
    deadline = now - timedelta(minutes=get_settings().dq_quorum_window_min)
    query = (
        update(StatusReport)
        .where(
            StatusReport.validation_status == V.QUORUM_PENDING,
            StatusReport.received_at < deadline,
        )
        .values(validation_status=V.EXPIRED, validated_at=now)
    )
    if shelter_id is not None:
        query = query.where(StatusReport.shelter_id == shelter_id)
    return db.execute(query).rowcount


def _apply(shelter: Shelter, status: ShelterStatus, occupancy: int | None, now: datetime) -> None:
    shelter.current_status = status
    shelter.status_updated_at = now
    if occupancy is not None:
        shelter.current_occupancy = occupancy
    elif status is ShelterStatus.FULL:
        shelter.current_occupancy = shelter.capacity
    elif status in (ShelterStatus.CLOSED, ShelterStatus.UNKNOWN):
        shelter.current_occupancy = None
    elif shelter.current_occupancy is not None and shelter.current_occupancy >= shelter.capacity:
        # Укриття знову відкрите, а стара заповненість казала «місць немає»
        shelter.current_occupancy = None


def submit_official(
    db: Session,
    shelter: Shelter,
    user: User,
    status: ShelterStatus,
    occupancy: int | None,
    comment: str | None,
    now: datetime,
) -> Submission:
    """Статус від коменданта чи оператора ДСНС застосовується одразу."""
    report = StatusReport(
        shelter_id=shelter.id,
        reporter_id=user.id,
        report_type=ReportType.OFFICIAL,
        reported_status=status,
        occupancy=occupancy,
        comment=comment,
        weight=user.role.report_weight,
        observed_at=now,
        received_at=now,
        validation_status=V.ACCEPTED,
        validated_at=now,
    )
    db.add(report)
    # Офіційний статус знімає з розгляду всі звіти, що ще чекали кворуму
    db.execute(
        update(StatusReport)
        .where(
            StatusReport.shelter_id == shelter.id,
            StatusReport.validation_status == V.QUORUM_PENDING,
        )
        .values(validation_status=V.EXPIRED, validated_at=now)
    )
    _apply(shelter, status, occupancy, now)
    db.flush()
    return Submission(report, applied=True)


def submit_crowd(
    db: Session,
    shelter: Shelter,
    user: User,
    status: ShelterStatus,
    distance_m: float,
    observed_at: datetime,
    comment: str | None,
    now: datetime,
) -> Submission:
    """Краудсорс-звіт: DQ-2 → DQ-1 → DQ-3. Сирі координати сюди вже не потрапляють."""
    expire_pending(db, now, shelter.id)
    report = StatusReport(
        shelter_id=shelter.id,
        reporter_id=user.id,
        report_type=ReportType.CROWDSOURCE,
        reported_status=status,
        comment=comment,
        distance_m=round(distance_m, 1),
        weight=user.role.report_weight,
        observed_at=observed_at,
        received_at=now,
    )

    violation = dq.first_violation(dq.Evidence(distance_m, observed_at, now))
    if violation is not None:
        report.validation_status = V.REJECTED
        report.rejection_code = violation.code
        report.validated_at = now
        db.add(report)
        db.flush()
        return Submission(report, applied=False, violation=violation)

    # «Незалежні» підтвердження: один користувач — один голос. Його попередній
    # звіт про це укриття, що ще чекав кворуму, замінюється новим.
    db.execute(
        update(StatusReport)
        .where(
            StatusReport.shelter_id == shelter.id,
            StatusReport.reporter_id == user.id,
            StatusReport.validation_status == V.QUORUM_PENDING,
        )
        .values(validation_status=V.EXPIRED, validated_at=now)
    )
    report.validation_status = V.QUORUM_PENDING
    db.add(report)
    db.flush()

    agreeing = db.scalars(
        select(StatusReport).where(
            StatusReport.shelter_id == shelter.id,
            StatusReport.validation_status == V.QUORUM_PENDING,
            StatusReport.reported_status == status,
        )
    ).all()
    quorum = dq.QuorumRule().evaluate([r.weight for r in agreeing])
    if not quorum.reached:
        return Submission(report, applied=False, quorum=quorum)

    for confirmed in agreeing:
        confirmed.validation_status = V.ACCEPTED
        confirmed.validated_at = now
    # Звіти з іншим статусом програли: кворум зібрав протилежне твердження
    db.execute(
        update(StatusReport)
        .where(
            StatusReport.shelter_id == shelter.id,
            StatusReport.validation_status == V.QUORUM_PENDING,
            StatusReport.reported_status != status,
        )
        .values(validation_status=V.EXPIRED, validated_at=now)
    )
    _apply(shelter, status, None, now)
    db.flush()
    return Submission(report, applied=True, quorum=quorum)
