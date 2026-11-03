from fastapi import FastAPI

from app.api.routes import health
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Прототип керованого обміну геоданими про укриття (SkyGuard).",
)

app.include_router(health.router)

# Наступні роутери (SG-10, SG-11, SG-21):
#   /api/v1/shelters        — реєстр укриттів у GeoJSON
#   /api/v1/status-reports  — статус від коменданта, краудсорс-звіт
#   /api/v1/consents        — видача / відкликання згоди
#   /api/v1/audit           — консоль аудитора
#   /ws/shelters            — push-оновлення статусів
