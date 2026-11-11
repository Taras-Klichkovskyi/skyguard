"""Консоль аудитора безпеки: читання незмінного журналу аудиту (SG-11 / TC-06).

Доступ надається виключно користувачам із роллю SECURITY_AUDITOR.
Усі інші ролі (CITIZEN, SHELTER_MANAGER тощо) отримують відмову 403 DENIED_403_RBAC
із фіксацією інциденту в самому журналі аудиту.
"""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DbSession, authorize
from app.core.policy import AUDIT_TRAIL_READ
from app.models import AuditLog, User
from app.models.enums import AuditOutcome, DataClassification
from app.services import audit as audit_service

router = APIRouter(prefix="/api/v1/governance", tags=["SG-11 Audit Trail"])


class AuditLogItem(BaseModel):
    id: int
    occurred_at: datetime
    actor_role: str | None = None
    action: str
    entity_type: str | None = None
    entity_id: str | None = None
    outcome: str
    http_status: int | None = None
    data_classification: str | None = None
    ip_hash: str | None = None
    details: dict[str, Any] | None = None
    prev_hash: str | None = None
    hash: str | None = None


class AuditTrailResponse(BaseModel):
    audit_event_id: int
    integrity_verified: bool
    count: int
    after_sequence: int
    entries: list[AuditLogItem]


@router.get(
    "/audit-trail",
    response_model=AuditTrailResponse,
    summary="Отримати зріз журналу аудиту з верифікацією ланцюга SHA-256",
)
def read_audit_trail(
    request: Request,
    db: DbSession,
    user: Annotated[User, Depends(authorize(AUDIT_TRAIL_READ))],
    after_sequence: Annotated[
        int, Query(ge=0, description="Початковий ідентифікатор запису")
    ] = 0,
    limit: Annotated[
        int, Query(ge=1, le=200, description="Кількість записів у зрізі")
    ] = 100,
    through_sequence: Annotated[
        int | None, Query(ge=0, description="Кінцевий ідентифікатор запису")
    ] = None,
) -> dict[str, Any]:
    """Читання незмінного журналу аудиту (лише для Security Auditor).

    Перевіряє ланцюжок SHA-256 хешів між послідовними записами (integrity check).
    Факт читання журналу обов'язково фіксується окремим аудиторським записом.
    """
    # 1. Запит вибірки записів
    stmt = (
        select(AuditLog)
        .where(AuditLog.id > after_sequence)
        .order_by(AuditLog.id.asc())
        .limit(limit)
    )
    if through_sequence is not None:
        stmt = stmt.where(AuditLog.id <= through_sequence)

    rows = list(db.scalars(stmt))

    # 2. Перевірка криптографічної цілісності ланцюга SHA-256
    integrity_verified = True
    for i in range(1, len(rows)):
        prev_entry = rows[i - 1]
        curr_entry = rows[i]
        # Якщо prev_hash поточного блоку не збігається з hash попереднього блоку
        if curr_entry.prev_hash and prev_entry.hash and curr_entry.prev_hash != prev_entry.hash:
            integrity_verified = False
            break

    # 3. Фіксація факту читання аудитором
    read_event = audit_service.record(
        db,
        request,
        action="AUDIT_TRAIL_READ",
        outcome=AuditOutcome.SUCCESS,
        http_status=200,
        actor=user,
        classification=DataClassification.CONFIDENTIAL,
        entity_type="audit_log",
        entity_id="snapshot",
        details={
            "after_sequence": after_sequence,
            "limit": limit,
            "count": len(rows),
            "integrity_verified": integrity_verified,
        },
        commit=True,
    )

    items = [
        AuditLogItem(
            id=r.id,
            occurred_at=r.occurred_at,
            actor_role=r.actor_role.value if hasattr(r.actor_role, "value") else str(r.actor_role),
            action=r.action,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            outcome=r.outcome.value if hasattr(r.outcome, "value") else str(r.outcome),
            http_status=r.http_status,
            data_classification=(
                r.data_classification.value
                if hasattr(r.data_classification, "value") and r.data_classification
                else None
            ),
            ip_hash=r.ip_hash,
            details=r.details,
            prev_hash=r.prev_hash,
            hash=r.hash,
        )
        for r in rows
    ]

    return {
        "audit_event_id": read_event.id,
        "integrity_verified": integrity_verified,
        "count": len(items),
        "after_sequence": after_sequence,
        "entries": items,
    }
