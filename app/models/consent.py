import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ConsentPurpose
from app.models.mixins import UUIDPkMixin, str_enum


class ConsentRecord(UUIDPkMixin, Base):
    """Згода на обробку ПДн (ЗУ «Про захист персональних даних», GDPR ст. 7).

    Клас даних: SENSITIVE (L4). Записи не редагуються: відкликання = заповнення
    revoked_at, повторна видача = новий запис. Так зберігається доказова історія.
    """

    __tablename__ = "consent_record"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[ConsentPurpose] = mapped_column(str_enum(ConsentPurpose, "consent_purpose"))
    policy_version: Mapped[str] = mapped_column(String(20))  # версія тексту політики
    source: Mapped[str] = mapped_column(String(20), server_default="web")  # web | mobile
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="consents")  # noqa: F821

    __table_args__ = (
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= granted_at", name="revoked_after_granted"
        ),
        CheckConstraint(
            "expires_at IS NULL OR expires_at > granted_at", name="expires_after_granted"
        ),
        # Не більше однієї активної згоди на ціль для користувача
        Index(
            "uq_consent_active_per_purpose",
            "user_id",
            "purpose",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )
