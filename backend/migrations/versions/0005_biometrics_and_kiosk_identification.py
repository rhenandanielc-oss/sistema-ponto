"""biometrics and kiosk identification

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-01 19:39:33.259269
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "biometric_consents",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.BigInteger(), nullable=False),
        sa.Column("term_version", sa.Text(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_by_admin_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name=op.f("fk_biometric_consents_employee_id_employees"),
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_admin_id"],
            ["admins.id"],
            name=op.f("fk_biometric_consents_recorded_by_admin_id_admins"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_biometric_consents")),
    )
    op.create_index(
        "uq_biometric_consents_active",
        "biometric_consents",
        ["employee_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_table(
        "biometric_templates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.BigInteger(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("key_id", sa.Text(), nullable=False),
        sa.Column("quality_score", sa.REAL(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name=op.f("fk_biometric_templates_employee_id_employees"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_biometric_templates")),
    )
    op.create_index(
        "ix_biometric_templates_active",
        "biometric_templates",
        ["employee_id"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "kiosk_identifications",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("employee_id", sa.BigInteger(), nullable=False),
        sa.Column("device_id", sa.BigInteger(), nullable=False),
        sa.Column("score", sa.REAL(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], name=op.f("fk_kiosk_identifications_device_id_devices")
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name=op.f("fk_kiosk_identifications_employee_id_employees"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kiosk_identifications")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_kiosk_identifications_token_hash")),
    )


def downgrade() -> None:
    op.drop_table("kiosk_identifications")
    op.drop_index(
        "ix_biometric_templates_active",
        table_name="biometric_templates",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_table("biometric_templates")
    op.drop_index(
        "uq_biometric_consents_active",
        table_name="biometric_consents",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.drop_table("biometric_consents")
