"""conversao de reserva em venda com comprovante multimodal
 
Revision ID: 0022
Revises: 0021
Create Date: 2026-10-05
 
"""
from collections.abc import Sequence
 
import sqlalchemy as sa
from alembic import op
 
revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
 
 
def upgrade() -> None:
    op.add_column("pedidos", sa.Column("comprovante_url", sa.String(length=255), nullable=True))
    op.add_column("pedidos", sa.Column("tipo_conversao", sa.String(length=50), nullable=True))
    op.add_column("pedidos", sa.Column("convertido_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("pedidos", sa.Column("convertido_por", sa.String(length=100), nullable=True))
    op.add_column("pedidos", sa.Column("llm_parecer", sa.Text(), nullable=True))
    op.create_index("ix_pedidos_status", "pedidos", ["status"])
 
 
def downgrade() -> None:
    op.drop_index("ix_pedidos_status", table_name="pedidos")
    op.drop_column("pedidos", "llm_parecer")
    op.drop_column("pedidos", "convertido_por")
    op.drop_column("pedidos", "convertido_em")
    op.drop_column("pedidos", "tipo_conversao")
    op.drop_column("pedidos", "comprovante_url")
