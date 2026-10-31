"""agente_execucoes (uma linha por avaliação do agente de estoque, R13)

Permite ao catálogo mostrar que o agente está vivo mesmo quando não há alerta.

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agente_execucoes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("agente", sa.String(50), nullable=False),
        sa.Column("modo", sa.String(20), nullable=False),
        sa.Column("produtos_avaliados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("alertas_criados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("idx_agente_execucoes_agente", "agente_execucoes", ["agente"])
    op.create_index("idx_agente_execucoes_criado_em", "agente_execucoes", ["criado_em"])


def downgrade() -> None:
    op.drop_index("idx_agente_execucoes_criado_em", table_name="agente_execucoes")
    op.drop_index("idx_agente_execucoes_agente", table_name="agente_execucoes")
    op.drop_table("agente_execucoes")
