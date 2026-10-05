"""ingestion cost events table

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-04

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_cost_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_identifier", sa.String(length=500), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completion_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cost_prompt_usd", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("cost_completion_usd", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("total_cost_usd", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_ingestion_cost_events_source_type", "ingestion_cost_events", ["source_type"])
    op.create_index("idx_ingestion_cost_events_criado_em", "ingestion_cost_events", ["criado_em"])


def downgrade() -> None:
    op.drop_index("idx_ingestion_cost_events_criado_em", table_name="ingestion_cost_events")
    op.drop_index("idx_ingestion_cost_events_source_type", table_name="ingestion_cost_events")
    op.drop_table("ingestion_cost_events")
