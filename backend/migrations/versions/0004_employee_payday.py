"""dia do pagamento do funcionário

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Funcionários já cadastrados recebem dia 5; o administrador ajusta no cadastro.
    op.add_column(
        "employees", sa.Column("payday", sa.SmallInteger(), server_default="5", nullable=False)
    )
    op.alter_column("employees", "payday", server_default=None)
    op.create_check_constraint("payday", "employees", "payday BETWEEN 1 AND 31")


def downgrade() -> None:
    op.drop_constraint("payday", "employees", type_="check")
    op.drop_column("employees", "payday")
