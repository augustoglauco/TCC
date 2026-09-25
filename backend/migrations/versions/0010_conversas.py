"""conversas e conversa_mensagens (memória da conversa, R9, Fase 6)

Ver decisão de 2026-09-25 em docs/ARCHITECTURE.md §5. Substitui o histórico
em memória de app.api.chat. As colunas email/perfil/perfil_motivo de
`conversas` são da classificação do usuário (R10).

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-25

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversas",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "criada_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "atualizada_em",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resumo", sa.String(), nullable=True),
        sa.Column("mensagens_resumidas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("perfil", sa.String(), nullable=True),
        sa.Column("perfil_motivo", sa.String(), nullable=True),
    )
    op.create_table(
        "conversa_mensagens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversa_id", sa.String(), sa.ForeignKey("conversas.id"), nullable=False),
        sa.Column("papel", sa.String(), nullable=False),
        sa.Column("texto", sa.String(), nullable=False),
        sa.Column("dominio", sa.String(), nullable=True),
        sa.Column(
            "criada_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_conversa_mensagens_conversa_id", "conversa_mensagens", ["conversa_id"])


def downgrade() -> None:
    op.drop_index("ix_conversa_mensagens_conversa_id", table_name="conversa_mensagens")
    op.drop_table("conversa_mensagens")
    op.drop_table("conversas")
