"""Довідники (enum) схеми SkyGuard.

У БД зберігаються як VARCHAR + CHECK (native_enum=False) — так їх легше
розширювати міграціями, ніж нативні типи ENUM у PostgreSQL.
"""

from enum import StrEnum


class RoleCode(StrEnum):
    """6 ролей RBAC за політикою Data Governance (SG-2)."""

    ANONYMOUS = "ANONYMOUS"  # без токена: лише публічна мапа укриттів
    CITIZEN = "CITIZEN"  # мешканець: маршрут за згодою, краудсорс-звіти
    VERIFIED_VOLUNTEER = "VERIFIED_VOLUNTEER"  # волонтер: звіти з підвищеною вагою
    SHELTER_MANAGER = "SHELTER_MANAGER"  # комендант: керує закріпленим укриттям
    DSNS_OPERATOR = "DSNS_OPERATOR"  # оператор ДСНС: моніторинг, контакти комендантів, SOS
    SECURITY_AUDITOR = "SECURITY_AUDITOR"  # аудитор безпеки: лише журнал аудиту


class DataClassification(StrEnum):
    """4-рівнева класифікація даних L1–L4 (SG-2)."""

    PUBLIC = "PUBLIC"  # L1: реєстр укриттів, статус
    INTERNAL = "INTERNAL"  # L2: телеметрія, службові довідники
    CONFIDENTIAL = "CONFIDENTIAL"  # L3: контакти комендантів, облікові записи, журнал аудиту
    SENSITIVE = "SENSITIVE"  # L4: GPS мешканця, SOS, записи згоди


class ShelterType(StrEnum):
    PROTECTIVE_STRUCTURE = "PROTECTIVE_STRUCTURE"  # сховище
    ANTI_RADIATION = "ANTI_RADIATION"  # протирадіаційне укриття
    DUAL_PURPOSE = "DUAL_PURPOSE"  # споруда подвійного призначення
    SIMPLE_SHELTER = "SIMPLE_SHELTER"  # найпростіше укриття


class ShelterStatus(StrEnum):
    OPEN = "OPEN"
    FULL = "FULL"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


class ConsentPurpose(StrEnum):
    """Гранулярні цілі обробки GPS (ст. 11 ЗУ «Про захист персональних даних»)."""

    ROUTE_GPS = "ROUTE_GPS"  # маршрут і пошук найближчого укриття
    REPORT_GEOFENCE = "REPORT_GEOFENCE"  # перевірка присутності біля укриття (DQ-1)
    SOS = "SOS"  # передача координат черговим службам


class ConsentStatus(StrEnum):
    NOT_GRANTED = "NOT_GRANTED"
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class ReportType(StrEnum):
    OFFICIAL = "OFFICIAL"  # від коменданта
    CROWDSOURCE = "CROWDSOURCE"  # від громадянина


class ValidationStatus(StrEnum):
    PENDING = "PENDING"
    QUORUM_PENDING = "QUORUM_PENDING"  # DQ-3: чекаємо підтвердження інших звітів
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"  # кворум не зібрано за відведений час або звіт замінено новішим


class RejectionCode(StrEnum):
    GEOLOCATION_OUT_OF_BOUNDS = "GEOLOCATION_OUT_OF_BOUNDS"  # DQ-1
    STALE_DATA = "STALE_DATA"  # DQ-2
    QUORUM_NOT_REACHED = "QUORUM_NOT_REACHED"  # DQ-3
    NO_CONSENT = "NO_CONSENT"


class AuditOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    DENIED = "DENIED"  # 403 — обов'язково логуємо (SG-13)
    ERROR = "ERROR"
