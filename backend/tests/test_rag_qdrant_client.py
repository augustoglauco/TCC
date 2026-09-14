import asyncio
import uuid

import pytest
from qdrant_client import AsyncQdrantClient

from app.config import get_settings
from app.rag.embeddings import TextEmbedder
from app.rag.qdrant_client import QdrantRAGClient
from app.router.rag_client import Document, RAGConnectionError


@pytest.fixture
def rag_client(text_embedder: TextEmbedder) -> QdrantRAGClient:
    """Cliente RAG contra um Qdrant em memória (`location=":memory:"`), uma
    collection nova por teste — evita depender de um Qdrant externo no ar
    e evita colisão entre testes."""
    memory_client = AsyncQdrantClient(location=":memory:")
    return QdrantRAGClient(
        host="unused",
        port=0,
        embedder=text_embedder,
        collection_name=f"test_{uuid.uuid4().hex}",
        client=memory_client,
    )


async def test_search_sem_nada_indexado_retorna_lista_vazia(rag_client: QdrantRAGClient):
    resultado = await rag_client.search("qualquer pergunta", domain="vendas")

    assert resultado == []


async def test_upsert_chunks_vazio_nao_grava_e_retorna_zero(rag_client: QdrantRAGClient):
    total = await rag_client.upsert_chunks([], source="arquivo.txt", domain="vendas")

    assert total == 0
    assert await rag_client.search("qualquer coisa", domain="vendas") == []


async def test_upsert_e_search_retorna_documento_com_conteudo_e_fonte(rag_client: QdrantRAGClient):
    await rag_client.upsert_chunks(
        ["O gerador diesel GD-30 tem potência de 30 kVA e autonomia de 10 horas."],
        source="catalogo_geradores.txt",
        domain="vendas",
    )

    resultado = await rag_client.search("Qual a potência do gerador GD-30?", domain="vendas")

    assert len(resultado) == 1
    documento = resultado[0]
    assert isinstance(documento, Document)
    assert "GD-30" in documento.content
    assert documento.source == "catalogo_geradores.txt"
    assert documento.score > 0


async def test_search_filtra_por_domain_nao_traz_documento_de_outro_dominio(
    rag_client: QdrantRAGClient,
):
    await rag_client.upsert_chunks(
        ["O gerador não liga: verificar bateria de partida e nível de combustível."],
        source="manual_gd30.txt",
        domain="suporte",
    )

    resultado = await rag_client.search("gerador não liga", domain="vendas")

    assert resultado == []


async def test_search_erro_de_conexao_vira_rag_connection_error(text_embedder: TextEmbedder):
    # Porta sem nenhum serviço no ar — falha de conexão, não busca vazia.
    client = QdrantRAGClient(host="localhost", port=1, embedder=text_embedder)

    with pytest.raises(RAGConnectionError):
        await client.search("qualquer coisa", domain="vendas")


async def test_search_apos_drop_collection_volta_a_checar_existencia(
    rag_client: QdrantRAGClient,
):
    """Regressão: a guarda em memória (`_collection_ready`) que evita
    round trips repetidos ao Qdrant precisa ser invalidada por
    `drop_collection`, senão uma busca depois do drop tentaria consultar
    uma collection que não existe mais em vez de devolver lista vazia."""
    await rag_client.upsert_chunks(
        ["conteúdo de teste sobre o produto"], source="arquivo.txt", domain="vendas"
    )
    assert len(await rag_client.search("produto", domain="vendas")) == 1

    await rag_client.drop_collection()

    assert await rag_client.search("produto", domain="vendas") == []


class _FailingEmbedder:
    """`get_dimension` funciona normalmente (deixa `ensure_collection`
    criar a collection) mas `embed` falha — simula um erro do modelo (ex.:
    texto degenerado extraído de um PDF) durante o próprio `upsert_chunks`,
    não na criação da collection."""

    async def get_dimension(self) -> int:
        return 384

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("falha simulada do modelo de embeddings")


async def test_upsert_chunks_com_falha_no_embedder_vira_rag_connection_error():
    client = QdrantRAGClient(
        host="unused",
        port=0,
        embedder=_FailingEmbedder(),
        collection_name=f"test_{uuid.uuid4().hex}",
        client=AsyncQdrantClient(location=":memory:"),
    )

    with pytest.raises(RAGConnectionError):
        await client.upsert_chunks(["texto qualquer"], source="arquivo.txt", domain="vendas")


async def test_upsert_chunks_concorrentes_nao_colidem_na_criacao_da_collection(
    text_embedder: TextEmbedder,
):
    """Regressão: duas ingestões quase simultâneas contra uma collection que
    ainda não existe não devem tentar criá-la em paralelo (race
    check-then-act entre `collection_exists`/`create_collection`,
    serializada por `_collection_lock`)."""
    client = QdrantRAGClient(
        host="unused",
        port=0,
        embedder=text_embedder,
        collection_name=f"test_{uuid.uuid4().hex}",
        client=AsyncQdrantClient(location=":memory:"),
    )

    resultados = await asyncio.gather(
        client.upsert_chunks(["texto A sobre o produto"], source="a.txt", domain="vendas"),
        client.upsert_chunks(["texto B sobre o produto"], source="b.txt", domain="vendas"),
    )

    assert resultados == [1, 1]
    assert len(await client.search("produto", domain="vendas")) == 2


@pytest.mark.qdrant
async def test_upsert_e_search_contra_qdrant_real_do_docker_compose(text_embedder: TextEmbedder):
    """Mesmo comportamento de `test_upsert_e_search_retorna_documento_...`,
    mas contra o Qdrant real do `docker-compose.yml` (não em memória) — só
    roda com o serviço no ar (ver `QDRANT_HOST`/`QDRANT_PORT` em `.env`)."""
    settings = get_settings()
    collection_name = f"test_{uuid.uuid4().hex}"
    client = QdrantRAGClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        embedder=text_embedder,
        collection_name=collection_name,
    )

    try:
        await client.upsert_chunks(
            ["A garantia padrão dos geradores é de 12 meses contra defeitos de fabricação."],
            source="politicas_troca_garantia.txt",
            domain="atendimento",
        )

        resultado = await client.search("qual o prazo de garantia?", domain="atendimento")

        assert len(resultado) == 1
        assert "garantia" in resultado[0].content.lower()
    finally:
        await client.drop_collection()
