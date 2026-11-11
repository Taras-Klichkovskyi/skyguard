"""Розсилка змін статусу підписникам через WebSocket.

Підписники зберігаються в пам'яті процесу — цього досить для одного
екземпляра API. Для кількох екземплярів розсилку треба провести через
спільний брокер, наприклад Redis pub/sub (NFR-S4).
"""

import logging
from datetime import UTC, datetime

from fastapi import WebSocket

logger = logging.getLogger(__name__)

SHELTER_UPDATED = "shelter.updated"
AIR_RAID_ALERT_UPDATED = "air_raid_alert.updated"


class Hub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    @property
    def subscribers(self) -> int:
        return len(self._clients)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

    async def broadcast(self, message: dict) -> int:
        """Надсилає повідомлення всім підписникам. Повертає кількість доставлених."""
        delivered = 0
        for client in list(self._clients):
            try:
                await client.send_json(message)
                delivered += 1
            except Exception:  # клієнт зник, не попрощавшись
                self.disconnect(client)
        logger.info("%s -> %d subscribers", message.get("type"), delivered)
        return delivered


hub = Hub()


def shelter_updated(feature: dict, source: str) -> dict:
    """Подія для споживачів: уже публічне подання укриття, без даних репортера."""
    return {
        "type": SHELTER_UPDATED,
        "source": source,
        "sent_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "shelter": feature,
    }


def air_raid_alert_updated(
    active: bool,
    location_title: str,
    started_at: str | None = None,
    source: str = "alerts.in.ua",
) -> dict:
    """Подія про зміну статусу повітряної тривоги (SG-23)."""
    return {
        "type": AIR_RAID_ALERT_UPDATED,
        "active": active,
        "location": location_title,
        "source": source,
        "started_at": started_at,
        "sent_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
