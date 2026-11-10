import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.api.deps import DbSession, authorize, deny_rbac
from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.policy import SHELTER_NEARBY_SEARCH, SHELTER_READ_CONTACTS
from app.models import Shelter, User
from app.models.enums import AuditOutcome, ShelterStatus
from app.schemas.common import FORBIDDEN, NOT_FOUND, UNAUTHORIZED, ErrorOut
from app.schemas.shelter import (
    NearbyIn,
    PointGeometry,
    ShelterContactsOut,
    ShelterFeature,
    ShelterFeatureCollection,
    ShelterProperties,
    ShelterResources,
)
from app.services import audit
from app.services.geo import haversine_m, walk_minutes

router = APIRouter(prefix="/api/v1/shelters", tags=["shelters"])


def to_feature(shelter: Shelter, distance_m: float | None = None) -> ShelterFeature:
    """Публічне подання укриття. Контакти коменданта сюди не потрапляють."""
    fresh_after = datetime.now(UTC) - timedelta(minutes=get_settings().dq_max_age_min)
    free = (
        max(shelter.capacity - shelter.current_occupancy, 0)
        if shelter.current_occupancy is not None
        else None
    )
    return ShelterFeature(
        id=shelter.id,
        geometry=PointGeometry(coordinates=(float(shelter.longitude), float(shelter.latitude))),
        properties=ShelterProperties(
            id=shelter.id,
            registry_id=shelter.registry_id,
            name=shelter.name,
            address=shelter.address,
            district=shelter.district,
            shelter_type=shelter.shelter_type,
            capacity=shelter.capacity,
            status=shelter.current_status,
            occupancy=shelter.current_occupancy,
            free_places=free,
            status_updated_at=shelter.status_updated_at,
            status_is_fresh=(
                shelter.status_updated_at is not None and shelter.status_updated_at >= fresh_after
            ),
            resources=ShelterResources(
                ramp=shelter.is_accessible,
                generator=shelter.has_generator,
                starlink=shelter.has_starlink,
                water=shelter.has_water,
            ),
            distance_m=round(distance_m, 1) if distance_m is not None else None,
            walk_minutes=walk_minutes(distance_m) if distance_m is not None else None,
        ),
    )


def _parse_bbox(bbox: str) -> tuple[float, float, float, float]:
    try:
        min_lon, min_lat, max_lon, max_lat = (float(x) for x in bbox.split(","))
    except ValueError as exc:
        raise ApiError(
            422, "VALIDATION_ERROR", "bbox має вигляд min_lon,min_lat,max_lon,max_lat"
        ) from exc
    if not (-180 <= min_lon <= max_lon <= 180 and -90 <= min_lat <= max_lat <= 90):
        raise ApiError(422, "VALIDATION_ERROR", "bbox виходить за межі координат WGS84")
    return min_lon, min_lat, max_lon, max_lat


