"""chaves_parceiro: chaves de acesso ao MCP B2B geradas pelo Admin (só o hash)

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chaves_parceiro",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=False),
        sa.Column("prefixo", sa.String(length=16), nullable=False),
        sa.Column("chave_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "criada_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("revogada_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chaves_parceiro_cliente_id"), "chaves_parceiro", ["cliente_id"])
    op.create_index(
        op.f("ix_chaves_parceiro_chave_hash"), "chaves_parceiro", ["chave_hash"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_chaves_parceiro_chave_hash"), table_name="chaves_parceiro")
    op.drop_index(op.f("ix_chaves_parceiro_cliente_id"), table_name="chaves_parceiro")
    op.drop_table("chaves_parceiro")
