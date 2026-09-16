"""Script de ingestão das linhas de uma tabela do banco relacional no RAG
(R4 — conector de leitura a BD relacional).

# MVP: somente leitura, sem sincronização incremental (ver
docs/ARCHITECTURE.md §5) — lê a tabela informada uma vez por execução, sem
observar mudanças nem escrever no banco de origem; reingestão é manual
(rodar de novo), o que duplica registros/pontos no Qdrant, mesma limitação
de `backend/scripts/ingest_sample_docs.py`.

Reaproveita o pipeline de ingestão existente (`app.rag.ingest.ingest_bytes`):
cada linha vira um texto (`app.rag.db_connector.row_to_text`) e é ingerida
como um "documento" próprio, chunked/embedado como qualquer outro texto.

Uso (a partir de `backend/`, com o Postgres do docker-compose no ar e a
migração do Alembic já aplicada — `alembic upgrade head`, que cria e semeia
a tabela fixture `produtos`):

    .venv/bin/python scripts/ingest_db_table.py --table produtos --domain vendas
"""

import argparse
import asyncio
import logging
from pathlib import Path

from app.config import get_settings
from app.db.engine import create_db_engine, create_session_factory
from app.logging_config import configure_logging
from app.rag.collections_registry import get_active_collection
from app.rag.db_connector import read_table_as_text
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.ingest import ingest_bytes
from app.rag.qdrant_client import QdrantRAGClient


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", required=True, help="Nome da tabela a ler (ex.: produtos).")
    parser.add_argument(
        "--domain",
        required=True,
        choices=["vendas", "suporte", "atendimento"],
        help="Domínio do RAG a associar às linhas ingeridas.",
    )
    parser.add_argument(
        "--columns",
        nargs="*",
        default=None,
        help="Subconjunto de colunas a ler (default: todas as colunas da tabela).",
    )
    return parser.parse_args()


async def main() -> None:
    args = _parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)

    qdrant = QdrantRAGClient(
        host=settings.qdrant_host, port=settings.qdrant_port, timeout_s=settings.qdrant_timeout_s
    )
    embedders = EmbedderRegistry()
    uploads_dir = Path(settings.rag_uploads_dir)
    db_engine = create_db_engine(settings.postgres_dsn)
    session_factory = create_session_factory(db_engine)

    async with session_factory() as session, db_engine.connect() as connection:
        collection = await get_active_collection(session)
        if collection is None:
            raise RuntimeError(
                "Nenhuma collection ativa configurada — rode `alembic upgrade head` primeiro."
            )
        embedder = embedders.get(collection.embedding_model)

        textos = await read_table_as_text(connection, args.table, columns=args.columns)
        documentos = [
            await ingest_bytes(
                qdrant,
                embedder,
                collection,
                uploads_dir,
                f"{args.table}_row{indice}.txt",
                texto.encode("utf-8"),
                args.domain,
                session=session,
                # MVP: reaproveita o mesmo `origin` do script de lote de
                # PDFs/textos — não há um valor dedicado para "conector de
                # BD" no schema de resposta (`DocumentRegistryResponse.origin`
                # é `Literal["upload", "batch_script", "reingest"]`).
                origin="batch_script",
            )
            for indice, texto in enumerate(textos, start=1)
        ]

    total_chunks = sum(documento.chunk_count for documento in documentos)
    print(
        f"Ingerida(s) {len(documentos)} linha(s) da tabela '{args.table}', {total_chunks} "
        f"chunk(s), na collection '{collection.name}'"
    )
    await db_engine.dispose()


if __name__ == "__main__":
    logging.getLogger(__name__).info("iniciando ingestão de tabela do banco relacional")
    asyncio.run(main())
