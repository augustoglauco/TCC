"""Pipeline mínimo de ingestão de PDFs/textos no RAG (R4).

Toda ingestão (via `ingest_bytes`, usado tanto pelo endpoint de upload
quanto — indiretamente, via `ingest_file`/`ingest_directory` — pelo script
em lote) cria um registro em `app.rag.registry`, amarrado aos pontos do
Qdrant pelo `document_id` gerado aqui (ver
docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md §3).

# MVP: pipeline pensado para rodar sob demanda via script ou endpoint HTTP,
# não como serviço/observador de diretório — sem deduplicação nem
# re-ingestão incremental (reingerir a mesma fonte cria um registro novo e
# pontos duplicados no Qdrant, ver `app.rag.qdrant_client.upsert_chunks`).
Ordem de escrita: upsert no Qdrant primeiro, registro no Postgres depois —
se a escrita no Postgres falhar depois do upsert ter tido sucesso, sobra um
ponto órfão no Qdrant sem registro; isso é logado como aviso, sem tentativa
de rollback cross-store (ver spec §3, "sem transação distribuída
Qdrant+Postgres").
"""

import logging
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RagDocument
from app.rag.chunking import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, chunk_text
from app.rag.pdf_extract import extract_text_from_pdf
from app.rag.qdrant_client import QdrantRAGClient
from app.rag.registry import create_document

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}


def _extract_text(filename: str, content: bytes) -> str:
    if Path(filename).suffix.lower() == ".pdf":
        return extract_text_from_pdf(content)
    return content.decode("utf-8")


async def ingest_bytes(
    client: QdrantRAGClient,
    filename: str,
    content: bytes,
    domain: str,
    session: AsyncSession,
    origin: str,
) -> RagDocument:
    """Extrai texto, faz chunking, grava no Qdrant e cria o registro do
    documento (`app.rag.registry.create_document`).

    `origin` distingue quem disparou a ingestão ("upload" — endpoint HTTP,
    "batch_script" — `scripts/ingest_sample_docs.py`), só para fins de
    auditoria no registro.
    """
    text = _extract_text(filename, content)
    chunks = chunk_text(text)
    document_id = str(uuid.uuid4())
    chunk_count = await client.upsert_chunks(
        chunks, source=filename, domain=domain, document_id=document_id
    )
    logger.info(
        "rag_ingest arquivo=%s domain=%s chunks=%d document_id=%s",
        filename,
        domain,
        chunk_count,
        document_id,
    )
    try:
        return await create_document(
            session,
            document_id=document_id,
            filename=filename,
            domain=domain,
            chunk_count=chunk_count,
            embedding_model=client.embedding_model_name,
            chunk_size=DEFAULT_CHUNK_SIZE,
            chunk_overlap=DEFAULT_CHUNK_OVERLAP,
            origin=origin,
        )
    except Exception:
        logger.warning(
            "rag_registro_orfao document_id=%s arquivo=%s — pontos gravados no Qdrant sem "
            "registro correspondente no Postgres",
            document_id,
            filename,
        )
        raise


async def ingest_file(
    client: QdrantRAGClient, path: Path, domain: str, session: AsyncSession, origin: str
) -> RagDocument:
    """Mesma lógica de `ingest_bytes`, a partir de um arquivo em disco."""
    return await ingest_bytes(client, path.name, path.read_bytes(), domain, session, origin)


async def ingest_directory(
    client: QdrantRAGClient,
    directory: Path,
    session: AsyncSession,
    origin: str = "batch_script",
) -> list[RagDocument]:
    """Ingere todos os arquivos suportados (.txt/.md/.pdf) de `directory`.

    # MVP: domínio inferido do nome do subdiretório imediato de cada arquivo
    # (ex.: `sample_docs/vendas/catalogo.txt` -> domain="vendas") — convenção
    # simples por convenção de pasta, sem metadados explícitos por arquivo.
    Retorna um documento de registro por arquivo ingerido.
    """
    documentos = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        domain = path.parent.name
        documentos.append(await ingest_file(client, path, domain, session, origin))
    return documentos
