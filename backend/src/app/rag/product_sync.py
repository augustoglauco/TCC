"""Sincronização automática do catálogo de produtos no RAG (R4, correção de
2026-09-29 — ver docs/ARCHITECTURE.md §5).

Antes, o único jeito de o catálogo (`app.db.catalog.Produto`) aparecer na
busca semântica (Qdrant) era rodar manualmente
`backend/scripts/ingest_db_table.py` — um script avulso da Fase 2, nunca
reexecutado depois que o catálogo cresceu (estoque, descontos, imagens,
Fase 7). Este módulo substitui isso por um hook automático chamado pelas
rotas de CRUD de produtos (`app.api.admin_products`): toda vez que um
produto (ou seu estoque/desconto) muda, o texto correspondente é
reingerido na collection ativa do RAG (a mesma buscada pelo chat público),
domínio "vendas".

# MVP: sem deduplicação incremental — cada sync apaga e recria o documento
do zero (delete + ingest), mesma limitação já aceita em `app.rag.ingest`.
Falha de sincronização é logada e nunca propagada — o catálogo em SQL
(`app.db.catalog`, fonte de verdade para `SalesCatalogClient`) nunca fica
bloqueado por uma falha do RAG (mesmo espírito das falhas de indexação CLIP
já toleradas em `app.api.admin_products`).
"""

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.catalog import listar_estoque
from app.db.models import Produto, RagDocument
from app.rag.collections_registry import get_active_collection
from app.rag.db_connector import row_to_text
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.ingest import ingest_bytes
from app.rag.qdrant_client import QdrantRAGClient
from app.rag.registry import delete_document

logger = logging.getLogger(__name__)

_DOMAIN = "vendas"


def _nome_arquivo(produto_id: int) -> str:
    """Nome determinístico por produto — permite achar e apagar a versão
    anterior antes de reingerir (evita duplicar documentos a cada edição)."""
    return f"produto_{produto_id}.txt"


async def sync_produto_no_rag(
    session: AsyncSession,
    qdrant: QdrantRAGClient,
    embedders: EmbedderRegistry,
    uploads_dir: Path,
    produto: Produto,
) -> None:
    """(Re)ingere `produto` como um documento de texto na collection ativa
    do RAG — chamado depois de criar/editar um produto ou seu estoque/
    desconto. Nunca levanta exceção (mesmo espírito de `analyze_tone`/
    `_consultar_vendas`: uma falha aqui não pode derrubar o CRUD de
    produtos, que é a fonte de verdade real)."""
    try:
        collection = await get_active_collection(session)
        if collection is None:
            logger.warning("rag_sync_produto_sem_collection_ativa produto_id=%s", produto.id)
            return
        filename = _nome_arquivo(produto.id)
        await _apagar_documento_existente(session, qdrant, collection.name, filename)

        estoques = await listar_estoque(session, produto.id)
        linha = {
            "produto_id": produto.id,
            "nome": produto.nome,
            "categoria": produto.categoria,
            "descricao": produto.descricao,
            "especificacoes_tecnicas": produto.especificacoes_tecnicas,
            "dimensoes_cm": produto.dimensoes_cm,
            "peso_kg": produto.peso_kg,
            "preco": produto.preco,
            "preco_promocional": produto.preco_promocional,
            "estoque_total": sum(estoque.quantidade for estoque in estoques),
        }
        embedder = embedders.get(collection.embedding_model)
        await ingest_bytes(
            qdrant,
            embedder,
            collection,
            uploads_dir,
            filename,
            row_to_text(linha).encode("utf-8"),
            _DOMAIN,
            session=session,
            # MVP: reaproveita o valor existente mais próximo — não há um
            # "auto_sync" dedicado no schema (`origin`, ver `app.rag.registry`).
            origin="batch_script",
        )
    except Exception:
        logger.exception("rag_sync_produto_falhou produto_id=%s", produto.id)


async def remover_produto_do_rag(
    session: AsyncSession, qdrant: QdrantRAGClient, produto_id: int
) -> None:
    """Remove o documento do produto do RAG (Qdrant + registro) — chamado ao
    excluir um produto. Mesma tolerância a falha de `sync_produto_no_rag`."""
    try:
        collection = await get_active_collection(session)
        if collection is None:
            return
        filename = _nome_arquivo(produto_id)
        await _apagar_documento_existente(session, qdrant, collection.name, filename)
    except Exception:
        logger.exception("rag_sync_produto_remocao_falhou produto_id=%s", produto_id)


async def _apagar_documento_existente(
    session: AsyncSession, qdrant: QdrantRAGClient, collection_name: str, filename: str
) -> None:
    result = await session.execute(select(RagDocument).where(RagDocument.filename == filename))
    for document in result.scalars().all():
        await qdrant.delete_by_document_id(collection_name, str(document.id))
        await delete_document(session, str(document.id))
