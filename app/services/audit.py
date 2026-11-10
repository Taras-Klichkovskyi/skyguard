"""Запис подій у незмінний журнал аудиту (таблиця audit_log).

Хеш-ланцюжок і заборону змін забезпечує сама БД (міграція 0001); тут лише
формується запис. У журнал не потрапляють паролі, токени, email чи координати.
"""

import hashlib
import hmac
import uuid

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AuditLog, User
from app.models.enums import AuditOutcome, DataClassification, RoleCode


def ip_hash(request: Request) -> str | None:
    """IP зберігається лише як HMAC-SHA-256: звичайний хеш IPv4 легко перебрати."""
    if request.client is None:
        return None
    key = get_settings().jwt_secret.encode()
    return hmac.new(key, request.client.host.encode(), hashlib.sha256).hexdigest()


def record(
    db: Session,
    request: Request,
    *,
    action: str,
    outcome: AuditOutcome,
    http_status: int,
    actor: User | None = None,
    classification: DataClassification | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | str | None = None,
    details: dict | None = None,
    commit: bool = False,
) -> AuditLog:
    """Додає запис аудиту в поточну транзакцію.

    Успішні дії пишуться в одній транзакції з бізнес-зміною (commit робить
    викликач): зміна без аудиторського сліду неможлива. Для відмов
    commit=True — запис має зберегтися, хоча сам запит буде відхилено.
    """
    entry = AuditLog(
        actor_user_id=actor.id if actor else None,
        actor_role=actor.role.code if actor else RoleCode.ANONYMOUS,
        action=action,
        outcome=outcome,
        http_status=http_status,
        data_classification=classification,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        request_id=getattr(request.state, "request_id", None),
        ip_hash=ip_hash(request),
        details={"method": request.method, "path": request.url.path, **(details or {})},
    )
    db.add(entry)
    db.flush()
    if commit:
        db.commit()
    return entry
