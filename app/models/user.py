import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, SmallInteger, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin


class User(UUIDPkMixin, TimestampMixin, Base):
    """Користувач. Клас даних: CONFIDENTIAL (ПДн).

    Видалення — м'яке (deleted_at) з подальшою анонімізацією за політикою retention:
    жорстке видалення зламало б посилання з append-only журналу аудиту.
    """

    __tablename__ = "app_user"  # "user" — зарезервоване слово в PostgreSQL

    role_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("role.id", ondelete="RESTRICT"), index=True
    )
    email: Mapped[str] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(20))
    full_name: Mapped[str | None] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255))
    # Для коменданта — укриття, за яке він відповідає (RBAC на рівні об'єкта)
    assigned_shelter_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("shelter.id", ondelete="SET NULL"), index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    role: Mapped["Role"] = relationship(back_populates="users")  # noqa: F821
    assigned_shelter: Mapped["Shelter | None"] = relationship()  # noqa: F821
    consents: Mapped[list["ConsentRecord"]] = relationship(back_populates="user")  # noqa: F821

    __table_args__ = (
        # email унікальний без урахування регістру
        Index("uq_app_user_email_lower", text("lower(email)"), unique=True),
    )
