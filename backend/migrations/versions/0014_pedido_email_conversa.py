"""adiciona user_email e conversation_id à tabela pedidos (R12, Fase 7)

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("pedidos", sa.Column("user_email", sa.String(), nullable=True))
    op.add_column("pedidos", sa.Column("conversation_id", sa.String(), nullable=True))
    op.create_index("ix_pedidos_user_email", "pedidos", ["user_email"])
    op.create_index("ix_pedidos_conversation_id", "pedidos", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_pedidos_conversation_id", table_name="pedidos")
    op.drop_index("ix_pedidos_user_email", table_name="pedidos")
    op.drop_column("pedidos", "conversation_id")
    op.drop_column("pedidos", "user_email")
