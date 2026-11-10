import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    DataClassification,
    RejectionCode,
    ReportType,
    ShelterStatus,
    ValidationStatus,
)
from app.models.mixins import UUIDPkMixin, str_enum


class StatusReport(UUIDPkMixin, Base):
    """Звіт про статус укриття: офіційний (комендант) або краудсорс (громадянин).

    Клас даних: SENSITIVE (L4) — пов'язує особу з місцем і часом перебування.
    Правила DQ-1 (≤100 м) і DQ-2 (≤30 хв) перевіряються в API (SG-21),
    а CHECK-обмеження нижче — страховка на рівні БД: ACCEPTED-звіт, що їх
    порушує, не може бути збережений навіть у разі помилки в коді.
    """

    __tablename__ = "status_report"

    shelter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("shelter.id", ondelete="CASCADE")
    )
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="RESTRICT"), index=True
    )
    report_type: Mapped[ReportType] = mapped_column(str_enum(ReportType, "report_type"))
    reported_status: Mapped[ShelterStatus] = mapped_column(
        str_enum(ShelterStatus, "shelter_status")
    )
    occupancy: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(String(500))

    # Сирі координати репортера API не зберігає (мінімізація даних, SG-2):
    # для перевірки DQ-1 достатньо виміряної відстані distance_m.
    reporter_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    reporter_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    distance_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 1))  # Haversine до укриття
    weight: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))  # для DQ-3

    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # час спостереження
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    validation_status: Mapped[ValidationStatus] = mapped_column(
        str_enum(ValidationStatus, "validation_status"),
        server_default=ValidationStatus.PENDING.value,
    )
    rejection_code: Mapped[RejectionCode | None] = mapped_column(
        str_enum(RejectionCode, "rejection_code")
    )
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    classification: Mapped[DataClassification] = mapped_column(
        str_enum(DataClassification, "data_classification"),
        server_default=DataClassification.SENSITIVE.value,
    )

    shelter: Mapped["Shelter"] = relationship()  # noqa: F821
    reporter: Mapped["User"] = relationship()  # noqa: F821

    __table_args__ = (
        CheckConstraint("reporter_latitude BETWEEN -90 AND 90", name="lat_range"),
        CheckConstraint("reporter_longitude BETWEEN -180 AND 180", name="lon_range"),
        CheckConstraint("occupancy IS NULL OR occupancy >= 0", name="occupancy_non_negative"),
        CheckConstraint("observed_at <= received_at + interval '1 minute'", name="not_from_future"),
        # DQ-1: прийнятий краудсорс-звіт — лише в межах 100 м від укриття.
        # Офіційний статус коменданта чи оператора ДСНС геоприв'язки не потребує.
        CheckConstraint(
            "validation_status <> 'ACCEPTED' OR report_type = 'OFFICIAL' "
            "OR (distance_m IS NOT NULL AND distance_m <= 100)",
            name="dq1_accepted_within_radius",
        ),
        # DQ-2: прийнятий звіт — не старший за 30 хв на момент отримання
        CheckConstraint(
            "validation_status <> 'ACCEPTED' OR received_at - observed_at <= interval '30 minutes'",
            name="dq2_accepted_fresh",
        ),
        CheckConstraint(
            "(validation_status = 'REJECTED') = (rejection_code IS NOT NULL)",
            name="rejection_code_iff_rejected",
        ),
        # Типовий запит: останні звіти по укриттю (поточний статус, кворум DQ-3)
        Index("ix_status_report_shelter_received", "shelter_id", text("received_at DESC")),
    )
