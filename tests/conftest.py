"""Тести схеми працюють проти справжнього PostgreSQL з застосованою міграцією.

    docker compose up -d db
    alembic upgrade head
    pytest

Якщо БД недоступна — тести схеми пропускаються, health/live проходить завжди.
Кожен тест працює в транзакції, яка відкочується.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.session import engine


@pytest.fixture(scope="session")
def db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM role LIMIT 1"))
        return True
    except OperationalError:
        return False
    except Exception:
        return False


@pytest.fixture
def db(db_available) -> Session:
    if not db_available:
        pytest.skip("PostgreSQL з міграцією 0001 недоступний")
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()
