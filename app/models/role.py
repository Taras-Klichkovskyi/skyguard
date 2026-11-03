from sqlalchemy import SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import RoleCode
from app.models.mixins import str_enum


class Role(Base):
    """Роль RBAC. 6 записів засіваються міграцією; змінює лише ADMIN."""

    __tablename__ = "role"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[RoleCode] = mapped_column(str_enum(RoleCode, "role_code"), unique=True)
    name_uk: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)

    users: Mapped[list["User"]] = relationship(back_populates="role")  # noqa: F821
