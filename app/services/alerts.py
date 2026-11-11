"""Інтеграція з API повітряних тривог alerts.in.ua (SG-23).

Здійснює періодичне опитування офіційного ендпоінта https://api.alerts.in.ua/v1/alerts/active.json
для моніторингу статусу тривоги у Львівській області (location_uid=27).
У разі зміни статусу миттєво транслює подію air_raid_alert.updated через WebSocket усім клієнтам.
"""

import asyncio
import json
import logging
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings
from app.services.notify import air_raid_alert_updated, hub

logger = logging.getLogger(__name__)

ALERTS_IN_UA_API_URL = "https://api.alerts.in.ua/v1/alerts/active.json"


class AlertsService:
    def __init__(self) -> None:
        self.is_active: bool = False
        self.location_title: str = "Львівська область"
        self.location_uid: int = 27
        self.started_at: str | None = None
        self.last_checked_at: str | None = None
        self.last_error: str | None = None

    def get_status(self, token_configured: bool) -> dict[str, Any]:
        return {
            "active": self.is_active,
            "location": self.location_title,
            "location_uid": self.location_uid,
            "started_at": self.started_at,
            "last_checked_at": self.last_checked_at,
            "configured": token_configured,
            "source": "alerts.in.ua",
            "last_error": self.last_error,
        }

    async def simulate_alert(self, active: bool) -> dict[str, Any]:
        """Симуляція зміни статусу (для тестування без живого токена)."""
        changed = (self.is_active != active)
        self.is_active = active
        self.started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z") if active else None
        self.last_checked_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        if changed:
            logger.info("Simulated air raid alert: active=%s for %s", active, self.location_title)
            await hub.broadcast(
                air_raid_alert_updated(
                    active=self.is_active,
                    location_title=self.location_title,
                    started_at=self.started_at,
                    source="alerts.in.ua (simulation)",
                )
            )

        return self.get_status(token_configured=False)


alerts_service = AlertsService()


def _fetch_from_alerts_in_ua_sync(token: str, location_uid: int, location_title: str) -> tuple[bool, str | None]:
    """Синхронний запит до API alerts.in.ua (виконується в пулі потоків)."""
    req = urllib.request.Request(
        ALERTS_IN_UA_API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "SkyGuard-Lviv-Emergency/1.0 (+https://github.com/Taras-Klichkovskyi/skyguard)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=8.0) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    alerts = data.get("alerts", [])
    for alert in alerts:
        # Перевірка за location_uid або назвою регіону
        uid = alert.get("location_uid")
        title = alert.get("location_title", "")
        matches_uid = (uid == str(location_uid) or uid == location_uid)
        matches_title = (location_title.lower() in title.lower())

        if (matches_uid or matches_title) and alert.get("finished_at") is None:
            started_at = alert.get("started_at")
            return True, started_at

    return False, None


async def check_alerts(settings: Settings) -> None:
    """Перевірка статусу тривоги в alerts.in.ua через HTTP запит."""
    token = (settings.alerts_in_ua_token or "").strip()
    if not token:
        return

    alerts_service.location_title = settings.alerts_monitored_location_title
    alerts_service.location_uid = settings.alerts_monitored_location_uid

    try:
        is_active, started_at = await asyncio.to_thread(
            _fetch_from_alerts_in_ua_sync,
            token,
            alerts_service.location_uid,
            alerts_service.location_title,
        )
        alerts_service.last_checked_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        alerts_service.last_error = None

        if alerts_service.is_active != is_active:
            alerts_service.is_active = is_active
            alerts_service.started_at = started_at
            logger.warning(
                "🚨 Зміна статусу тривоги в %s: active=%s (started_at=%s)",
                alerts_service.location_title,
                is_active,
                started_at,
            )
            await hub.broadcast(
                air_raid_alert_updated(
                    active=is_active,
                    location_title=alerts_service.location_title,
                    started_at=started_at,
                    source="alerts.in.ua",
                )
            )
    except urllib.error.HTTPError as http_err:
        alerts_service.last_error = f"HTTP {http_err.code}: {http_err.reason}"
        logger.warning("alerts.in.ua HTTP error: %s", alerts_service.last_error)
    except Exception as exc:
        alerts_service.last_error = str(exc)
        logger.warning("alerts.in.ua check failed: %s", exc)


async def run_alerts_monitor(settings: Settings) -> None:
    """Фоновий процес моніторингу alerts.in.ua."""
    token = (settings.alerts_in_ua_token or "").strip()
    if not token:
        logger.info(
            "alerts.in.ua токен не вказано в .env (ALERTS_IN_UA_TOKEN). "
            "Моніторинг працює в режимі очікування токена та локальної симуляції."
        )

    interval = max(10, settings.alerts_in_ua_poll_interval_s)
    while True:
        try:
            if (settings.alerts_in_ua_token or "").strip():
                await check_alerts(settings)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Error in alerts monitor loop: %s", exc)

        await asyncio.sleep(interval)
