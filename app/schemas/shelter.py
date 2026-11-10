"""Укриття у форматі GeoJSON (RFC 7946): координати — [довгота, широта], WGS84."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import ShelterStatus, ShelterType


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
