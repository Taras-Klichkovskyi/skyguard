import asyncio
import contextlib
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import alerts, audit, auth, consents, health, shelters, ws
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.services import alerts as alerts_service
from app.services import sweeper

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    sweeper_task = (
        asyncio.create_task(sweeper.run_forever(settings.sweep_interval_s))
        if settings.sweep_interval_s > 0
        else None
    )
    alerts_task = (
        asyncio.create_task(alerts_service.run_alerts_monitor(settings))
        if settings.alerts_in_ua_poll_interval_s > 0
        else None
    )
    yield
    for t in (sweeper_task, alerts_task):
        if t is not None:
            t.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await t


app = FastAPI(
    title=settings.app_name,
    version="0.3.0",
    lifespan=lifespan,
    description=(
        "Прототип керованого обміну геоданими про укриття (SkyGuard).\n\n"
        "Публічний реєстр укриттів доступний без токена. Захищені ендпоінти проходять "
        "шлюз доступу: автентифікація (401) → роль (403) → згода (403); кожна відмова "
        "записується в журнал аудиту, а її номер повертається в `audit_entry_id`.\n\n"
        "Краудсорс-звіти проходять правила якості DQ-1 (≤ 100 м), DQ-2 (≤ 30 хв) і DQ-3 "
        "(кворум). Застосовані зміни статусу розсилаються через WebSocket `/ws/v1/shelters`."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Наскрізний ідентифікатор запиту: потрапляє у відповідь, помилки та журнал аудиту."""
    request.state.request_id = uuid.uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


register_error_handlers(app)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(consents.router)
app.include_router(shelters.router)
app.include_router(alerts.router)
app.include_router(audit.router)

app.include_router(ws.router)
