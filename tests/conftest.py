"""Тести працюють проти справжнього PostgreSQL з застосованою міграцією.

    docker compose up -d db
    alembic upgrade head
    pytest

Якщо БД недоступна, тести НЕ пропускаються, а весь запуск зупиняється з
помилкою: зелений результат означає, що перевірені всі гарантії схеми.
Кожен тест працює в транзакції, яка відкочується.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import engine


@pytest.fixture(scope="session", autouse=True)
def require_database() -> None:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM role LIMIT 1"))
    except Exception as exc:
        pytest.exit(
            "PostgreSQL з міграцією 0001 недоступний: запустіть "
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
