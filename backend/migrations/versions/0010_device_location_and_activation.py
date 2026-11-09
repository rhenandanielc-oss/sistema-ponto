"""device: location check and one-time activation link

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-09 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Só acrescenta colunas (com padrão): nenhum dado existente é alterado.
    op.add_column(
        "devices",
        sa.Column("require_location", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("devices", sa.Column("activation_hash", sa.Text(), nullable=True))
    op.add_column(
        "devices", sa.Column("activation_expires_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("devices", "activation_expires_at")
    op.drop_column("devices", "activation_hash")
    op.drop_column("devices", "require_location")
