"""Залежності FastAPI: сесія БД, поточний користувач, шлюз контролю доступу.

Порядок перевірок однаковий для всіх захищених ендпоінтів:
автентифікація (401) → роль за політикою (403) → згода (403).
Кожна відмова спершу записується в журнал аудиту, і лише тоді клієнт
отримує відповідь з номером цього запису.
"""

import uuid
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core import errors
from app.core.errors import ApiError
from app.core.policy import AccessPolicy
from app.core.security import ACCESS, TokenError, decode_token
from app.db.session import get_db
from app.models import User
from app.models.enums import AuditOutcome
from app.services import audit
from app.services import consent as consent_service

DbSession = Annotated[Session, Depends(get_db)]
bearer_scheme = HTTPBearer(auto_error=False, description="Access-токен з POST /api/v1/auth/login")
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def deny_unauthenticated(db: Session, request: Request, reason: str) -> ApiError:
    entry = audit.record(
        db,
        request,
        action=errors.DENIED_401_AUTH,
        outcome=AuditOutcome.DENIED,
        http_status=401,
        details={"reason": reason},
        commit=True,
    )
    return ApiError(
        401,
        errors.DENIED_401_AUTH,
        "Потрібна автентифікація: надішліть дійсний access-токен",
        headers={"WWW-Authenticate": "Bearer"},
        reason=reason,
        audit_entry_id=entry.id,
    )


def deny_rbac(
    db: Session,
    request: Request,
    user: User,
    policy: AccessPolicy,
    *,
    reason: str = "role_not_allowed",
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
) -> ApiError:
    entry = audit.record(
        db,
        request,
        action=errors.DENIED_403_RBAC,
        outcome=AuditOutcome.DENIED,
        http_status=403,
        actor=user,
        classification=policy.classification,
        entity_type=entity_type,
        entity_id=entity_id,
        details={"policy": policy.action, "reason": reason},
        commit=True,
    )
    return ApiError(
        403,
        errors.DENIED_403_RBAC,
        "Ваша роль не має доступу до цих даних",
        reason=reason,
        role=user.role.code,
        required_roles=sorted(policy.allowed_roles),
        data_classification=policy.classification,
        audit_entry_id=entry.id,
    )


def deny_consent(db: Session, request: Request, user: User, policy: AccessPolicy) -> ApiError:
    entry = audit.record(
        db,
        request,
        action=errors.DENIED_403_CONSENT,
        outcome=AuditOutcome.DENIED,
        http_status=403,
        actor=user,
        classification=policy.classification,
        details={"policy": policy.action, "purpose": policy.requires_consent},
        commit=True,
    )
    return ApiError(
        403,
        errors.DENIED_403_CONSENT,
        "Потрібна ваша згода на обробку геолокації для цієї дії",
        required_consent=policy.requires_consent,
        data_classification=policy.classification,
        audit_entry_id=entry.id,
    )


def get_current_user(request: Request, credentials: Credentials, db: DbSession) -> User:
    if credentials is None:
        raise deny_unauthenticated(db, request, "token_missing")
    try:
        payload = decode_token(credentials.credentials, ACCESS)
    except TokenError as exc:
        raise deny_unauthenticated(db, request, str(exc)) from exc
    user = db.get(User, payload["sub"])
    if user is None or not user.is_active or user.deleted_at is not None:
        raise deny_unauthenticated(db, request, "user_inactive")
    # Роль беремо з БД, а не з токена: зміна ролі діє одразу, без очікування
    # завершення життя вже виданих токенів.
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def authorize(policy: AccessPolicy):
    """Шлюз доступу: повертає користувача, якщо політика дозволяє дію."""

    def gate(request: Request, user: CurrentUser, db: DbSession) -> User:
        if not policy.permits(user.role.code):
            raise deny_rbac(db, request, user, policy)
        if policy.requires_consent and not consent_service.is_active(
            db, user.id, policy.requires_consent
        ):
            raise deny_consent(db, request, user, policy)
        return user

    return gate
