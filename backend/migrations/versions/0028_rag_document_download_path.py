"""rag_documents.download_path (arquivo que o cliente baixa, separado do ingerido)

Ver decisão de 2026-10-31 em docs/ARCHITECTURE.md. Nulo = o download devolve o
arquivo ingerido (`storage_path`), como antes.

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("rag_documents", sa.Column("download_path", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("rag_documents", "download_path")
