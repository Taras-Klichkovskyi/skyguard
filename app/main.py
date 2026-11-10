import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, consents, health, shelters
from app.core.config import get_settings
from app.core.errors import register_error_handlers

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description=(
        "Прототип керованого обміну геоданими про укриття (SkyGuard).\n\n"
        "Публічний реєстр укриттів доступний без токена. Захищені ендпоінти проходять "
        "шлюз доступу: автентифікація (401) → роль (403) → згода (403); кожна відмова "
        "записується в журнал аудиту, а її номер повертається в `audit_entry_id`."
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

# Наступні роутери:
#   /api/v1/shelters/{id}/status  — статус від коменданта, краудсорс-звіт, DQ (SG-21)
#   /api/v1/governance/audit-trail — консоль аудитора (SG-11)
#   /ws/shelters                  — push-оновлення статусів (SG-21)
