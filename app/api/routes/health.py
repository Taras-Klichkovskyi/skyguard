from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["health"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/health/live")
def live() -> dict:
    """Процес живий (liveness probe)."""
    return {"status": "ok"}


@router.get("/health/ready")
def ready(response: Response, db: DbSession) -> dict:
    """Готовий обслуговувати запити: БД доступна (readiness probe)."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "database": "down"}
    return {"status": "ok", "database": "up"}
