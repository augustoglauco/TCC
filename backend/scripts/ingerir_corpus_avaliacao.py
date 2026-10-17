"""Ingere o corpus de documentos da avaliação experimental (Fase 10) — os
PDFs de manual e datasheet do fornecedor — na collection ativa do RAG.

Por que não reaproveita `ingest_directory`: aquela função infere o domínio
pelo nome do diretório-pai de cada arquivo, e aqui o pai é o nome do produto
(`ControlId/iDFace Max/...`), não um domínio válido — todos os arquivos
seriam ignorados com aviso. Este script fixa `domain="suporte"`, que é onde
manuais e datasheets vivem no sistema e o domínio que
`eval/rag_quality/run_eval.py` usa na busca.

Retomável: pula o que já está ingerido na collection, comparando pelo nome
do arquivo. Reingerir sem isso duplicaria pontos no Qdrant — não há
deduplicação em `upsert_chunks`.

Uso (a partir de `backend/`, com Qdrant e Postgres no ar):

    .venv/bin/python scripts/ingerir_corpus_avaliacao.py
    .venv/bin/python scripts/ingerir_corpus_avaliacao.py --dir <outro>
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db.engine import create_db_engine, create_session_factory
from app.db.models import RagDocument
from app.logging_config import configure_logging
from app.rag.collections_registry import get_active_collection
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.ingest import SUPPORTED_SUFFIXES, ingest_file
from app.rag.qdrant_client import QdrantRAGClient

CORPUS_PADRAO = Path(__file__).resolve().parents[2] / "docs" / "Manuais_fornecedor" / "ControlId"
DOMINIO = "suporte"


def listar_arquivos_corpus(diretorio: Path) -> list[Path]:
    """Lista os documentos ingeríveis (`SUPPORTED_SUFFIXES`: `.pdf`, `.md`, `.txt`)
    em `diretorio`, ordenados deterministicamente por nome e caminho."""
    return sorted(
        (p for p in diretorio.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES),
        key=lambda p: (p.name, str(p)),
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=CORPUS_PADRAO)
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    arquivos = listar_arquivos_corpus(args.dir)
    if not arquivos:
        print(f"Nenhum documento suportado em {args.dir}")
        sys.exit(1)
    print(f"{len(arquivos)} documento(s) em {args.dir}")

    qdrant = QdrantRAGClient(
        host=settings.qdrant_host, port=settings.qdrant_port, timeout_s=settings.qdrant_timeout_s
    )
    embedders = EmbedderRegistry()
    uploads_dir = Path(settings.rag_uploads_dir)
    db_engine = create_db_engine(settings.postgres_dsn)
    session_factory = create_session_factory(db_engine)

    ingeridos = pulados = falhas = 0
    total_chunks = 0

    async with session_factory() as session:
        collection = await get_active_collection(session)
        if collection is None:
            raise RuntimeError("Nenhuma collection ativa — rode `alembic upgrade head` primeiro.")
        embedder = embedders.get(collection.embedding_model)

        existentes = set(
            (
                await session.execute(
                    select(RagDocument.filename).where(RagDocument.collection_id == collection.id)
                )
            )
            .scalars()
            .all()
        )
        print(f"collection ativa: '{collection.name}' ({len(existentes)} documento(s) já dentro)")

        for i, doc_path in enumerate(arquivos, start=1):
            if doc_path.name in existentes:
                pulados += 1
                continue
            try:
                documento = await ingest_file(
                    qdrant,
                    embedder,
                    collection,
                    uploads_dir,
                    doc_path,
                    DOMINIO,
                    session=session,
                    origin="corpus_avaliacao",
                )
            except Exception as exc:  # noqa: BLE001
                # Um PDF escaneado sem camada de texto, ou corrompido, não
                # pode derrubar a ingestão dos outros documentos.
                falhas += 1
                print(f"[{i}/{len(arquivos)}] FALHOU {doc_path.name}: {type(exc).__name__}: {exc}")
                continue
            ingeridos += 1
            total_chunks += documento.chunk_count
            print(f"[{i}/{len(arquivos)}] {doc_path.name}: {documento.chunk_count} chunk(s)")

    print(
        f"\nIngeridos {ingeridos}, pulados {pulados} (já estavam), falhas {falhas}. "
        f"{total_chunks} chunk(s) novos na collection '{collection.name}'."
    )
    await db_engine.dispose()


if __name__ == "__main__":
    logging.getLogger(__name__).info("iniciando ingestão do corpus de avaliação")
    asyncio.run(main())
