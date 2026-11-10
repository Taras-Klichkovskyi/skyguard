from sqlalchemy import SmallInteger, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import RoleCode
from app.models.mixins import str_enum


class Role(Base):
    """Роль RBAC. 6 записів засіваються міграціями 0001–0002 (перелік — політика SG-2)."""

    __tablename__ = "role"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[RoleCode] = mapped_column(str_enum(RoleCode, "role_code"), unique=True)
    name_uk: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    # Вага звіту про стан укриття для кворуму DQ-3 (поріг — 3): мешканець — 1,
    # волонтер, комендант і оператор ДСНС — 3, тобто застосовують статус одразу.
    report_weight: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))

    users: Mapped[list["User"]] = relationship(back_populates="role")  # noqa: F821
