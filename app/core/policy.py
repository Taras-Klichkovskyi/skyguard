"""Політики доступу — матриця RBAC із SG-2 у вигляді даних.

Одна політика відповідає одній дії над одним класом даних: хто її може
виконувати, чи потрібне володіння ресурсом і чи потрібна згода суб'єкта.
Ендпоінти не перевіряють ролі самі, а посилаються на політику, тож усі
правила доступу читаються і змінюються в одному місці.
"""

from dataclasses import dataclass

from app.models.enums import ConsentPurpose, DataClassification, RoleCode

R = RoleCode
AUTHENTICATED = frozenset(
    {R.CITIZEN, R.VERIFIED_VOLUNTEER, R.SHELTER_MANAGER, R.DSNS_OPERATOR, R.SECURITY_AUDITOR}
)


@dataclass(frozen=True)
class AccessPolicy:
    action: str
    classification: DataClassification
    allowed_roles: frozenset[RoleCode]
    # Ролі, яким доступ дозволено лише до закріпленого за ними ресурсу
    ownership_roles: frozenset[RoleCode] = frozenset()
    requires_consent: ConsentPurpose | None = None

    def permits(self, role: RoleCode) -> bool:
        return role in self.allowed_roles

    def needs_ownership(self, role: RoleCode) -> bool:
        return role in self.ownership_roles


# Контакти коменданта (L3): оператор ДСНС — усі укриття, комендант — лише своє
SHELTER_READ_CONTACTS = AccessPolicy(
    action="SHELTER_READ_CONTACTS",
    classification=DataClassification.CONFIDENTIAL,
    allowed_roles=frozenset({R.DSNS_OPERATOR, R.SHELTER_MANAGER}),
    ownership_roles=frozenset({R.SHELTER_MANAGER}),
)

# Пошук найближчих укриттів за GPS користувача (L4): потрібна згода ROUTE_GPS.
# Аудитор безпеки працює лише з журналом і геосервісами не користується.
SHELTER_NEARBY_SEARCH = AccessPolicy(
    action="SHELTER_NEARBY_SEARCH",
    classification=DataClassification.SENSITIVE,
    allowed_roles=frozenset({R.CITIZEN, R.VERIFIED_VOLUNTEER, R.SHELTER_MANAGER, R.DSNS_OPERATOR}),
    requires_consent=ConsentPurpose.ROUTE_GPS,
)

# Власні згоди: будь-який автентифікований користувач керує лише своїми
CONSENT_MANAGE_OWN = AccessPolicy(
    action="CONSENT_MANAGE_OWN",
    classification=DataClassification.SENSITIVE,
    allowed_roles=AUTHENTICATED,
)

# Офіційний статус укриття: комендант — лише свого, оператор ДСНС — будь-якого
SHELTER_STATUS_UPDATE = AccessPolicy(
    action="SHELTER_STATUS_UPDATE",
    classification=DataClassification.PUBLIC,
    allowed_roles=frozenset({R.SHELTER_MANAGER, R.DSNS_OPERATOR}),
    ownership_roles=frozenset({R.SHELTER_MANAGER}),
)

# Краудсорс-звіт про стан укриття: містить GPS репортера (L4), тому потрібна
# згода REPORT_GEOFENCE. Далі звіт проходить правила якості DQ-1..DQ-3.
SHELTER_STATUS_REPORT = AccessPolicy(
    action="SHELTER_STATUS_REPORT",
    classification=DataClassification.SENSITIVE,
    allowed_roles=frozenset({R.CITIZEN, R.VERIFIED_VOLUNTEER}),
    requires_consent=ConsentPurpose.REPORT_GEOFENCE,
)

ALL_POLICIES = (
    SHELTER_READ_CONTACTS,
    SHELTER_NEARBY_SEARCH,
    CONSENT_MANAGE_OWN,
    SHELTER_STATUS_UPDATE,
    SHELTER_STATUS_REPORT,
)
