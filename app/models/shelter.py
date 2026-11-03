from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import DataClassification, ShelterStatus, ShelterType
from app.models.mixins import TimestampMixin, UUIDPkMixin, str_enum


class Shelter(UUIDPkMixin, TimestampMixin, Base):
    """Укриття. Клас даних: PUBLIC. Віддається споживачам як GeoJSON Feature (SG-1).

    Координати — WGS84 (EPSG:4326), окремі колонки lat/lon: для прототипу
    Haversine рахується в застосунку (SG-21), PostGIS не потрібен.
    """

    __tablename__ = "shelter"

    registry_id: Mapped[str] = mapped_column(String(64), unique=True)  # ID з міського реєстру
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(String(500))
    district: Mapped[str | None] = mapped_column(String(100))
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    shelter_type: Mapped[ShelterType] = mapped_column(str_enum(ShelterType, "shelter_type"))
    capacity: Mapped[int] = mapped_column(Integer)
    is_accessible: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))

    # Поточний (денормалізований) статус — останній ACCEPTED StatusReport
    current_status: Mapped[ShelterStatus] = mapped_column(
        str_enum(ShelterStatus, "shelter_status"), server_default=ShelterStatus.UNKNOWN.value
    )
    current_occupancy: Mapped[int | None] = mapped_column(Integer)
    status_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    classification: Mapped[DataClassification] = mapped_column(
        str_enum(DataClassification, "data_classification"),
        server_default=DataClassification.PUBLIC.value,
    )
    registry_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )  # штатний режим: синхронізація з реєстром раз на 24 год
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="lat_range"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="lon_range"),
        CheckConstraint("capacity > 0", name="capacity_positive"),
        CheckConstraint(
            "current_occupancy IS NULL OR current_occupancy >= 0", name="occupancy_non_negative"
        ),
        Index("ix_shelter_lat_lon", "latitude", "longitude"),
        Index("ix_shelter_status", "current_status"),
    )
