"""tom_escalonamentos (Monitor de Tom, R8, Fase 4B)

Ver docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md §5. Tabela
append-only — sem coluna de atualização, cada linha é uma escalada.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tom_escalonamentos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.String(), nullable=False),
        sa.Column("mensagem", sa.String(), nullable=False),
        sa.Column("motivo", sa.String(), nullable=True),
        sa.Column("confianca", sa.Float(), nullable=False),
        sa.Column("provider_efetivo", sa.String(), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("tom_escalonamentos")
