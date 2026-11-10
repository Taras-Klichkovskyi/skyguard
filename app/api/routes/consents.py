from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import DbSession, authorize
from app.core.errors import ApiError
from app.core.policy import CONSENT_MANAGE_OWN
from app.models import ConsentRecord, User
from app.models.enums import AuditOutcome, ConsentPurpose
from app.schemas.common import FORBIDDEN, NOT_FOUND, UNAUTHORIZED
from app.schemas.consent import ConsentIn, ConsentOut
from app.services import audit
from app.services import consent as consent_service

router = APIRouter(
    prefix="/api/v1/consents", tags=["consent"], responses={**UNAUTHORIZED, **FORBIDDEN}
)
Subject = Annotated[User, Depends(authorize(CONSENT_MANAGE_OWN))]


def _out(purpose: ConsentPurpose, record: ConsentRecord | None) -> ConsentOut:
    return ConsentOut(
        purpose=purpose,
        status=consent_service.status_of(record),
        policy_version=record.policy_version if record else None,
        granted_at=record.granted_at if record else None,
        revoked_at=record.revoked_at if record else None,
        expires_at=record.expires_at if record else None,
    )


@router.get("", response_model=list[ConsentOut])
def my_consents(user: Subject, db: DbSession) -> list[ConsentOut]:
    """Поточний стан згоди за кожною з трьох цілей обробки GPS."""
    return [_out(p, consent_service.latest(db, user.id, p)) for p in ConsentPurpose]


@router.post("", response_model=ConsentOut, status_code=201)
def grant_consent(
    body: ConsentIn, request: Request, response: Response, user: Subject, db: DbSession
) -> ConsentOut:
    """Надати згоду на одну ціль. Якщо згода вже активна — 200 без змін."""
    record, created = consent_service.grant(db, user.id, body.purpose)
    if not created:
        response.status_code = 200
        return _out(body.purpose, record)
    audit.record(
        db,
        request,
        action="CONSENT_GRANTED",
        outcome=AuditOutcome.SUCCESS,
        http_status=201,
        actor=user,
        classification=CONSENT_MANAGE_OWN.classification,
        entity_type="consent",
        entity_id=record.id,
        details={"purpose": body.purpose, "policy_version": record.policy_version},
    )
    db.commit()
    return _out(body.purpose, record)


@router.delete("/{purpose}", response_model=ConsentOut, responses=NOT_FOUND)
def revoke_consent(
    purpose: ConsentPurpose, request: Request, user: Subject, db: DbSession
) -> ConsentOut:
    """Відкликати згоду. Діє одразу: наступний запит, що її потребує, отримає 403."""
    record = consent_service.revoke(db, user.id, purpose)
    if record is None:
        raise ApiError(404, "CONSENT_NOT_ACTIVE", "Активної згоди на цю ціль немає")
    audit.record(
        db,
        request,
        action="CONSENT_REVOKED",
        outcome=AuditOutcome.SUCCESS,
        http_status=200,
        actor=user,
        classification=CONSENT_MANAGE_OWN.classification,
        entity_type="consent",
        entity_id=record.id,
        details={"purpose": purpose},
    )
    db.commit()
    return _out(purpose, record)
