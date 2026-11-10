"""Демонстраційні дані для прототипу: укриття Львова і по одному користувачу на роль.

    python -m app.seed

Запуск повторюваний: наявні записи не дублюються. Укриття вигадані
(registry_id починається з DEMO-), координати — у межах Львова.
Усі демо-користувачі мають однаковий пароль із SEED_PASSWORD.
"""

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Role, Shelter, User
from app.models.enums import RoleCode, ShelterStatus, ShelterType

DEFAULT_PASSWORD = "skyguard-demo"

T = ShelterType
S = ShelterStatus
# registry_id, назва, адреса, район, lat, lon, тип, місткість, статус, зайнято,
# пандус, генератор, starlink, вода
SHELTERS = [
    (
        "DEMO-0001",
        "Підземний паркінг ТРЦ",
        "вул. Під Дубом, 7Б",
        "Шевченківський",
        "49.849800",
        "24.022300",
        T.DUAL_PURPOSE,
        850,
        S.OPEN,
        140,
        True,
        True,
        True,
        True,
    ),
    (
        "DEMO-0002",
        "Школа №12, підвал",
        "вул. Городоцька, 40",
        "Залізничний",
        "49.838600",
        "24.014900",
        T.SIMPLE_SHELTER,
        200,
        S.CLOSED,
        None,
        False,
        False,
        False,
        True,
    ),
    (
        "DEMO-0003",
        "Підвал ОСББ «Затишок»",
        "вул. Личаківська, 55",
        "Личаківський",
        "49.838900",
        "24.047800",
        T.SIMPLE_SHELTER,
        60,
        S.FULL,
        60,
        False,
        False,
        False,
        False,
    ),
    (
        "DEMO-0004",
        "Сховище політехніки, корпус 1",
        "вул. Степана Бандери, 12",
        "Франківський",
        "49.835300",
        "24.014200",
        T.PROTECTIVE_STRUCTURE,
        400,
        S.OPEN,
        85,
        True,
        True,
        False,
        True,
    ),
    (
        "DEMO-0005",
        "Укриття лікарні",
        "вул. Миколайчука, 9",
        "Шевченківський",
        "49.867600",
        "24.030900",
        T.PROTECTIVE_STRUCTURE,
        300,
        S.OPEN,
        120,
        True,
        True,
        True,
        True,
    ),
    (
        "DEMO-0006",
        "Підземний перехід, пл. Митна",
        "пл. Митна, 1",
        "Галицький",
        "49.839900",
        "24.037300",
        T.DUAL_PURPOSE,
        150,
        S.OPEN,
        20,
        False,
        False,
        False,
        False,
    ),
    (
        "DEMO-0007",
        "Протирадіаційне укриття заводу",
        "вул. Зелена, 149",
        "Сихівський",
        "49.812400",
        "24.060300",
        T.ANTI_RADIATION,
        500,
        S.UNKNOWN,
        None,
        False,
        True,
        False,
        True,
    ),
    (
        "DEMO-0008",
        "Паркінг бізнес-центру",
        "вул. Героїв УПА, 73",
        "Франківський",
        "49.826700",
        "24.000600",
        T.DUAL_PURPOSE,
        350,
        S.OPEN,
        40,
        True,
        True,
        True,
        False,
    ),
]

# email, роль, ім'я, registry_id закріпленого укриття
USERS = [
    ("citizen@skyguard.demo", RoleCode.CITIZEN, "Олена Мешканка", None),
    ("volunteer@skyguard.demo", RoleCode.VERIFIED_VOLUNTEER, "Андрій Волонтер", None),
    ("manager@skyguard.demo", RoleCode.SHELTER_MANAGER, "Іван Комендант", "DEMO-0001"),
    ("dsns@skyguard.demo", RoleCode.DSNS_OPERATOR, "Марія Операторка", None),
    ("auditor@skyguard.demo", RoleCode.SECURITY_AUDITOR, "Петро Аудитор", None),
]


def seed() -> tuple[int, int]:
    if get_settings().app_env not in ("dev", "test"):
        raise SystemExit("Демо-дані призначені лише для APP_ENV=dev/test")
    password_hash = hash_password(os.environ.get("SEED_PASSWORD", DEFAULT_PASSWORD))
    now = datetime.now(UTC)
    new_shelters = new_users = 0
    with SessionLocal() as db:
        for i, row in enumerate(SHELTERS):
            (
                registry_id,
                name,
                address,
                district,
                lat,
                lon,
                kind,
                capacity,
                status,
                occupancy,
                ramp,
                generator,
                starlink,
                water,
            ) = row
            if db.scalar(select(Shelter.id).where(Shelter.registry_id == registry_id)):
                continue
            db.add(
                Shelter(
                    registry_id=registry_id,
                    name=name,
                    address=f"{address}, Львів",
                    district=district,
                    latitude=Decimal(lat),
                    longitude=Decimal(lon),
                    shelter_type=kind,
                    capacity=capacity,
                    current_status=status,
                    current_occupancy=occupancy,
                    status_updated_at=None
                    if status is S.UNKNOWN
                    else now - timedelta(minutes=5 * i),
                    is_accessible=ramp,
                    has_generator=generator,
                    has_starlink=starlink,
                    has_water=water,
                    commander_name=f"Комендант укриття {registry_id}",
                    commander_phone=f"+38050000{i + 1:04d}",
                    registry_synced_at=now,
                )
            )
            new_shelters += 1
        db.flush()

        roles = {code: role_id for role_id, code in db.execute(select(Role.id, Role.code))}
        for email, role, full_name, shelter_registry_id in USERS:
            if db.scalar(select(User.id).where(func.lower(User.email) == email)):
                continue
            shelter_id = (
                db.scalar(select(Shelter.id).where(Shelter.registry_id == shelter_registry_id))
                if shelter_registry_id
                else None
            )
            db.add(
                User(
                    role_id=roles[role],
                    email=email,
                    full_name=full_name,
                    password_hash=password_hash,
                    assigned_shelter_id=shelter_id,
                )
            )
            new_users += 1
        db.commit()
    return new_shelters, new_users


if __name__ == "__main__":
    shelters, users = seed()
    print(f"Додано укриттів: {shelters}, користувачів: {users}")
