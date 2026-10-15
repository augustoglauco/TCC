"""produtos.dias_alerta_estoque (horizonte do alerta de estoque por produto, R13)

Ver decisão de 2026-10-15 em docs/ARCHITECTURE.md. Nulo = usa o padrão global.

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("produtos", sa.Column("dias_alerta_estoque", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("produtos", "dias_alerta_estoque")
