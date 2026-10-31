"""produtos.familia (agrupa modelos do mesmo produto; só cadastro e API)

Ver decisão de 2026-10-31 em docs/ARCHITECTURE.md. Nulo = produto sem família.

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("produtos", sa.Column("familia", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("produtos", "familia")
