"""employee consumption

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-04 15:18:33.008969
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "consumption_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("price_cents > 0", name=op.f("ck_consumption_items_price")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consumption_items")),
    )
    op.create_index(
        "uq_consumption_items_name",
        "consumption_items",
        [sa.literal_column("lower(name)")],
        unique=True,
    )
    op.create_table(
        "consumption_entries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.BigInteger(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.Column("created_by_admin_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_by_admin_id", sa.BigInteger(), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(canceled_at IS NULL) = (cancel_reason IS NULL)",
            name=op.f("ck_consumption_entries_cancel_consistency"),
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_consumption_entries_quantity")),
        sa.CheckConstraint("unit_price_cents > 0", name=op.f("ck_consumption_entries_unit_price")),
        sa.ForeignKeyConstraint(
            ["canceled_by_admin_id"],
            ["admins.id"],
            name=op.f("fk_consumption_entries_canceled_by_admin_id_admins"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_admin_id"],
            ["admins.id"],
            name=op.f("fk_consumption_entries_created_by_admin_id_admins"),
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name=op.f("fk_consumption_entries_employee_id_employees"),
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["consumption_items.id"],
            name=op.f("fk_consumption_entries_item_id_consumption_items"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consumption_entries")),
    )
    op.create_index(
        "ix_consumption_entries_employee_date",
        "consumption_entries",
        ["employee_id", "entry_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_consumption_entries_employee_date", table_name="consumption_entries")
    op.drop_table("consumption_entries")
    op.drop_index("uq_consumption_items_name", table_name="consumption_items")
    op.drop_table("consumption_items")
