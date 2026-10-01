"""phase 2 timekeeping

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-01 18:20:30.309956
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_devices")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_devices_token_hash")),
    )
    op.create_table(
        "holidays",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("recurring", sa.Boolean(), server_default="false", nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_holidays")),
    )
    op.create_index(
        "uq_holidays_date",
        "holidays",
        ["date"],
        unique=True,
        postgresql_where=sa.text("NOT recurring"),
    )
    op.create_index(
        "uq_holidays_recurring_month_day",
        "holidays",
        [
            sa.literal_column("EXTRACT(MONTH FROM date)"),
            sa.literal_column("EXTRACT(DAY FROM date)"),
        ],
        unique=True,
        postgresql_where=sa.text("recurring"),
    )
    op.create_table(
        "hour_bank_entries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.BigInteger(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_admin_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('OPENING_BALANCE', 'COMPENSATION', 'PAYOUT', 'CORRECTION')",
            name=op.f("ck_hour_bank_entries_kind"),
        ),
        sa.CheckConstraint("char_length(reason) >= 10", name=op.f("ck_hour_bank_entries_reason")),
        sa.CheckConstraint("minutes <> 0", name=op.f("ck_hour_bank_entries_minutes")),
        sa.ForeignKeyConstraint(
            ["created_by_admin_id"],
            ["admins.id"],
            name=op.f("fk_hour_bank_entries_created_by_admin_id_admins"),
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name=op.f("fk_hour_bank_entries_employee_id_employees"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hour_bank_entries")),
    )
    op.create_index(
        "ix_hour_bank_entries_employee_date",
        "hour_bank_entries",
        ["employee_id", "entry_date"],
        unique=False,
    )
    op.create_table(
        "time_records",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("workday_date", sa.Date(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("face_match_score", sa.REAL(), nullable=True),
        sa.Column("device_id", sa.BigInteger(), nullable=True),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by_adjustment_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('KIOSK', 'ADJUSTMENT')", name=op.f("ck_time_records_source")
        ),
        sa.CheckConstraint(
            "type IN ('ENTRY', 'LUNCH_EXIT', 'LUNCH_RETURN', 'EXIT')",
            name=op.f("ck_time_records_type"),
        ),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], name=op.f("fk_time_records_device_id_devices")
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["employees.id"], name=op.f("fk_time_records_employee_id_employees")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_time_records")),
    )
    op.create_index(
        "ix_time_records_employee_recorded",
        "time_records",
        ["employee_id", "recorded_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_time_records_workday_date"), "time_records", ["workday_date"], unique=False
    )
    op.create_index(
        "uq_time_records_active_type",
        "time_records",
        ["employee_id", "workday_date", "type"],
        unique=True,
        postgresql_where=sa.text("voided_at IS NULL"),
    )
    op.create_table(
        "time_record_adjustments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("record_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_admin_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('ADD', 'VOID')", name=op.f("ck_time_record_adjustments_kind")),
        sa.CheckConstraint(
            "char_length(reason) >= 10", name=op.f("ck_time_record_adjustments_reason")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_admin_id"],
            ["admins.id"],
            name=op.f("fk_time_record_adjustments_created_by_admin_id_admins"),
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name=op.f("fk_time_record_adjustments_employee_id_employees"),
        ),
        sa.ForeignKeyConstraint(
            ["record_id"],
            ["time_records.id"],
            name=op.f("fk_time_record_adjustments_record_id_time_records"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_time_record_adjustments")),
    )
    op.create_index(
        op.f("ix_time_record_adjustments_employee_id"),
        "time_record_adjustments",
        ["employee_id"],
        unique=False,
    )
    # Referência circular (registro anulado -> ajuste que o anulou): criada depois das duas tabelas.
    op.create_foreign_key(
        op.f("fk_time_records_voided_by_adjustment_id_time_record_adjustments"),
        "time_records",
        "time_record_adjustments",
        ["voided_by_adjustment_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_audit_logs_actor_device_id_devices"),
        "audit_logs",
        "devices",
        ["actor_device_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_audit_logs_actor_device_id_devices"), "audit_logs", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("fk_time_records_voided_by_adjustment_id_time_record_adjustments"),
        "time_records",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_time_record_adjustments_employee_id"), table_name="time_record_adjustments"
    )
    op.drop_table("time_record_adjustments")
    op.drop_index(
        "uq_time_records_active_type",
        table_name="time_records",
        postgresql_where=sa.text("voided_at IS NULL"),
    )
    op.drop_index(op.f("ix_time_records_workday_date"), table_name="time_records")
    op.drop_index("ix_time_records_employee_recorded", table_name="time_records")
    op.drop_table("time_records")
    op.drop_index("ix_hour_bank_entries_employee_date", table_name="hour_bank_entries")
    op.drop_table("hour_bank_entries")
    op.drop_index(
        "uq_holidays_recurring_month_day",
        table_name="holidays",
        postgresql_where=sa.text("recurring"),
    )
    op.drop_index(
        "uq_holidays_date", table_name="holidays", postgresql_where=sa.text("NOT recurring")
    )
    op.drop_table("holidays")
    op.drop_table("devices")
