"""create crawler_pending_pages (R4 - crawler de páginas)

# MVP: fila de revisão humana para páginas cuja classificação de domínio
teve confiança abaixo do limiar configurado — ver
docs/superpowers/specs/2026-09-19-crawler-paginas-design.md.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-19

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "crawler_pending_pages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("url", sa.String(), nullable=False, unique=True),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("domain_proposed", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("crawler_pending_pages")
