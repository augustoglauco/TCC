"""atendimento humano e transbordo

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-05

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversas", sa.Column("atendente_id", sa.String(length=100), nullable=True))
    op.add_column("conversas", sa.Column("atendente_nome", sa.String(length=100), nullable=True))
    op.add_column("conversas", sa.Column("motivo_escalonamento", sa.String(length=100), nullable=True))
    op.add_column("conversas", sa.Column("prioridade", sa.Integer(), server_default="1", nullable=False))
    op.add_column("conversas", sa.Column("escalado_em", sa.DateTime(timezone=True), nullable=True))
    op.create_index("idx_conversas_fila_atendimento", "conversas", ["status", "prioridade", "escalado_em"])
    op.create_index("idx_conversas_atendente_id", "conversas", ["atendente_id"])

    op.add_column("conversa_mensagens", sa.Column("atendente_nome", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("conversa_mensagens", "atendente_nome")
    op.drop_index("idx_conversas_atendente_id", table_name="conversas")
    op.drop_index("idx_conversas_fila_atendimento", table_name="conversas")
    op.drop_column("conversas", "escalado_em")
    op.drop_column("conversas", "prioridade")
    op.drop_column("conversas", "motivo_escalonamento")
    op.drop_column("conversas", "atendente_nome")
    op.drop_column("conversas", "atendente_id")
