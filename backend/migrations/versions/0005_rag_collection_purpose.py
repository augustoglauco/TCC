"""add purpose to rag_collections (ingestão restrita ao MCP B2B)

# MVP: segmenta conteúdo restrito ao canal MCP B2B numa collection dedicada
(`purpose="mcp_b2b"`), que nunca é ativada nem buscada pelo chat público —
ver docs/superpowers/specs/2026-09-21-ingestao-mcp-b2b-design.md §3.

A coluna nasce com server_default 'chat' para que todas as collections já
existentes fiquem como 'chat' (comportamento atual preservado); o
server_default é removido em seguida para que novas linhas sejam controladas
pela aplicação (mesmo critério das demais colunas de rag_collections).

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "rag_collections",
        sa.Column("purpose", sa.String(), nullable=False, server_default="chat"),
    )
    # Remove o server_default depois do backfill implícito das linhas
    # existentes — novas linhas passam a receber o valor pela aplicação.
    op.alter_column("rag_collections", "purpose", server_default=None)


def downgrade() -> None:
    op.drop_column("rag_collections", "purpose")
