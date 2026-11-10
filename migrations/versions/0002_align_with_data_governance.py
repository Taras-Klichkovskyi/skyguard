"""Узгодження схеми з політикою Data Governance SG-2 (SG-10).

Початкову схему 0001 писали до затвердження SG-2, тому довідники розійшлися
зі звітом, UML і макетами. Ця міграція приводить їх до одного вигляду:

  * ролі RBAC: ANONYMOUS, CITIZEN, VERIFIED_VOLUNTEER, SHELTER_MANAGER,
    DSNS_OPERATOR, SECURITY_AUDITOR;
  * класифікація L1–L4: PUBLIC, INTERNAL, CONFIDENTIAL, SENSITIVE
    (RESTRICTED скасовано; звіти з GPS репортера стають SENSITIVE);
  * цілі згоди: ROUTE_GPS, REPORT_GEOFENCE, SOS;
  * укриття: ресурси (генератор, Starlink, вода) і контакти коменданта (L3).

audit_log незмінний, тому його старі рядки не переписуються: нові CHECK
додаються як NOT VALID — діють для нових записів, історія лишається як була.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_ROLES = [
    (1, "CITIZEN", "Мешканець", "Маршрут до укриття за згодою, краудсорс-звіти про стан укриття"),
    (2, "SHELTER_MANAGER", "Комендант укриття", "Офіційний статус і контакти закріпленого укриття"),
    (3, "VERIFIED_VOLUNTEER", "Верифікований волонтер", "Звіти про стан укриттів із підвищеною вагою"),
    (4, "DSNS_OPERATOR", "Оператор ДСНС", "Моніторинг, контакти комендантів, обробка SOS"),
    (5, "SECURITY_AUDITOR", "Аудитор безпеки", "Лише читання та перевірка журналу аудиту"),
    (6, "ANONYMOUS", "Анонімний користувач", "Без автентифікації: лише публічний реєстр укриттів"),
]
OLD_ROLES = [
    (1, "CITIZEN", "Громадянин", "Перегляд мапи укриттів, краудсорс-звіт про стан укриття"),
    (2, "COMMANDANT", "Комендант укриття", "Офіційний статус і заповненість закріпленого укриття"),
    (3, "MUNICIPAL_OPERATOR", "Оператор міськради", "Ведення реєстру укриттів, штатна синхронізація"),
    (4, "EMERGENCY_SERVICE", "Екстрена служба (ДСНС)", "Отримання статусів у реальному часі, SOS-режим"),
    (5, "AUDITOR", "Аудитор", "Лише читання журналу аудиту та звітів про доступ"),
    (6, "ADMIN", "Адміністратор", "Керування користувачами та призначення ролей"),
]
NEW_CLASSES = ("PUBLIC", "INTERNAL", "CONFIDENTIAL", "SENSITIVE")
OLD_CLASSES = ("PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED")
NEW_PURPOSES = ("ROUTE_GPS", "REPORT_GEOFENCE", "SOS")
OLD_PURPOSES = ("GEOLOCATION", "PUSH_NOTIFICATIONS", "CROWDSOURCE_REPORTING")


def _in(values: Sequence[str]) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def _require_no_rows(sql: str, problem: str) -> None:
    """Міграція не вгадує, що робити з даними, яким немає відповідника."""
    count = op.get_bind().execute(sa.text(sql)).scalar()
    if count:
        raise RuntimeError(f"Міграцію 0002 зупинено: {problem} (рядків: {count}).")


def _set_roles(roles: list[tuple[int, str, str, str]]) -> None:
    codes = [r[1] for r in roles]
    op.execute("ALTER TABLE role DROP CONSTRAINT ck_role_role_code")
    # Тимчасові коди — щоб не зачепити UNIQUE(code) під час перестановки
    op.execute("UPDATE role SET code = '~' || id")
    for role_id, code, name_uk, description in roles:
        op.execute(
            sa.text(
                "UPDATE role SET code = :code, name_uk = :name, description = :descr WHERE id = :id"
            ).bindparams(code=code, name=name_uk, descr=description, id=role_id)
        )
    op.execute(f"ALTER TABLE role ADD CONSTRAINT ck_role_role_code CHECK (code IN {_in(codes)})")
    op.execute("ALTER TABLE audit_log DROP CONSTRAINT ck_audit_log_role_code")
    op.execute(
        "ALTER TABLE audit_log ADD CONSTRAINT ck_audit_log_role_code "
        f"CHECK (actor_role IN {_in(codes)}) NOT VALID"
    )


def _set_classes(classes: Sequence[str]) -> None:
    for table, column, not_valid in (
        ("shelter", "classification", ""),
        ("status_report", "classification", ""),
        ("audit_log", "data_classification", " NOT VALID"),
    ):
        name = f"ck_{table}_data_classification"
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {name}")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {name} "
            f"CHECK ({column} IN {_in(classes)}){not_valid}"
        )


def _set_purposes(purposes: Sequence[str], mapping: dict[str, str]) -> None:
    op.execute("ALTER TABLE consent_record DROP CONSTRAINT ck_consent_record_consent_purpose")
    for old, new in mapping.items():
        op.execute(
            sa.text("UPDATE consent_record SET purpose = :new WHERE purpose = :old").bindparams(
                new=new, old=old
            )
        )
    op.execute(
        "ALTER TABLE consent_record ADD CONSTRAINT ck_consent_record_consent_purpose "
        f"CHECK (purpose IN {_in(purposes)})"
    )


def upgrade() -> None:
    _require_no_rows(
        "SELECT count(*) FROM app_user WHERE role_id IN (3, 6)",
        "є користувачі з ролями MUNICIPAL_OPERATOR / ADMIN, яких немає в SG-2; "
        "призначте їм іншу роль",
    )
    _require_no_rows(
        "SELECT count(*) FROM consent_record WHERE purpose = 'PUSH_NOTIFICATIONS'",
        "є згоди з ціллю PUSH_NOTIFICATIONS, якої немає в SG-2",
    )

    _set_roles(NEW_ROLES)

    # Спершу знімаємо старі CHECK, тоді переносимо значення
    for table, column in (("shelter", "classification"), ("status_report", "classification")):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT ck_{table}_data_classification")
        op.execute(f"UPDATE {table} SET {column} = 'CONFIDENTIAL' WHERE {column} = 'RESTRICTED'")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT ck_{table}_data_classification "
            f"CHECK ({column} IN {_in(OLD_CLASSES + ('SENSITIVE',))})"
        )
    op.execute("UPDATE status_report SET classification = 'SENSITIVE'")
    _set_classes(NEW_CLASSES)
    op.alter_column("status_report", "classification", server_default="SENSITIVE")

    _set_purposes(
        NEW_PURPOSES,
        {"GEOLOCATION": "ROUTE_GPS", "CROWDSOURCE_REPORTING": "REPORT_GEOFENCE"},
    )

    for column in ("has_generator", "has_starlink", "has_water"):
        op.add_column(
            "shelter",
            sa.Column(column, sa.Boolean(), server_default=sa.text("false"), nullable=False),
        )
    op.add_column("shelter", sa.Column("commander_name", sa.String(length=200), nullable=True))
    op.add_column("shelter", sa.Column("commander_phone", sa.String(length=20), nullable=True))


def downgrade() -> None:
    _require_no_rows(
        "SELECT count(*) FROM app_user WHERE role_id IN (3, 6)",
        "є користувачі з ролями VERIFIED_VOLUNTEER / ANONYMOUS, яких немає у схемі 0001",
    )
    _require_no_rows(
        "SELECT count(*) FROM consent_record WHERE purpose = 'SOS'",
        "є згоди з ціллю SOS, якої немає у схемі 0001",
    )

    for column in ("commander_phone", "commander_name", "has_water", "has_starlink", "has_generator"):
        op.drop_column("shelter", column)

    _set_purposes(
        OLD_PURPOSES,
        {"ROUTE_GPS": "GEOLOCATION", "REPORT_GEOFENCE": "CROWDSOURCE_REPORTING"},
    )

    op.alter_column("status_report", "classification", server_default="CONFIDENTIAL")
    for table in ("shelter", "status_report"):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT ck_{table}_data_classification")
        op.execute(
            f"UPDATE {table} SET classification = 'CONFIDENTIAL' WHERE classification = 'SENSITIVE'"
        )
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT ck_{table}_data_classification "
            f"CHECK (classification IN {_in(OLD_CLASSES)})"
        )
    _set_classes(OLD_CLASSES)

    _set_roles(OLD_ROLES)
