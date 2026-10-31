"""crawler_pending_pages.collection_id (collection escolhida no crawl)

Nulo = a collection ativa de chat na hora da aprovação, como antes.

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "crawler_pending_pages",
        sa.Column(
            "collection_id",
            sa.Uuid(),
            sa.ForeignKey("rag_collections.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("crawler_pending_pages", "collection_id")
