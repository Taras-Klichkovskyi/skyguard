import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    FetchedValue,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AuditOutcome, DataClassification, RoleCode
from app.models.mixins import str_enum


class AuditLog(Base):
    """Незмінний журнал аудиту. Клас даних: CONFIDENTIAL (L3), читає лише SECURITY_AUDITOR.

    Незмінність забезпечує БД (міграція 0001):
      * тригер забороняє UPDATE / DELETE / TRUNCATE;
      * тригер BEFORE INSERT рахує hash = sha256(prev_hash || запис) — ланцюжок,
        будь-яке втручання в історію ламає перевірку.
    IP зберігається лише як хеш (мінімізація ПДн).
    """

    __tablename__ = "audit_log"

    # id, prev_hash, hash присвоює тригер trg_audit_log_chain
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="RESTRICT")
    )
    actor_role: Mapped[RoleCode | None] = mapped_column(str_enum(RoleCode, "role_code"))
    action: Mapped[str] = mapped_column(String(64))  # напр. STATUS_REPORT_CREATE, CONSENT_REVOKE
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    outcome: Mapped[AuditOutcome] = mapped_column(str_enum(AuditOutcome, "audit_outcome"))
    http_status: Mapped[int | None] = mapped_column(SmallInteger)
    request_id: Mapped[str | None] = mapped_column(String(64))
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    data_classification: Mapped[DataClassification | None] = mapped_column(
        str_enum(DataClassification, "data_classification")
    )
    details: Mapped[dict | None] = mapped_column(JSONB)
    prev_hash: Mapped[str | None] = mapped_column(String(64), server_default=FetchedValue())
    hash: Mapped[str] = mapped_column(String(64), server_default=FetchedValue())

    __table_args__ = (
        Index("ix_audit_log_occurred_at", "occurred_at"),
        Index("ix_audit_log_actor", "actor_user_id", "occurred_at"),
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
        Index("ix_audit_log_outcome", "outcome", "occurred_at"),
    )
