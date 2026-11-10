"""Статуси укриттів і кворум краудсорс-звітів (SG-21).

  * role.report_weight — вага звіту для кворуму DQ-3 (поріг 3);
  * status_report.weight — вага, з якою звіт зараховано;
  * координати репортера стають необов'язковими: API зберігає лише виміряну
    відстань, сирі GPS не зберігаються (мінімізація даних, SG-2);
  * DQ-1 на рівні БД стосується лише краудсорс-звітів: офіційний статус
    коменданта чи оператора ДСНС геоприв'язки не потребує;
  * новий стан звіту EXPIRED — кворум не зібрано вчасно.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-11
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WEIGHTS = {
    "CITIZEN": 1,
    "VERIFIED_VOLUNTEER": 3,
    "SHELTER_MANAGER": 3,
    "DSNS_OPERATOR": 3,
}
DQ1 = "ck_status_report_dq1_accepted_within_radius"
VSTATUS = "ck_status_report_validation_status"
OLD_STATES = "('PENDING', 'QUORUM_PENDING', 'ACCEPTED', 'REJECTED')"
NEW_STATES = "('PENDING', 'QUORUM_PENDING', 'ACCEPTED', 'REJECTED', 'EXPIRED')"


def upgrade() -> None:
    op.add_column(
        "role",
        sa.Column("report_weight", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
    )
    for code, weight in WEIGHTS.items():
        op.execute(
            sa.text("UPDATE role SET report_weight = :w WHERE code = :c").bindparams(
                w=weight, c=code
            )
        )

    op.add_column(
        "status_report",
        sa.Column("weight", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
    )
    op.alter_column("status_report", "reporter_latitude", nullable=True)
    op.alter_column("status_report", "reporter_longitude", nullable=True)

    op.execute(f"ALTER TABLE status_report DROP CONSTRAINT {DQ1}")
    op.execute(
        f"ALTER TABLE status_report ADD CONSTRAINT {DQ1} CHECK ("
        "validation_status <> 'ACCEPTED' OR report_type = 'OFFICIAL' "
        "OR (distance_m IS NOT NULL AND distance_m <= 100))"
    )
    op.execute(f"ALTER TABLE status_report DROP CONSTRAINT {VSTATUS}")
    op.execute(
        f"ALTER TABLE status_report ADD CONSTRAINT {VSTATUS} "
        f"CHECK (validation_status IN {NEW_STATES})"
    )


def downgrade() -> None:
    bind = op.get_bind()
    blocking = bind.execute(
        sa.text(
            "SELECT count(*) FROM status_report WHERE reporter_latitude IS NULL "
            "OR reporter_longitude IS NULL OR validation_status = 'EXPIRED' "
            "OR (validation_status = 'ACCEPTED' AND distance_m IS NULL)"
        )
    ).scalar()
    if blocking:
        raise RuntimeError(
            f"Відкат 0003 зупинено: {blocking} звітів не відповідають схемі 0002 "
            "(без координат, EXPIRED або офіційні без відстані)."
        )

    op.execute(f"ALTER TABLE status_report DROP CONSTRAINT {VSTATUS}")
    op.execute(
        f"ALTER TABLE status_report ADD CONSTRAINT {VSTATUS} "
        f"CHECK (validation_status IN {OLD_STATES})"
    )
    op.execute(f"ALTER TABLE status_report DROP CONSTRAINT {DQ1}")
    op.execute(
        f"ALTER TABLE status_report ADD CONSTRAINT {DQ1} CHECK ("
        "validation_status <> 'ACCEPTED' OR (distance_m IS NOT NULL AND distance_m <= 100))"
    )
    op.alter_column("status_report", "reporter_longitude", nullable=False)
    op.alter_column("status_report", "reporter_latitude", nullable=False)
    op.drop_column("status_report", "weight")
    op.drop_column("role", "report_weight")
