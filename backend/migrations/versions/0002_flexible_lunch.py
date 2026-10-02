"""almoço livre: horário fixo guarda só entrada, saída e duração do almoço

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "employee_schedule_days",
        sa.Column("lunch_minutes", sa.SmallInteger(), server_default="60", nullable=False),
    )
    # Preserva a duração de almoços cadastrados com horário fixo.
    op.execute(
        """
        UPDATE employee_schedule_days
        SET lunch_minutes = CASE
            WHEN lunch_start IS NULL THEN 0
            ELSE (EXTRACT(EPOCH FROM (lunch_end - lunch_start))::int / 60 + 1440) % 1440
        END
        """
    )
    op.drop_constraint("lunch_pair", "employee_schedule_days", type_="check")
    op.drop_column("employee_schedule_days", "lunch_start")
    op.drop_column("employee_schedule_days", "lunch_end")
    op.create_check_constraint("lunch_minutes", "employee_schedule_days", "lunch_minutes >= 0")


def downgrade() -> None:
    op.drop_constraint("lunch_minutes", "employee_schedule_days", type_="check")
    op.add_column("employee_schedule_days", sa.Column("lunch_start", sa.Time(), nullable=True))
    op.add_column("employee_schedule_days", sa.Column("lunch_end", sa.Time(), nullable=True))
    op.create_check_constraint(
        "lunch_pair",
        "employee_schedule_days",
        "(lunch_start IS NULL) = (lunch_end IS NULL)",
    )
    op.drop_column("employee_schedule_days", "lunch_minutes")
