"""Тести працюють проти справжнього PostgreSQL з застосованою міграцією.

    docker compose up -d db
    alembic upgrade head
    pytest

Якщо БД недоступна, тести НЕ пропускаються, а весь запуск зупиняється з
помилкою: зелений результат означає, що перевірені всі гарантії схеми.
Кожен тест працює в транзакції, яка відкочується.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import engine, get_db
from app.main import app
from app.models import Role, Shelter, User
from app.models.enums import RoleCode, ShelterStatus, ShelterType

PASSWORD = "correct-horse-battery"
# argon2 навмисно повільний, тому хеш рахуємо один раз на весь прогін
PASSWORD_HASH = hash_password(PASSWORD)


@pytest.fixture(scope="session", autouse=True)
def require_database() -> None:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT has_water FROM shelter LIMIT 1"))
    except Exception as exc:
        pytest.exit(
            "PostgreSQL з застосованими міграціями недоступний: запустіть "
            "`docker compose up -d db` і `alembic upgrade head`.\n"
            f"Причина: {exc.__class__.__name__}: {exc}",
            returncode=1,
        )


@pytest.fixture
def db() -> Session:
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


@pytest.fixture
def client(db) -> TestClient:
    """HTTP-клієнт, що працює в тій самій транзакції, що й фікстура db."""
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def make_shelter(db):
    counter = iter(range(1, 1000))

    def _make(lat="49.839700", lon="24.029700", **kw) -> Shelter:
        n = next(counter)
        fields = dict(
            registry_id=f"TEST-{n:04d}",
            name=f"Укриття {n}",
            address="вул. Тестова, 1, Львів",
            latitude=Decimal(lat),
            longitude=Decimal(lon),
            shelter_type=ShelterType.PROTECTIVE_STRUCTURE,
            capacity=100,
            current_status=ShelterStatus.OPEN,
        )
        fields.update(kw)
        shelter = Shelter(**fields)
        db.add(shelter)
        db.flush()
        return shelter

    return _make


@pytest.fixture
def make_user(db):
    counter = iter(range(1, 1000))

    def _make(role: RoleCode = RoleCode.CITIZEN, **kw) -> User:
        role_id = db.scalar(select(Role.id).where(Role.code == role))
        fields = dict(
            role_id=role_id,
            email=f"{role.lower()}{next(counter)}@test.ua",
            password_hash=PASSWORD_HASH,
        )
        fields.update(kw)
        user = User(**fields)
        db.add(user)
        db.flush()
        return user

    return _make


@pytest.fixture
def auth(client):
    """Логін через API: повертає заголовок Authorization для користувача."""

    def _headers(user: User) -> dict[str, str]:
        r = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _headers
