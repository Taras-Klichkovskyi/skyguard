"""Укриття у форматі GeoJSON (RFC 7946): координати — [довгота, широта], WGS84."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

from app.models.enums import ShelterStatus, ShelterType, ValidationStatus


class PointGeometry(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float] = Field(
        description="[довгота, широта]", examples=[[24.0297, 49.8397]]
    )


class ShelterResources(BaseModel):
    ramp: bool
    generator: bool
    starlink: bool
    water: bool


class ShelterProperties(BaseModel):
    id: uuid.UUID
    registry_id: str
    name: str
    address: str
    district: str | None
    shelter_type: ShelterType
    capacity: int
    status: ShelterStatus
    occupancy: int | None
    free_places: int | None
    status_updated_at: datetime | None
    status_is_fresh: bool = Field(description="DQ-2: статус підтверджено не пізніше ніж 30 хв тому")
    resources: ShelterResources
    distance_m: float | None = Field(
        default=None, description="Лише у відповіді пошуку найближчих укриттів"
    )
    walk_minutes: int | None = None


class ShelterFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: uuid.UUID
    geometry: PointGeometry
    properties: ShelterProperties


class ShelterFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[ShelterFeature]


class NearbyIn(BaseModel):
    """Координати передаються в тілі запиту, а не в URL, щоб не осідати в журналах доступу."""

    latitude: float = Field(ge=-90, le=90, examples=[49.8397])
    longitude: float = Field(ge=-180, le=180, examples=[24.0297])
    limit: int = Field(default=5, ge=1, le=20)
    only_open: bool = True


class ShelterContactsOut(BaseModel):
    shelter_id: uuid.UUID
    commander_name: str | None
    commander_phone: str | None
    data_classification: Literal["CONFIDENTIAL"] = "CONFIDENTIAL"


ReportableStatus = Literal[ShelterStatus.OPEN, ShelterStatus.FULL, ShelterStatus.CLOSED]


class StatusUpdateIn(BaseModel):
    """Офіційний статус від коменданта або оператора ДСНС."""

    status: ReportableStatus
    occupancy: int | None = Field(default=None, ge=0, description="Скільки людей зараз в укритті")
    comment: str | None = Field(default=None, max_length=500)


class StatusReportIn(BaseModel):
    """Краудсорс-звіт. Координати потрібні лише для перевірки DQ-1 і не зберігаються."""

    status: ReportableStatus
    latitude: float = Field(ge=-90, le=90, examples=[49.8397])
    longitude: float = Field(ge=-180, le=180, examples=[24.0297])
    observed_at: AwareDatetime | None = Field(
        default=None, description="Час спостереження (ISO 8601 з часовим поясом); типово — зараз"
    )
    comment: str | None = Field(default=None, max_length=500)


class QuorumOut(BaseModel):
    collected: int = Field(description="Сума ваг звітів, що підтверджують цей статус")
    required: int
    window_min: int


class StatusSubmissionOut(BaseModel):
    report_id: uuid.UUID
    shelter_id: uuid.UUID
    reported_status: ShelterStatus
    applied: bool = Field(description="Чи змінено публічний статус укриття")
    validation_status: ValidationStatus
    distance_m: float | None = Field(default=None, description="Виміряна сервером відстань, DQ-1")
    quorum: QuorumOut | None = Field(default=None, description="Стан кворуму DQ-3")
    shelter: ShelterFeature
