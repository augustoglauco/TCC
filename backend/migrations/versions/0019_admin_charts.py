"""admin charts table

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-04

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JsonVariant = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "admin_charts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("titulo", sa.String(length=255), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("tipo_grafico", sa.String(length=50), nullable=False),
        sa.Column("config_json", _JsonVariant, nullable=False),
        sa.Column("dados_json", _JsonVariant, nullable=False),
        sa.Column("sql_query", sa.Text(), nullable=True),
        sa.Column("fixado", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("ordem", sa.Integer(), server_default="0", nullable=False),
        sa.Column("criado_por", sa.String(length=255), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_admin_charts_fixado", "admin_charts", ["fixado"])
    op.create_index("idx_admin_charts_criado_em", "admin_charts", ["criado_em"])
    op.create_index("idx_admin_charts_ordem", "admin_charts", ["ordem"])


def downgrade() -> None:
    op.drop_index("idx_admin_charts_ordem", table_name="admin_charts")
    op.drop_index("idx_admin_charts_criado_em", table_name="admin_charts")
    op.drop_index("idx_admin_charts_fixado", table_name="admin_charts")
    op.drop_table("admin_charts")
