"""cria a tabela model_characteristics (características de modelo, hover admin)

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_characteristics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("tag", sa.String(), nullable=False),
        sa.Column("is_multimodal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("input_modalities", JSONB(), nullable=False),
        sa.Column("output_modalities", JSONB(), nullable=False),
        sa.Column("context_length", sa.Integer(), nullable=True),
        sa.Column("parameter_size", sa.String(), nullable=True),
        sa.Column("quantization", sa.String(), nullable=True),
        sa.Column("pricing_prompt_per_1k", sa.Float(), nullable=True),
        sa.Column("pricing_completion_per_1k", sa.Float(), nullable=True),
        sa.Column("knowledge_cutoff", sa.String(), nullable=True),
        sa.Column("raw_payload", JSONB(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "tag", name="uq_model_characteristics_source_tag"),
    )


def downgrade() -> None:
    op.drop_table("model_characteristics")
