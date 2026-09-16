"""Pipeline de ingestão de PDFs/textos no RAG (R4) — por collection, com
reingestão em outra collection (Entregas B+C+D, além do MVP).

Toda ingestão cria um registro em `app.rag.registry`, amarrado aos pontos do
Qdrant pelo `document_id` gerado aqui, e salva o arquivo original em disco
(`uploads_dir`) para permitir reingestão futura em outra collection (ver
docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §3, §5).

# MVP: pipeline pensado para rodar sob demanda via script ou endpoint HTTP,
# não como serviço/observador de diretório — sem deduplicação nem
# re-ingestão incremental automática (reingerir a mesma fonte cria um
# registro novo e pontos duplicados no Qdrant).
Ordem de escrita: upsert no Qdrant primeiro, registro no Postgres depois —
se a escrita no Postgres falhar depois do upsert ter tido sucesso, sobra um
ponto órfão no Qdrant sem registro; isso é logado como aviso, sem tentativa
de rollback cross-store.
"""

import logging
import uuid
from pathlib import Path
from typing import get_args

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RagCollection, RagDocument
from app.models.rag import RagDomain
from app.rag.chunking import chunk_text
from app.rag.embeddings import TextEmbedder
from app.rag.pdf_extract import extract_text_from_pdf
from app.rag.qdrant_client import CollectionAlreadyExistsError, QdrantRAGClient
from app.rag.registry import create_document

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}
_VALID_DOMAINS = set(get_args(RagDomain))


def _extract_text(filename: str, content: bytes) -> str:
    if Path(filename).suffix.lower() == ".pdf":
        return extract_text_from_pdf(content)
    return content.decode("utf-8")


async def _ensure_collection_exists(qdrant: QdrantRAGClient, collection: RagCollection) -> None:
    """Recria `collection` no Qdrant a partir do perfil salvo se ela não
    existir (self-healing) — fresh install, cuja migração só semeia a linha
    em Postgres (ver
    docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §4.1),
    ou alguém apagou a collection no Qdrant por fora do app. Não é uma
    garantia de transação distribuída Qdrant+Postgres, mesma tolerância já
    aceita para o caso inverso (registro órfão) em `ingest_bytes`.

    Compartilhada entre `ingest_bytes` e `reingest_document` (achado #5 da
    revisão final: a segunda não tinha essa auto-cura, apesar de reingerir
    em uma `RagCollection` cuja collection no Qdrant também pode estar
    ausente)."""
    if await qdrant.collection_exists(collection.name):
        return
    try:
        await qdrant.create_collection(
            name=collection.name,
            vector_dimension=collection.vector_dimension,
            distance_metric=collection.distance_metric,
            hnsw_m=collection.hnsw_m,
            hnsw_ef_construct=collection.hnsw_ef_construct,
            hnsw_full_scan_threshold=collection.hnsw_full_scan_threshold,
            hnsw_max_indexing_threads=collection.hnsw_max_indexing_threads,
            hnsw_on_disk=collection.hnsw_on_disk,
            hnsw_payload_m=collection.hnsw_payload_m,
            quantization_type=collection.quantization_type,
            quantization_config=collection.quantization_config,
            payload_indexes=collection.payload_indexes,
        )
    except CollectionAlreadyExistsError:
        pass  # corrida com uma ingestão concorrente recriando-a — tudo bem, já existe


