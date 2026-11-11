"""Ендпоінти для отримання та тестування статусу повітряної тривоги (SG-23)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.services.alerts import alerts_service, check_alerts

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


class AlertStatusResponse(BaseModel):
    active: bool
    location: str
    location_uid: int
    started_at: str | None = None
    last_checked_at: str | None = None
    configured: bool
    source: str
    last_error: str | None = None


class SimulateAlertRequest(BaseModel):
    active: bool = Field(..., description="Встановити активний або неактивний стан тривоги")


@router.get("/status", response_model=AlertStatusResponse)
async def get_alerts_status(settings: Settings = Depends(get_settings)) -> dict:
    """Отримати поточний статус повітряної тривоги (Львів та область).

    Джерело: alerts.in.ua. У разі відсутності токена повертає стан симулятора.
    """
    token_configured = bool((settings.alerts_in_ua_token or "").strip())
    return alerts_service.get_status(token_configured=token_configured)


@router.post("/simulate", response_model=AlertStatusResponse)
async def simulate_alert_state(
    body: SimulateAlertRequest,
) -> dict:
    """Симуляція надходження тривоги (для тестування фронтенду та реагування).

    Транслює подію WebSocket air_raid_alert.updated усім підключеним клієнтам.
    """
    return await alerts_service.simulate_alert(active=body.active)


@router.post("/check-now", response_model=AlertStatusResponse)
async def force_check_alerts(settings: Settings = Depends(get_settings)) -> dict:
    """Примусовий запит до alerts.in.ua просто зараз (якщо токен задано)."""
    token_configured = bool((settings.alerts_in_ua_token or "").strip())
    if token_configured:
        await check_alerts(settings)
    return alerts_service.get_status(token_configured=token_configured)
