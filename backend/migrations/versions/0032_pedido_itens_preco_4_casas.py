"""pedido_itens.preco_unitario com 4 casas (reserva com desconto por volume)

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # O preço unitário com desconto por volume (ex.: 129,90 x 0,95 = 123,405)
    # não cabe em 2 casas; arredondar por unidade faria o total da reserva
    # divergir do subtotal da cotação.
    op.alter_column(
        "pedido_itens",
        "preco_unitario",
        existing_type=sa.Numeric(10, 2),
        type_=sa.Numeric(12, 4),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "pedido_itens",
        "preco_unitario",
        existing_type=sa.Numeric(12, 4),
        type_=sa.Numeric(10, 2),
        existing_nullable=False,
    )
