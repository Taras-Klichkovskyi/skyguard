from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app

client = TestClient(app)


def test_live():
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ready_reports_database_up():
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "up"}


def test_openapi_available():
    assert client.get("/openapi.json").status_code == 200


def test_ready_returns_503_when_database_down():
    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise ConnectionError("database is down")

    app.dependency_overrides[get_db] = lambda: BrokenSession()
    try:
        r = client.get("/health/ready")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 503
    assert r.json() == {"status": "unavailable", "database": "down"}
