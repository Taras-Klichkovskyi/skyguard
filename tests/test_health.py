from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_live():
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ready_reports_database_state(db_available):
    r = client.get("/health/ready")
    if db_available:
        assert r.status_code == 200
        assert r.json()["database"] == "up"
    else:
        assert r.status_code == 503


def test_openapi_available():
    assert client.get("/openapi.json").status_code == 200
