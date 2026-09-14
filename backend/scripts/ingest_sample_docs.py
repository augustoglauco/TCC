"""Script de ingestão de um pequeno conjunto de documentos de exemplo no RAG.

# MVP: script de linha de comando único, sem agendamento nem observador de
# diretório — reingestão é manual (rodar o script de novo), o que duplica
# pontos no Qdrant, já que não há deduplicação (ver
# `app.rag.qdrant_client.upsert_chunks`). Serve para ter algo indexado para
# demonstrar/testar o RAG, não é um pipeline de produção (ver
# docs/ARCHITECTURE.md §5).

Uso (a partir de `backend/`, com o Qdrant do docker-compose no ar):

    .venv/bin/python scripts/ingest_sample_docs.py
"""

import asyncio
import logging
from pathlib import Path

from app.config import get_settings
from app.logging_config import configure_logging
from app.rag.embeddings import TextEmbedder
from app.rag.ingest import ingest_directory
from app.rag.qdrant_client import QdrantRAGClient

SAMPLE_DOCS_DIR = Path(__file__).parent / "sample_docs"


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    embedder = TextEmbedder(settings.rag_embedding_model)
    client = QdrantRAGClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        embedder=embedder,
        timeout_s=settings.qdrant_timeout_s,
    )

    total = await ingest_directory(client, SAMPLE_DOCS_DIR)
    print(f"Ingeridos {total} chunks a partir de {SAMPLE_DOCS_DIR}")


if __name__ == "__main__":
    logging.getLogger(__name__).info("iniciando ingestão de documentos de exemplo")
    asyncio.run(main())
