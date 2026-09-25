"""preco_base_fornecedor e produto_imagens (Gestao de Produtos)

Adiciona preco_base_fornecedor e imagem_url na tabela produtos, e cria a tabela
produto_imagens para associacao de fotos fisicas e vetores do Qdrant CLIP.
Ver spec docs/superpowers/specs/2026-09-25-admin-produtos-catalogo-design.md.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "produtos",
        sa.Column("preco_base_fornecedor", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "produtos",
        sa.Column("imagem_url", sa.String(500), nullable=True),
    )
    op.create_table(
        "produto_imagens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "produto_id",
            sa.Integer(),
            sa.ForeignKey("produtos.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("imagem_url", sa.String(500), nullable=False),
        sa.Column("clip_image_id", sa.String(64), nullable=True),
        sa.Column("is_principal", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("produto_imagens")
    op.drop_column("produtos", "imagem_url")
    op.drop_column("produtos", "preco_base_fornecedor")
