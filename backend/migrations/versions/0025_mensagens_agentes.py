"""mensagens_agentes (caixa de entrada dos agentes autônomos, R13)

Ver decisão de 2026-10-15 em docs/ARCHITECTURE.md.

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mensagens_agentes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("agente", sa.String(length=100), nullable=False),
        sa.Column("tipo", sa.String(length=50), nullable=False),
        sa.Column("severidade", sa.String(length=20), nullable=False),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("corpo", sa.Text(), nullable=False),
        sa.Column("dados", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True),
        sa.Column("chave_dedupe", sa.String(length=200), nullable=True),
        sa.Column("lida", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("email_status", sa.String(length=30), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("idx_mensagens_agentes_agente", "mensagens_agentes", ["agente"])
    op.create_index("idx_mensagens_agentes_lida", "mensagens_agentes", ["lida"])
    op.create_index("idx_mensagens_agentes_criado_em", "mensagens_agentes", ["criado_em"])
    op.create_index("idx_mensagens_agentes_dedupe", "mensagens_agentes", ["chave_dedupe"])


def downgrade() -> None:
    op.drop_index("idx_mensagens_agentes_dedupe", table_name="mensagens_agentes")
    op.drop_index("idx_mensagens_agentes_criado_em", table_name="mensagens_agentes")
    op.drop_index("idx_mensagens_agentes_lida", table_name="mensagens_agentes")
    op.drop_index("idx_mensagens_agentes_agente", table_name="mensagens_agentes")
    op.drop_table("mensagens_agentes")
