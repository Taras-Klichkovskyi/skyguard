"""Довідники (enum) схеми SkyGuard.

У БД зберігаються як VARCHAR + CHECK (native_enum=False) — так їх легше
розширювати міграціями, ніж нативні типи ENUM у PostgreSQL.
"""

from enum import StrEnum


class RoleCode(StrEnum):
    """6 ролей RBAC (SG-2)."""

    CITIZEN = "CITIZEN"  # громадянин: бачить мапу, надсилає краудсорс-звіт
    COMMANDANT = "COMMANDANT"  # комендант укриття: офіційний статус свого укриття
    MUNICIPAL_OPERATOR = "MUNICIPAL_OPERATOR"  # оператор міськради: веде реєстр укриттів
    EMERGENCY_SERVICE = "EMERGENCY_SERVICE"  # ДСНС / екстрені служби: споживач real-time
    AUDITOR = "AUDITOR"  # аудитор: лише читання журналу аудиту
    ADMIN = "ADMIN"  # адміністратор: користувачі та ролі


class DataClassification(StrEnum):
    """4-рівнева класифікація даних (SG-2)."""

    PUBLIC = "PUBLIC"  # публічні: реєстр укриттів, статус
    INTERNAL = "INTERNAL"  # службові: агреговані звіти, метрики
    CONFIDENTIAL = "CONFIDENTIAL"  # конфіденційні: ПДн, геолокація користувача, згоди
    RESTRICTED = "RESTRICTED"  # обмеженого доступу: журнал аудиту, безпекові події


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
    GEOLOCATION = "GEOLOCATION"  # обробка геопозиції для пошуку найближчого укриття
    PUSH_NOTIFICATIONS = "PUSH_NOTIFICATIONS"  # сповіщення про зміну статусу
    CROWDSOURCE_REPORTING = "CROWDSOURCE_REPORTING"  # надсилання звітів з геоміткою


class ReportType(StrEnum):
    OFFICIAL = "OFFICIAL"  # від коменданта
    CROWDSOURCE = "CROWDSOURCE"  # від громадянина


class ValidationStatus(StrEnum):
    PENDING = "PENDING"
    QUORUM_PENDING = "QUORUM_PENDING"  # DQ-3: чекаємо підтвердження інших звітів
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class RejectionCode(StrEnum):
    GEOLOCATION_OUT_OF_BOUNDS = "GEOLOCATION_OUT_OF_BOUNDS"  # DQ-1
    STALE_DATA = "STALE_DATA"  # DQ-2
    QUORUM_NOT_REACHED = "QUORUM_NOT_REACHED"  # DQ-3
    NO_CONSENT = "NO_CONSENT"


class AuditOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    DENIED = "DENIED"  # 403 — обов'язково логуємо (SG-13)
    ERROR = "ERROR"
