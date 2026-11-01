"""chat_admin_acoes (propostas e auditoria das ferramentas do Admin no chat)

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_admin_acoes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("admin_id", sa.Integer(), nullable=False),
        sa.Column("ferramenta", sa.String(50), nullable=False),
        sa.Column("argumentos", sa.JSON(), nullable=False),
        sa.Column("antes", sa.JSON(), nullable=True),
        sa.Column("depois", sa.JSON(), nullable=True),
        sa.Column("aviso", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="proposta"),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executado_em", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_chat_admin_acoes_admin_id", "chat_admin_acoes", ["admin_id"])
    op.create_index("idx_chat_admin_acoes_status", "chat_admin_acoes", ["status"])


def downgrade() -> None:
    op.drop_index("idx_chat_admin_acoes_status", table_name="chat_admin_acoes")
    op.drop_index("idx_chat_admin_acoes_admin_id", table_name="chat_admin_acoes")
    op.drop_table("chat_admin_acoes")
