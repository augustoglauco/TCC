"""conversas status e custos

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversas", sa.Column("status", sa.String(length=20), server_default="aberta", nullable=False))
    op.add_column("conversas", sa.Column("encerrada_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("conversas", sa.Column("motivo_encerramento", sa.String(length=50), nullable=True))
    op.create_index("idx_conversas_status", "conversas", ["status"])
    op.create_index("idx_conversas_encerrada_em", "conversas", ["encerrada_em"])


def downgrade() -> None:
    op.drop_index("idx_conversas_encerrada_em", table_name="conversas")
    op.drop_index("idx_conversas_status", table_name="conversas")
    op.drop_column("conversas", "motivo_encerramento")
    op.drop_column("conversas", "encerrada_em")
    op.drop_column("conversas", "status")
