"""conversas.status para varchar(50) (achado de 2026-10-06)

A coluna foi criada em VARCHAR(20) na migração 0018, quando os únicos
valores em uso eram "aberta"/"encerrada". A 0021 (atendimento humano)
introduziu "em_atendimento_humano" (21 caracteres) sem alargar a coluna —
`app.db.models.Conversa.status` já declarava `String(50)` desde então (model
e schema do banco divergentes), mas sem esta migração todo `POST
/api/admin/atendimento/{id}/claim` quebrava com
`StringDataRightTruncationError` no UPDATE que grava o novo status, um 500
sem corpo JSON que o navegador relata como "Failed to fetch" (sem cabeçalhos
CORS numa resposta de erro não tratada).

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-07

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "conversas",
        "status",
        existing_type=sa.String(length=20),
        type_=sa.String(length=50),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "conversas",
        "status",
        existing_type=sa.String(length=50),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
