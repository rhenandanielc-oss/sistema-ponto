"""alternating weeks with two days off

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-06 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Só acrescenta uma coluna vazia: nenhum dado existente é alterado.
    op.add_column("employee_schedules", sa.Column("double_off_week", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("employee_schedules", "double_off_week")
