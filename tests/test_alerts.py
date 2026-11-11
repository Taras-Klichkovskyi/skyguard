"""Тести інтеграції alerts.in.ua та ендпоінтів тривоги (SG-23)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_alerts_status_default():
    response = client.get("/api/v1/alerts/status")
    assert response.status_code == 200
    data = response.json()
    assert "active" in data
    assert data["location"] == "Львівська область"
    assert data["source"] == "alerts.in.ua"


def test_simulate_alert_toggle():
    # Симуляція увімкнення тривоги
    res_on = client.post("/api/v1/alerts/simulate", json={"active": True})
    assert res_on.status_code == 200
    assert res_on.json()["active"] is True
    assert res_on.json()["started_at"] is not None

    # Перевірка через get
    res_status = client.get("/api/v1/alerts/status")
    assert res_status.json()["active"] is True

    # Симуляція відбою тривоги
    res_off = client.post("/api/v1/alerts/simulate", json={"active": False})
    assert res_off.status_code == 200
    assert res_off.json()["active"] is False
