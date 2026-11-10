from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.notify import SHELTER_UPDATED, hub

router = APIRouter()


@router.websocket("/ws/v1/shelters")
async def shelter_updates(websocket: WebSocket) -> None:
    """Потік змін статусу укриттів для мапи.

    Дані публічні (клас PUBLIC), тому токен не потрібен — як і для GET /shelters.
    Сервер надсилає `shelter.updated` після кожної застосованої зміни статусу.
    Клієнт може надіслати текст `ping` і отримає `{"type": "pong"}`.
    """
    await hub.connect(websocket)
    try:
        await websocket.send_json(
            {
                "type": "connected",
                "events": [SHELTER_UPDATED],
                "server_time": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            }
        )
        while True:
            if (await websocket.receive_text()).strip().lower() == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(websocket)
