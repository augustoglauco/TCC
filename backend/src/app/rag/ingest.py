"""Pipeline mínimo de ingestão de PDFs/textos no RAG (R4).

# MVP: pipeline pensado para rodar sob demanda via script (ver
# `backend/scripts/ingest_sample_docs.py`), não como serviço/observador de
# diretório — sem deduplicação nem re-ingestão incremental (reingerir o
# mesmo diretório cria pontos duplicados, ver
# `app.rag.qdrant_client.upsert_chunks`). Ver docs/ARCHITECTURE.md §5.
"""

import logging
import uuid
from pathlib import Path

from app.rag.chunking import chunk_text
from app.rag.pdf_extract import extract_text_from_pdf
from app.rag.qdrant_client import QdrantRAGClient

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}


def _extract_text(filename: str, content: bytes) -> str:
    if Path(filename).suffix.lower() == ".pdf":
        return extract_text_from_pdf(content)
    return content.decode("utf-8")


async def ingest_bytes(client: QdrantRAGClient, filename: str, content: bytes, domain: str) -> int:
    """Extrai texto, faz chunking e grava um arquivo em memória no Qdrant.

    Mesma lógica de `ingest_file`, mas a partir de bytes já carregados (usado
    pelo endpoint de upload `POST /api/rag/documents`, que recebe o arquivo
    via HTTP em vez de lê-lo do disco). Retorna o número de chunks gravados.
    """
    text = _extract_text(filename, content)
    chunks = chunk_text(text)
    count = await client.upsert_chunks(
        chunks, source=filename, domain=domain, document_id=str(uuid.uuid4())
    )
    logger.info("rag_ingest_upload arquivo=%s domain=%s chunks=%d", filename, domain, count)
    return count


async def ingest_file(client: QdrantRAGClient, path: Path, domain: str) -> int:
    """Extrai texto, faz chunking e grava um único arquivo no Qdrant.

    Retorna o número de chunks gravados.
    """
    return await ingest_bytes(client, path.name, path.read_bytes(), domain)


async def ingest_directory(client: QdrantRAGClient, directory: Path) -> int:
    """Ingere todos os arquivos suportados (.txt/.md/.pdf) de `directory`.

    # MVP: domínio inferido do nome do subdiretório imediato de cada arquivo
    # (ex.: `sample_docs/vendas/catalogo.txt` -> domain="vendas") — convenção
    # simples por convenção de pasta, sem metadados explícitos por arquivo.
    Retorna o total de chunks gravados.
    """
    total = 0
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        domain = path.parent.name
        total += await ingest_file(client, path, domain)
    return total