async def ingest_bytes(
    qdrant: QdrantRAGClient,
    embedder: TextEmbedder,
    collection: RagCollection,
    uploads_dir: Path,
    filename: str,
    content: bytes,
    domain: str,
    session: AsyncSession,
    origin: str,
) -> RagDocument:
    """Extrai texto, faz chunking com os parâmetros de `collection`, grava
    no Qdrant, salva o arquivo original em `uploads_dir` e cria o registro
    do documento."""
    text = _extract_text(filename, content)
    chunks = chunk_text(text, chunk_size=collection.chunk_size, overlap=collection.chunk_overlap)
    document_id = str(uuid.uuid4())

    # MVP: recriação idempotente/self-healing da collection no Qdrant se ela não
    # existir — ver docstring de `_ensure_collection_exists`.
    await _ensure_collection_exists(qdrant, collection)

    chunk_count = await qdrant.upsert_chunks(
        collection.name, embedder, chunks, source=filename, domain=domain, document_id=document_id
    )

    storage_path = uploads_dir / f"{document_id}_{Path(filename).name}"
    try:
        uploads_dir.mkdir(parents=True, exist_ok=True)
        storage_path.write_bytes(content)
    except OSError:
        # Achado #6 da revisão final: mesmo tratamento de órfão já aplicado
        # abaixo para a falha de registro no Postgres — aqui os chunks já
        # foram gravados no Qdrant, mas não há arquivo salvo em disco (e,
        # por consequência, nenhum registro no Postgres, que depende do
        # `storage_path` calculado aqui).
        logger.warning(
            "rag_registro_orfao document_id=%s arquivo=%s — pontos gravados no Qdrant sem "
            "arquivo salvo em disco (e sem registro correspondente no Postgres)",
            document_id,
            filename,
        )
        raise

    logger.info(
        "rag_ingest arquivo=%s domain=%s chunks=%d document_id=%s collection=%s",
        filename,
        domain,
        chunk_count,
        document_id,
        collection.name,
    )
    try:
        return await create_document(
            session,
            document_id=document_id,
            collection_id=collection.id,
            filename=filename,
            domain=domain,
            chunk_count=chunk_count,
            storage_path=str(storage_path),
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
    qdrant: QdrantRAGClient,
    embedder: TextEmbedder,
    collection: RagCollection,
    uploads_dir: Path,
    path: Path,
    domain: str,
    session: AsyncSession,
    origin: str,
) -> RagDocument:
    """Mesma lógica de `ingest_bytes`, a partir de um arquivo em disco."""
    return await ingest_bytes(
        qdrant,
        embedder,
        collection,
        uploads_dir,
        path.name,
        path.read_bytes(),
        domain,
        session,
        origin,
    )


async def ingest_directory(
    qdrant: QdrantRAGClient,
    embedder: TextEmbedder,
    collection: RagCollection,
    uploads_dir: Path,
    directory: Path,
    session: AsyncSession,
    origin: str = "batch_script",
) -> list[RagDocument]:
    """Ingere todos os arquivos suportados (.txt/.md/.pdf) de `directory` na
    `collection` informada.

    # MVP: domínio inferido do nome do subdiretório imediato de cada arquivo
    # (ex.: `sample_docs/vendas/catalogo.txt` -> domain="vendas"). Arquivos
    # em subdiretórios cujo nome não é um domínio válido são ignorados (com
    # aviso no log).
    """
    documentos = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        domain = path.parent.name
        if domain not in _VALID_DOMAINS:
            logger.warning(
                "rag_ingest_domain_invalido arquivo=%s domain=%s — ignorado, domínios válidos: %s",
                path,
                domain,
                sorted(_VALID_DOMAINS),
            )
            continue
        documentos.append(
            await ingest_file(
                qdrant, embedder, collection, uploads_dir, path, domain, session, origin
            )
        )
    return documentos


async def reingest_document(
    qdrant: QdrantRAGClient,
    embedder: TextEmbedder,
    source_document: RagDocument,
    target_collection: RagCollection,
    session: AsyncSession,
) -> RagDocument:
    """Reingere o arquivo original de `source_document` (lido de
    `storage_path`) na `target_collection`, com os parâmetros de chunking e
    o embedder dessa collection destino. Cria um documento **novo** — não
    move nem apaga o original.
    """
    if source_document.storage_path is None:
        raise ValueError(
            f"documento {source_document.id} não tem arquivo salvo, não é possível reingerir "
            "(ingerido antes desta funcionalidade existir)"
        )
    content = Path(source_document.storage_path).read_bytes()
    text = _extract_text(source_document.filename, content)
    chunks = chunk_text(
        text, chunk_size=target_collection.chunk_size, overlap=target_collection.chunk_overlap
    )
    document_id = str(uuid.uuid4())

    # Achado #5 da revisão final: mesma auto-cura de `ingest_bytes` — a
    # collection destino pode ter sido apagada no Qdrant por fora do app, ou
    # ser uma linha só-Postgres semeada, e reingerir não deveria depender
    # dela já existir de fato.
    await _ensure_collection_exists(qdrant, target_collection)

    chunk_count = await qdrant.upsert_chunks(
        target_collection.name,
        embedder,
        chunks,
        source=source_document.filename,
        domain=source_document.domain,
        document_id=document_id,
    )
    return await create_document(
        session,
        document_id=document_id,
        collection_id=target_collection.id,
        filename=source_document.filename,
        domain=source_document.domain,
        chunk_count=chunk_count,
        storage_path=source_document.storage_path,
        origin="reingest",
    )
