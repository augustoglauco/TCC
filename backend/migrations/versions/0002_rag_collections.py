"""create rag_collections, add collection_id/storage_path to rag_documents

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-15

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SEED_COLLECTION_ID = uuid.uuid4()


def upgrade() -> None:
    op.create_table(
        "rag_collections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("embedding_model", sa.String(), nullable=False),
        sa.Column("vector_dimension", sa.Integer(), nullable=False),
        sa.Column("distance_metric", sa.String(), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("chunk_overlap", sa.Integer(), nullable=False),
        sa.Column("hnsw_m", sa.Integer(), nullable=False),
        sa.Column("hnsw_ef_construct", sa.Integer(), nullable=False),
        sa.Column("hnsw_full_scan_threshold", sa.Integer(), nullable=False),
        sa.Column("hnsw_max_indexing_threads", sa.Integer(), nullable=False),
        sa.Column("hnsw_on_disk", sa.Boolean(), nullable=False),
        sa.Column("hnsw_payload_m", sa.Integer(), nullable=True),
        sa.Column("quantization_type", sa.String(), nullable=False),
        sa.Column("quantization_config", JSONB(), nullable=False),
        sa.Column("payload_indexes", JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    rag_collections = sa.table(
        "rag_collections",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("embedding_model", sa.String()),
        sa.column("vector_dimension", sa.Integer()),
        sa.column("distance_metric", sa.String()),
        sa.column("chunk_size", sa.Integer()),
        sa.column("chunk_overlap", sa.Integer()),
        sa.column("hnsw_m", sa.Integer()),
        sa.column("hnsw_ef_construct", sa.Integer()),
        sa.column("hnsw_full_scan_threshold", sa.Integer()),
        sa.column("hnsw_max_indexing_threads", sa.Integer()),
        sa.column("hnsw_on_disk", sa.Boolean()),
        sa.column("hnsw_payload_m", sa.Integer()),
        sa.column("quantization_type", sa.String()),
        sa.column("quantization_config", JSONB()),
        sa.column("payload_indexes", JSONB()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        rag_collections,
        [
            {
                "id": _SEED_COLLECTION_ID,
                "name": "docs_texto",
                "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
                "vector_dimension": 384,
                "distance_metric": "cosine",
                "chunk_size": 800,
                "chunk_overlap": 100,
                "hnsw_m": 16,
                "hnsw_ef_construct": 100,
                "hnsw_full_scan_threshold": 10000,
                "hnsw_max_indexing_threads": 0,
                "hnsw_on_disk": False,
                "hnsw_payload_m": None,
                "quantization_type": "none",
                "quantization_config": {},
                "payload_indexes": [],
                "is_active": True,
            }
        ],
    )

    op.add_column("rag_documents", sa.Column("collection_id", sa.Uuid(), nullable=True))
    op.add_column("rag_documents", sa.Column("storage_path", sa.String(), nullable=True))
    op.execute(
        sa.text("UPDATE rag_documents SET collection_id = :collection_id").bindparams(
            collection_id=_SEED_COLLECTION_ID
        )
    )
    op.alter_column("rag_documents", "collection_id", nullable=False)
    op.create_foreign_key(
        "fk_rag_documents_collection_id",
        "rag_documents",
        "rag_collections",
        ["collection_id"],
        ["id"],
    )
    op.drop_column("rag_documents", "embedding_model")
    op.drop_column("rag_documents", "chunk_size")
    op.drop_column("rag_documents", "chunk_overlap")


def downgrade() -> None:
    op.add_column("rag_documents", sa.Column("embedding_model", sa.String(), nullable=True))
    op.add_column("rag_documents", sa.Column("chunk_size", sa.Integer(), nullable=True))
    op.add_column("rag_documents", sa.Column("chunk_overlap", sa.Integer(), nullable=True))

    # Backfill a partir da `rag_collections` associada a cada linha, antes de
    # apagá-la: os valores originais por linha foram descartados no upgrade()
    # (que passou a guardá-los só uma vez por collection), então restaurar a
    # constraint NOT NULL de 0001 sem popular esses valores primeiro quebraria
    # com dados reais (ou deixaria linhas incoerentes com o schema de 0001).
    op.execute(
        sa.text(
            "UPDATE rag_documents SET "
            "embedding_model = rag_collections.embedding_model, "
            "chunk_size = rag_collections.chunk_size, "
            "chunk_overlap = rag_collections.chunk_overlap "
            "FROM rag_collections "
            "WHERE rag_documents.collection_id = rag_collections.id"
        )
    )
    op.alter_column("rag_documents", "embedding_model", nullable=False)
    op.alter_column("rag_documents", "chunk_size", nullable=False)
    op.alter_column("rag_documents", "chunk_overlap", nullable=False)

    op.drop_constraint("fk_rag_documents_collection_id", "rag_documents", type_="foreignkey")
    op.drop_column("rag_documents", "collection_id")
    op.drop_column("rag_documents", "storage_path")
    op.drop_table("rag_collections")
