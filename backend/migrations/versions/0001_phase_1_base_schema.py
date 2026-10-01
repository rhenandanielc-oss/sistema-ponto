"""phase 1 base schema

Revision ID: 0001
Revises:
Create Date: 2026-10-01 17:56:34.207894
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Necessária para a restrição EXCLUDE de vigências.
    # btree_gist é "trusted": o dono do banco pode criar sem superusuário.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.create_table(
        "admins",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("failed_login_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admins")),
    )
    op.create_index(
        "uq_admins_email_lower", "admins", [sa.literal_column("lower(email)")], unique=True
    )
    op.create_table(
        "employees",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("registration_number", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("cpf", sa.Text(), nullable=True),
        sa.Column("hire_date", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("status", sa.Text(), server_default="ACTIVE", nullable=False),
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
        sa.CheckConstraint(
            "cpf IS NULL OR cpf ~ '^[0-9]{11}$'", name=op.f("ck_employees_cpf_digits")
        ),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name=op.f("ck_employees_status")),
        sa.CheckConstraint(
            "termination_date IS NULL OR termination_date >= hire_date",
            name=op.f("ck_employees_termination_date"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_employees")),
        sa.UniqueConstraint("cpf", name=op.f("uq_employees_cpf")),
        sa.UniqueConstraint("registration_number", name=op.f("uq_employees_registration_number")),
    )
    op.create_index(
        "ix_employees_name_lower", "employees", [sa.literal_column("lower(name)")], unique=False
    )
    op.create_index(op.f("ix_employees_status"), "employees", ["status"], unique=False)
    op.create_table(
        "settings",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_settings")),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("actor_admin_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_device_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_employee_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=True),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["actor_admin_id"], ["admins.id"], name=op.f("fk_audit_logs_actor_admin_id_admins")
        ),
        sa.ForeignKeyConstraint(
            ["actor_employee_id"],
            ["employees.id"],
            name=op.f("fk_audit_logs_actor_employee_id_employees"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(
        "ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"], unique=False
    )
    op.create_index(op.f("ix_audit_logs_occurred_at"), "audit_logs", ["occurred_at"], unique=False)
    op.create_table(
        "employee_schedules",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.BigInteger(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("created_by_admin_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from",
            name=op.f("ck_employee_schedules_valid_range"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_admin_id"],
            ["admins.id"],
            name=op.f("fk_employee_schedules_created_by_admin_id_admins"),
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name=op.f("fk_employee_schedules_employee_id_employees"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_employee_schedules")),
    )
    op.create_index(
        op.f("ix_employee_schedules_employee_id"),
        "employee_schedules",
        ["employee_id"],
        unique=False,
    )
    # Vigências de horário do mesmo funcionário não podem se sobrepor (DATABASE.md §3).
    op.execute(
        "ALTER TABLE employee_schedules ADD CONSTRAINT ex_employee_schedules_no_overlap "
        "EXCLUDE USING gist (employee_id WITH =, daterange(valid_from, valid_to, '[]') WITH &&)"
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("admin_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("family_id", sa.UUID(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["admin_id"],
            ["admins.id"],
            name=op.f("fk_refresh_tokens_admin_id_admins"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index(
        op.f("ix_refresh_tokens_admin_id"), "refresh_tokens", ["admin_id"], unique=False
    )
    op.create_index(
        op.f("ix_refresh_tokens_family_id"), "refresh_tokens", ["family_id"], unique=False
    )
    op.create_table(
        "employee_schedule_days",
        sa.Column("schedule_id", sa.BigInteger(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("lunch_start", sa.Time(), nullable=True),
        sa.Column("lunch_end", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.CheckConstraint(
            "(lunch_start IS NULL) = (lunch_end IS NULL)",
            name=op.f("ck_employee_schedule_days_lunch_pair"),
        ),
        sa.CheckConstraint(
            "weekday BETWEEN 0 AND 6", name=op.f("ck_employee_schedule_days_weekday")
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["employee_schedules.id"],
            name=op.f("fk_employee_schedule_days_schedule_id_employee_schedules"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("schedule_id", "weekday", name=op.f("pk_employee_schedule_days")),
    )


def downgrade() -> None:
    op.drop_table("employee_schedule_days")
    op.drop_index(op.f("ix_refresh_tokens_family_id"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_admin_id"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index(op.f("ix_employee_schedules_employee_id"), table_name="employee_schedules")
    op.drop_table("employee_schedules")
    op.drop_index(op.f("ix_audit_logs_occurred_at"), table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("settings")
    op.drop_index(op.f("ix_employees_status"), table_name="employees")
    op.drop_index("ix_employees_name_lower", table_name="employees")
    op.drop_table("employees")
    op.drop_index("uq_admins_email_lower", table_name="admins")
    op.drop_table("admins")
