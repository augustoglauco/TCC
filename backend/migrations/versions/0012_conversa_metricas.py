"""metricas em conversa_mensagens (R9, Fase 6)

Guarda o conteúdo do evento `done` de cada resposta do assistente, para o
painel de métricas reaparecer nas mensagens recarregadas pelo widget. Ver
decisão de 2026-09-25 em docs/ARCHITECTURE.md §5.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-25

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversa_mensagens",
        sa.Column(
            "metricas", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("conversa_mensagens", "metricas")