@router.get(
    "",
    response_model=ShelterFeatureCollection,
    responses={422: {"model": ErrorOut, "description": "Некоректні параметри"}},
)
def list_shelters(
    db: DbSession,
    bbox: Annotated[
        str | None,
        Query(
            description="Вікно мапи: min_lon,min_lat,max_lon,max_lat",
            examples=["23.9,49.78,24.1,49.9"],
        ),
    ] = None,
    status: Annotated[ShelterStatus | None, Query(description="Лише з цим статусом")] = None,
    ramp: Annotated[bool | None, Query(description="Лише з пандусом")] = None,
    generator: Annotated[bool | None, Query()] = None,
    starlink: Annotated[bool | None, Query()] = None,
    water: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> ShelterFeatureCollection:
    """Публічний реєстр укриттів (клас PUBLIC). Автентифікація не потрібна."""
    query = select(Shelter).where(Shelter.is_active.is_(True))
    if bbox:
        min_lon, min_lat, max_lon, max_lat = _parse_bbox(bbox)
        query = query.where(
            Shelter.latitude.between(min_lat, max_lat), Shelter.longitude.between(min_lon, max_lon)
        )
    if status is not None:
        query = query.where(Shelter.current_status == status)
    for column, wanted in (
        (Shelter.is_accessible, ramp),
        (Shelter.has_generator, generator),
        (Shelter.has_starlink, starlink),
        (Shelter.has_water, water),
    ):
        if wanted is not None:
            query = query.where(column.is_(wanted))
    shelters = db.scalars(query.order_by(Shelter.name).limit(limit)).all()
    return ShelterFeatureCollection(features=[to_feature(s) for s in shelters])


@router.post(
    "/nearby",
    response_model=ShelterFeatureCollection,
    responses={**UNAUTHORIZED, **FORBIDDEN},
)
def nearby_shelters(
    body: NearbyIn,
    request: Request,
    db: DbSession,
    user: Annotated[User, Depends(authorize(SHELTER_NEARBY_SEARCH))],
) -> ShelterFeatureCollection:
    """Найближчі укриття за GPS користувача. Потрібна активна згода ROUTE_GPS.

    Координати використовуються лише для обчислення відстані й ніде не зберігаються.
    """
    query = select(Shelter).where(Shelter.is_active.is_(True))
    if body.only_open:
        query = query.where(Shelter.current_status == ShelterStatus.OPEN)
    ranked = sorted(
        (
            (haversine_m(body.latitude, body.longitude, float(s.latitude), float(s.longitude)), s)
            for s in db.scalars(query)
        ),
        key=lambda pair: pair[0],
    )[: body.limit]
    audit.record(
        db,
        request,
        action=SHELTER_NEARBY_SEARCH.action,
        outcome=AuditOutcome.SUCCESS,
        http_status=200,
        actor=user,
        classification=SHELTER_NEARBY_SEARCH.classification,
        details={"results": len(ranked)},  # без координат
    )
    db.commit()
    return ShelterFeatureCollection(features=[to_feature(s, d) for d, s in ranked])


def _get_shelter(db: DbSession, shelter_id: uuid.UUID) -> Shelter:
    shelter = db.get(Shelter, shelter_id)
    if shelter is None or not shelter.is_active:
        raise ApiError(404, "SHELTER_NOT_FOUND", "Укриття не знайдено")
    return shelter


@router.get("/{shelter_id}", response_model=ShelterFeature, responses=NOT_FOUND)
def get_shelter(shelter_id: uuid.UUID, db: DbSession) -> ShelterFeature:
    """Одне укриття з публічного реєстру. Автентифікація не потрібна."""
    return to_feature(_get_shelter(db, shelter_id))


@router.get(
    "/{shelter_id}/contacts",
    response_model=ShelterContactsOut,
    responses={**UNAUTHORIZED, **FORBIDDEN, **NOT_FOUND},
)
def shelter_contacts(
    shelter_id: uuid.UUID,
    request: Request,
    db: DbSession,
    user: Annotated[User, Depends(authorize(SHELTER_READ_CONTACTS))],
) -> ShelterContactsOut:
    """Контакти коменданта (клас CONFIDENTIAL).

    Оператор ДСНС бачить контакти будь-якого укриття, комендант — лише закріпленого за ним.
    """
    policy = SHELTER_READ_CONTACTS
    if policy.needs_ownership(user.role.code) and user.assigned_shelter_id != shelter_id:
        raise deny_rbac(
            db,
            request,
            user,
            policy,
            reason="not_resource_owner",
            entity_type="shelter",
            entity_id=shelter_id,
        )
    shelter = _get_shelter(db, shelter_id)
    audit.record(
        db,
        request,
        action=policy.action,
        outcome=AuditOutcome.SUCCESS,
        http_status=200,
        actor=user,
        classification=policy.classification,
        entity_type="shelter",
        entity_id=shelter.id,
    )
    db.commit()
    return ShelterContactsOut(
        shelter_id=shelter.id,
        commander_name=shelter.commander_name,
        commander_phone=shelter.commander_phone,
    )
