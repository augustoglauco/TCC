"""ai usage events table

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-08

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("origem", sa.String(length=50), nullable=False),
        sa.Column("ambiente", sa.String(length=20), nullable=False),
        sa.Column("modelo", sa.String(length=100), nullable=False),
        sa.Column("operacao", sa.String(length=100), nullable=False),
        sa.Column("tokens_entrada", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tokens_saida", sa.Integer(), server_default="0", nullable=False),
        sa.Column("custo_usd", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("referencia_id", sa.String(length=500), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_ai_usage_events_origem", "ai_usage_events", ["origem"])
    op.create_index("idx_ai_usage_events_operacao", "ai_usage_events", ["operacao"])
    op.create_index("idx_ai_usage_events_criado_em", "ai_usage_events", ["criado_em"])


def downgrade() -> None:
    op.drop_index("idx_ai_usage_events_criado_em", table_name="ai_usage_events")
    op.drop_index("idx_ai_usage_events_operacao", table_name="ai_usage_events")
    op.drop_index("idx_ai_usage_events_origem", table_name="ai_usage_events")
    op.drop_table("ai_usage_events")
