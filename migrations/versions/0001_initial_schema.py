"""Початкова схема SkyGuard (SG-19).

Таблиці: role, shelter, app_user, consent_record, status_report, audit_log.
Крім автогенерованих таблиць міграція створює:
  * засів 6 ролей RBAC;
  * тригер updated_at для shelter і app_user;
  * append-only захист audit_log (заборона UPDATE / DELETE / TRUNCATE);
  * хеш-ланцюжок audit_log (sha256) і функцію перевірки audit_log_verify().

Revision ID: 0001
Revises:
Create Date: 2026-11-03
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ROLES = [
    (1, "CITIZEN", "Громадянин", "Перегляд мапи укриттів, краудсорс-звіт про стан укриття"),
    (2, "COMMANDANT", "Комендант укриття", "Офіційний статус і заповненість закріпленого укриття"),
    (3, "MUNICIPAL_OPERATOR", "Оператор міськради", "Ведення реєстру укриттів, штатна синхронізація"),
    (4, "EMERGENCY_SERVICE", "Екстрена служба (ДСНС)", "Отримання статусів у реальному часі, SOS-режим"),
    (5, "AUDITOR", "Аудитор", "Лише читання журналу аудиту та звітів про доступ"),
    (6, "ADMIN", "Адміністратор", "Керування користувачами та призначення ролей"),
]

POST_SQL = [
    # --- updated_at ---------------------------------------------------------
    """
    CREATE FUNCTION set_updated_at() RETURNS trigger AS $$
    BEGIN
        NEW.updated_at := now();
        RETURN NEW;
    END $$ LANGUAGE plpgsql;
    """,
    "CREATE TRIGGER trg_shelter_updated_at BEFORE UPDATE ON shelter "
    "FOR EACH ROW EXECUTE FUNCTION set_updated_at();",
    "CREATE TRIGGER trg_app_user_updated_at BEFORE UPDATE ON app_user "
    "FOR EACH ROW EXECUTE FUNCTION set_updated_at();",
    # --- audit_log: хеш запису -----------------------------------------------
    # epoch замість тексту дати — щоб хеш не залежав від налаштування TimeZone
    """
    CREATE FUNCTION audit_log_row_hash(prev text, r audit_log) RETURNS text AS $$
        SELECT encode(sha256(convert_to(concat_ws('|',
            quote_nullable(prev),
            quote_nullable(r.id),
            quote_nullable(extract(epoch FROM r.occurred_at)),
            quote_nullable(r.actor_user_id),
            quote_nullable(r.actor_role),
            quote_nullable(r.action),
            quote_nullable(r.entity_type),
            quote_nullable(r.entity_id),
            quote_nullable(r.outcome),
            quote_nullable(r.http_status),
            quote_nullable(r.request_id),
            quote_nullable(r.ip_hash),
            quote_nullable(r.data_classification),
            quote_nullable(r.details::text)
        ), 'UTF8')), 'hex');
    $$ LANGUAGE sql IMMUTABLE;
    """,
    # --- audit_log: ланцюжок при вставці -------------------------------------
    # Advisory lock серіалізує вставки, id береться ПІСЛЯ блокування —
    # тож порядок id завжди збігається з порядком ланцюжка.
    """
    CREATE FUNCTION audit_log_chain() RETURNS trigger AS $$
    DECLARE
        last_hash text;
    BEGIN
        PERFORM pg_advisory_xact_lock(hashtext('audit_log_chain'));
        NEW.id := nextval(pg_get_serial_sequence('audit_log', 'id'));
        NEW.occurred_at := coalesce(NEW.occurred_at, now());
        SELECT hash INTO last_hash FROM audit_log ORDER BY id DESC LIMIT 1;
        NEW.prev_hash := last_hash;
        NEW.hash := audit_log_row_hash(last_hash, NEW);
        RETURN NEW;
    END $$ LANGUAGE plpgsql;
    """,
    "CREATE TRIGGER trg_audit_log_chain BEFORE INSERT ON audit_log "
    "FOR EACH ROW EXECUTE FUNCTION audit_log_chain();",
    # --- audit_log: append-only ----------------------------------------------
    """
    CREATE FUNCTION audit_log_immutable() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'audit_log is append-only: % is not allowed', TG_OP
            USING ERRCODE = 'insufficient_privilege';
    END $$ LANGUAGE plpgsql;
    """,
    "CREATE TRIGGER trg_audit_log_no_modify BEFORE UPDATE OR DELETE ON audit_log "
    "FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();",
    "CREATE TRIGGER trg_audit_log_no_truncate BEFORE TRUNCATE ON audit_log "
    "FOR EACH STATEMENT EXECUTE FUNCTION audit_log_immutable();",
    # --- audit_log: перевірка цілісності -------------------------------------
    # Повертає id першого пошкодженого запису або NULL, якщо ланцюжок цілий.
    """
    CREATE FUNCTION audit_log_verify() RETURNS bigint AS $$
    DECLARE
        r audit_log;
        prev text := NULL;
    BEGIN
        FOR r IN SELECT * FROM audit_log ORDER BY id LOOP
            IF r.prev_hash IS DISTINCT FROM prev
               OR r.hash IS DISTINCT FROM audit_log_row_hash(prev, r) THEN
                RETURN r.id;
            END IF;
            prev := r.hash;
        END LOOP;
        RETURN NULL;
    END $$ LANGUAGE plpgsql STABLE;
    """,
]

DOWN_SQL = [
    "DROP FUNCTION IF EXISTS audit_log_verify();",
    "DROP TRIGGER IF EXISTS trg_audit_log_no_truncate ON audit_log;",
    "DROP TRIGGER IF EXISTS trg_audit_log_no_modify ON audit_log;",
    "DROP TRIGGER IF EXISTS trg_audit_log_chain ON audit_log;",
    "DROP FUNCTION IF EXISTS audit_log_immutable();",
    "DROP FUNCTION IF EXISTS audit_log_chain();",
    "DROP FUNCTION IF EXISTS audit_log_row_hash(text, audit_log);",
    "DROP TRIGGER IF EXISTS trg_app_user_updated_at ON app_user;",
    "DROP TRIGGER IF EXISTS trg_shelter_updated_at ON shelter;",
    "DROP FUNCTION IF EXISTS set_updated_at();",
]


def _seed_roles() -> None:
    role = sa.table(
        "role",
        sa.column("id", sa.SmallInteger),
        sa.column("code", sa.String),
        sa.column("name_uk", sa.String),
        sa.column("description", sa.Text),
    )
    op.bulk_insert(
        role,
        [dict(zip(("id", "code", "name_uk", "description"), r, strict=True)) for r in ROLES],
    )


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('role',
    sa.Column('id', sa.SmallInteger(), nullable=False),
    sa.Column('code', sa.Enum('CITIZEN', 'COMMANDANT', 'MUNICIPAL_OPERATOR', 'EMERGENCY_SERVICE', 'AUDITOR', 'ADMIN', name='role_code', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('name_uk', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_role')),
    sa.UniqueConstraint('code', name=op.f('uq_role_code'))
    )
    op.create_table('shelter',
    sa.Column('registry_id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('address', sa.String(length=500), nullable=False),
    sa.Column('district', sa.String(length=100), nullable=True),
    sa.Column('latitude', sa.Numeric(precision=9, scale=6), nullable=False),
    sa.Column('longitude', sa.Numeric(precision=9, scale=6), nullable=False),
    sa.Column('shelter_type', sa.Enum('PROTECTIVE_STRUCTURE', 'ANTI_RADIATION', 'DUAL_PURPOSE', 'SIMPLE_SHELTER', name='shelter_type', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('capacity', sa.Integer(), nullable=False),
    sa.Column('is_accessible', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('current_status', sa.Enum('OPEN', 'FULL', 'CLOSED', 'UNKNOWN', name='shelter_status', native_enum=False, create_constraint=True, length=32), server_default='UNKNOWN', nullable=False),
    sa.Column('current_occupancy', sa.Integer(), nullable=True),
    sa.Column('status_updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('classification', sa.Enum('PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'RESTRICTED', name='data_classification', native_enum=False, create_constraint=True, length=32), server_default='PUBLIC', nullable=False),
    sa.Column('registry_synced_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('capacity > 0', name=op.f('ck_shelter_capacity_positive')),
    sa.CheckConstraint('current_occupancy IS NULL OR current_occupancy >= 0', name=op.f('ck_shelter_occupancy_non_negative')),
    sa.CheckConstraint('latitude BETWEEN -90 AND 90', name=op.f('ck_shelter_lat_range')),
    sa.CheckConstraint('longitude BETWEEN -180 AND 180', name=op.f('ck_shelter_lon_range')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_shelter')),
    sa.UniqueConstraint('registry_id', name=op.f('uq_shelter_registry_id'))
    )
    op.create_index('ix_shelter_lat_lon', 'shelter', ['latitude', 'longitude'], unique=False)
    op.create_index('ix_shelter_status', 'shelter', ['current_status'], unique=False)
    op.create_table('app_user',
    sa.Column('role_id', sa.SmallInteger(), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('full_name', sa.String(length=200), nullable=True),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('assigned_shelter_id', sa.Uuid(), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['assigned_shelter_id'], ['shelter.id'], name=op.f('fk_app_user_assigned_shelter_id_shelter'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['role_id'], ['role.id'], name=op.f('fk_app_user_role_id_role'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_app_user'))
    )
    op.create_index(op.f('ix_app_user_assigned_shelter_id'), 'app_user', ['assigned_shelter_id'], unique=False)
    op.create_index(op.f('ix_app_user_role_id'), 'app_user', ['role_id'], unique=False)
    op.create_index('uq_app_user_email_lower', 'app_user', [sa.literal_column('lower(email)')], unique=True)
    op.create_table('audit_log',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('actor_user_id', sa.Uuid(), nullable=True),
    sa.Column('actor_role', sa.Enum('CITIZEN', 'COMMANDANT', 'MUNICIPAL_OPERATOR', 'EMERGENCY_SERVICE', 'AUDITOR', 'ADMIN', name='role_code', native_enum=False, create_constraint=True, length=32), nullable=True),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('entity_type', sa.String(length=64), nullable=True),
    sa.Column('entity_id', sa.String(length=64), nullable=True),
    sa.Column('outcome', sa.Enum('SUCCESS', 'DENIED', 'ERROR', name='audit_outcome', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('http_status', sa.SmallInteger(), nullable=True),
    sa.Column('request_id', sa.String(length=64), nullable=True),
    sa.Column('ip_hash', sa.String(length=64), nullable=True),
    sa.Column('data_classification', sa.Enum('PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'RESTRICTED', name='data_classification', native_enum=False, create_constraint=True, length=32), nullable=True),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('prev_hash', sa.String(length=64), nullable=True),
    sa.Column('hash', sa.String(length=64), nullable=False),
    sa.ForeignKeyConstraint(['actor_user_id'], ['app_user.id'], name=op.f('fk_audit_log_actor_user_id_app_user'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_log'))
    )
    op.create_index('ix_audit_log_actor', 'audit_log', ['actor_user_id', 'occurred_at'], unique=False)
    op.create_index('ix_audit_log_entity', 'audit_log', ['entity_type', 'entity_id'], unique=False)
    op.create_index('ix_audit_log_occurred_at', 'audit_log', ['occurred_at'], unique=False)
    op.create_index('ix_audit_log_outcome', 'audit_log', ['outcome', 'occurred_at'], unique=False)
    op.create_table('consent_record',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('purpose', sa.Enum('GEOLOCATION', 'PUSH_NOTIFICATIONS', 'CROWDSOURCE_REPORTING', name='consent_purpose', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('policy_version', sa.String(length=20), nullable=False),
    sa.Column('source', sa.String(length=20), server_default='web', nullable=False),
    sa.Column('granted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint('expires_at IS NULL OR expires_at > granted_at', name=op.f('ck_consent_record_expires_after_granted')),
    sa.CheckConstraint('revoked_at IS NULL OR revoked_at >= granted_at', name=op.f('ck_consent_record_revoked_after_granted')),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_consent_record_user_id_app_user'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_consent_record'))
    )
    op.create_index(op.f('ix_consent_record_user_id'), 'consent_record', ['user_id'], unique=False)
    op.create_index('uq_consent_active_per_purpose', 'consent_record', ['user_id', 'purpose'], unique=True, postgresql_where=sa.text('revoked_at IS NULL'))
    op.create_table('status_report',
    sa.Column('shelter_id', sa.Uuid(), nullable=False),
    sa.Column('reporter_id', sa.Uuid(), nullable=False),
    sa.Column('report_type', sa.Enum('OFFICIAL', 'CROWDSOURCE', name='report_type', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('reported_status', sa.Enum('OPEN', 'FULL', 'CLOSED', 'UNKNOWN', name='shelter_status', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('occupancy', sa.Integer(), nullable=True),
    sa.Column('comment', sa.String(length=500), nullable=True),
    sa.Column('reporter_latitude', sa.Numeric(precision=9, scale=6), nullable=False),
    sa.Column('reporter_longitude', sa.Numeric(precision=9, scale=6), nullable=False),
    sa.Column('distance_m', sa.Numeric(precision=8, scale=1), nullable=True),
    sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('validation_status', sa.Enum('PENDING', 'QUORUM_PENDING', 'ACCEPTED', 'REJECTED', name='validation_status', native_enum=False, create_constraint=True, length=32), server_default='PENDING', nullable=False),
    sa.Column('rejection_code', sa.Enum('GEOLOCATION_OUT_OF_BOUNDS', 'STALE_DATA', 'QUORUM_NOT_REACHED', 'NO_CONSENT', name='rejection_code', native_enum=False, create_constraint=True, length=32), nullable=True),
    sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('classification', sa.Enum('PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'RESTRICTED', name='data_classification', native_enum=False, create_constraint=True, length=32), server_default='CONFIDENTIAL', nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint("(validation_status = 'REJECTED') = (rejection_code IS NOT NULL)", name=op.f('ck_status_report_rejection_code_iff_rejected')),
    sa.CheckConstraint("observed_at <= received_at + interval '1 minute'", name=op.f('ck_status_report_not_from_future')),
    sa.CheckConstraint("validation_status <> 'ACCEPTED' OR (distance_m IS NOT NULL AND distance_m <= 100)", name=op.f('ck_status_report_dq1_accepted_within_radius')),
    sa.CheckConstraint("validation_status <> 'ACCEPTED' OR received_at - observed_at <= interval '30 minutes'", name=op.f('ck_status_report_dq2_accepted_fresh')),
    sa.CheckConstraint('occupancy IS NULL OR occupancy >= 0', name=op.f('ck_status_report_occupancy_non_negative')),
    sa.CheckConstraint('reporter_latitude BETWEEN -90 AND 90', name=op.f('ck_status_report_lat_range')),
    sa.CheckConstraint('reporter_longitude BETWEEN -180 AND 180', name=op.f('ck_status_report_lon_range')),
    sa.ForeignKeyConstraint(['reporter_id'], ['app_user.id'], name=op.f('fk_status_report_reporter_id_app_user'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['shelter_id'], ['shelter.id'], name=op.f('fk_status_report_shelter_id_shelter'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_status_report'))
    )
    op.create_index(op.f('ix_status_report_reporter_id'), 'status_report', ['reporter_id'], unique=False)
    op.create_index('ix_status_report_shelter_received', 'status_report', ['shelter_id', sa.literal_column('received_at DESC')], unique=False)
    # ### end Alembic commands ###

    _seed_roles()
    for statement in POST_SQL:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWN_SQL:
        op.execute(statement)
    op.drop_index('ix_status_report_shelter_received', table_name='status_report')
    op.drop_index(op.f('ix_status_report_reporter_id'), table_name='status_report')
    op.drop_table('status_report')
    op.drop_index('uq_consent_active_per_purpose', table_name='consent_record', postgresql_where=sa.text('revoked_at IS NULL'))
    op.drop_index(op.f('ix_consent_record_user_id'), table_name='consent_record')
    op.drop_table('consent_record')
    op.drop_index('ix_audit_log_outcome', table_name='audit_log')
    op.drop_index('ix_audit_log_occurred_at', table_name='audit_log')
    op.drop_index('ix_audit_log_entity', table_name='audit_log')
    op.drop_index('ix_audit_log_actor', table_name='audit_log')
    op.drop_table('audit_log')
    op.drop_index('uq_app_user_email_lower', table_name='app_user')
    op.drop_index(op.f('ix_app_user_role_id'), table_name='app_user')
    op.drop_index(op.f('ix_app_user_assigned_shelter_id'), table_name='app_user')
    op.drop_table('app_user')
    op.drop_index('ix_shelter_status', table_name='shelter')
    op.drop_index('ix_shelter_lat_lon', table_name='shelter')
    op.drop_table('shelter')
    op.drop_table('role')
    # ### end Alembic commands ###
