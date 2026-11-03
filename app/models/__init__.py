"""Імпорт усіх моделей — щоб Alembic бачив повну metadata."""

from app.models.audit_log import AuditLog
from app.models.consent import ConsentRecord
from app.models.role import Role
from app.models.shelter import Shelter
from app.models.status_report import StatusReport
from app.models.user import User

__all__ = ["AuditLog", "ConsentRecord", "Role", "Shelter", "StatusReport", "User"]
