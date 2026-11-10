"""device: permanent link version

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-10 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Só acrescenta uma coluna com padrão: nenhum terminal existente é alterado.
    op.add_column(
        "devices", sa.Column("link_version", sa.Integer(), server_default="0", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("devices", "link_version")
