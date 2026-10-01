"""immutable history: audit, records, adjustments and hour bank entries

O banco recusa UPDATE/DELETE nas tabelas de histórico, mesmo que a aplicação (ou alguém com acesso
ao usuário da aplicação) tente. Em `time_records` a única alteração aceita é anular uma batida ainda
não anulada (preencher `voided_at` e `voided_by_adjustment_id`), feita pelo serviço de ajustes.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-01 21:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPEND_ONLY = ("audit_logs", "time_record_adjustments", "hour_bank_entries")


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION forbid_history_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '% em % não é permitido: o histórico é imutável', TG_OP, TG_TABLE_NAME
                USING ERRCODE = 'insufficient_privilege';
        END;
        $$
        """
    )
    for table in APPEND_ONLY:
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION forbid_history_change()"
        )

    op.execute(
        """
        CREATE FUNCTION time_records_only_void() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.voided_at IS NULL
               AND NEW.voided_at IS NOT NULL
               AND NEW.voided_by_adjustment_id IS NOT NULL
               AND (to_jsonb(NEW) - 'voided_at' - 'voided_by_adjustment_id')
                   = (to_jsonb(OLD) - 'voided_at' - 'voided_by_adjustment_id') THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'batidas são imutáveis: só é permitido anular por ajuste'
                USING ERRCODE = 'insufficient_privilege';
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER time_records_only_void BEFORE UPDATE ON time_records "
        "FOR EACH ROW EXECUTE FUNCTION time_records_only_void()"
    )
    op.execute(
        "CREATE TRIGGER time_records_no_delete BEFORE DELETE ON time_records "
        "FOR EACH ROW EXECUTE FUNCTION forbid_history_change()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER time_records_no_delete ON time_records")
    op.execute("DROP TRIGGER time_records_only_void ON time_records")
    op.execute("DROP FUNCTION time_records_only_void()")
    for table in APPEND_ONLY:
        op.execute(f"DROP TRIGGER {table}_immutable ON {table}")
    op.execute("DROP FUNCTION forbid_history_change()")
