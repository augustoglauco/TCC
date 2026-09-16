import uuid

import pytest
from qdrant_client import AsyncQdrantClient

from app.config import get_settings
from app.rag.embeddings import TextEmbedder
from app.rag.qdrant_client import CollectionAlreadyExistsError, QdrantRAGClient
from app.router.rag_client import Document, RAGConnectionError

_DEFAULT_HNSW = dict(
    hnsw_m=16,
    hnsw_ef_construct=100,
    hnsw_full_scan_threshold=10000,
    hnsw_max_indexing_threads=0,
    hnsw_on_disk=False,
    hnsw_payload_m=None,
)


@pytest.fixture
def qdrant() -> QdrantRAGClient:
    """Cliente RAG contra um Qdrant em memória (`location=":memory:"`) —
    evita depender de um Qdrant externo no ar e evita colisão entre testes."""
    return QdrantRAGClient(host="unused", port=0, client=AsyncQdrantClient(location=":memory:"))


async def _cria_collection(qdrant: QdrantRAGClient, dimension: int, name: str | None = None) -> str:
    name = name or f"test_{uuid.uuid4().hex}"
    await qdrant.create_collection(
        name=name,
        vector_dimension=dimension,
        distance_metric="cosine",
        quantization_type="none",
        quantization_config={},
        payload_indexes=[],
        **_DEFAULT_HNSW,
    )
    return name


async def test_create_collection_cria_e_collection_exists_confirma(
    qdrant: QdrantRAGClient, text_embedder: TextEmbedder
):
    name = await _cria_collection(qdrant, await text_embedder.get_dimension())

    assert await qdrant.collection_exists(name) is True


async def test_create_collection_duplicada_levanta_collection_already_exists(
    qdrant: QdrantRAGClient, text_embedder: TextEmbedder
):
    name = await _cria_collection(qdrant, await text_embedder.get_dimension())

    with pytest.raises(CollectionAlreadyExistsError):
        await _cria_collection(qdrant, await text_embedder.get_dimension(), name=name)


async def test_create_collection_com_payload_indexes_nao_levanta_erro(
    qdrant: QdrantRAGClient, text_embedder: TextEmbedder
):
    name = f"test_{uuid.uuid4().hex}"

    await qdrant.create_collection(
        name=name,
        vector_dimension=await text_embedder.get_dimension(),
        distance_metric="cosine",
        quantization_type="scalar",
        quantization_config={"quantile": 0.9, "always_ram": True},
        payload_indexes=[
            {"field": "domain", "schema_type": "keyword"},
            {"field": "content", "schema_type": "text", "text_params": {"tokenizer": "word"}},
        ],
        **_DEFAULT_HNSW,
    )

    assert await qdrant.collection_exists(name) is True


async def test_search_sem_collection_criada_retorna_lista_vazia(
    qdrant: QdrantRAGClient, text_embedder: TextEmbedder
):
    resultado = await qdrant.search("nome_inexistente", text_embedder, "qualquer pergunta", domain="vendas")

    assert resultado == []


async def test_upsert_chunks_vazio_nao_grava_e_retorna_zero(
    qdrant: QdrantRAGClient, text_embedder: TextEmbedder
):
    name = await _cria_collection(qdrant, await text_embedder.get_dimension())

    total = await qdrant.upsert_chunks(
        name, text_embedder, [], source="arquivo.txt", domain="vendas", document_id="doc-1"
    )

    assert total == 0
    assert await qdrant.search(name, text_embedder, "qualquer coisa", domain="vendas") == []


async def test_upsert_e_search_retorna_documento_com_conteudo_e_fonte(
    qdrant: QdrantRAGClient, text_embedder: TextEmbedder
):
    name = await _cria_collection(qdrant, await text_embedder.get_dimension())
    await qdrant.upsert_chunks(
        name,
        text_embedder,
        ["O gerador diesel GD-30 tem potência de 30 kVA e autonomia de 10 horas."],
        source="catalogo_geradores.txt",
        domain="vendas",
        document_id="doc-1",
    )

    resultado = await qdrant.search(name, text_embedder, "Qual a potência do gerador GD-30?", domain="vendas")

    assert len(resultado) == 1
    documento = resultado[0]
    assert isinstance(documento, Document)
    assert "GD-30" in documento.content
    assert documento.source == "catalogo_geradores.txt"
    assert documento.score > 0


async def test_search_filtra_por_domain_nao_traz_documento_de_outro_dominio(
    qdrant: QdrantRAGClient, text_embedder: TextEmbedder
):
    name = await _cria_collection(qdrant, await text_embedder.get_dimension())
    await qdrant.upsert_chunks(
        name,
        text_embedder,
        ["O gerador não liga: verificar bateria de partida e nível de combustível."],
        source="manual_gd30.txt",
        domain="suporte",
        document_id="doc-1",
    )

    resultado = await qdrant.search(name, text_embedder, "gerador não liga", domain="vendas")

    assert resultado == []


async def test_search_erro_de_conexao_vira_rag_connection_error(text_embedder: TextEmbedder):
    # Porta sem nenhum serviço no ar — falha de conexão, não busca vazia.
    client = QdrantRAGClient(host="localhost", port=1)

    with pytest.raises(RAGConnectionError):
        await client.search("qualquer_nome", text_embedder, "qualquer coisa", domain="vendas")


class _FailingEmbedder:
    """`get_dimension` funciona normalmente mas `embed` falha — simula um
    erro do modelo (ex.: texto degenerado extraído de um PDF) durante o
    próprio `upsert_chunks`."""

    async def get_dimension(self) -> int:
        return 384

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("falha simulada do modelo de embeddings")


async def test_upsert_chunks_com_falha_no_embedder_vira_rag_connection_error(
    qdrant: QdrantRAGClient, text_embedder: TextEmbedder
):
    name = await _cria_collection(qdrant, await text_embedder.get_dimension())

    with pytest.raises(RAGConnectionError):
        await qdrant.upsert_chunks(
            name, _FailingEmbedder(), ["texto qualquer"], source="arquivo.txt", domain="vendas", document_id="doc-1"
        )


@pytest.mark.qdrant
async def test_upsert_e_search_contra_qdrant_real_do_docker_compose(text_embedder: TextEmbedder):
    """Mesmo comportamento de `test_upsert_e_search_retorna_documento_...`,
    mas contra o Qdrant real do `docker-compose.yml` (não em memória) — só
    roda com o serviço no ar (ver `QDRANT_HOST`/`QDRANT_PORT` em `.env`).
    Também é o único teste que exercita HNSW/quantização/payload indexing de
    verdade — o backend em memória usado nos demais testes aceita esses
    parâmetros mas os ignora silenciosamente (confirmado lendo
    `qdrant_client.local.qdrant_local.QdrantLocal.create_collection` e
    `.create_payload_index` — ver
    docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §4).
    """
    settings = get_settings()
    client = QdrantRAGClient(host=settings.qdrant_host, port=settings.qdrant_port)
    name = f"test_{uuid.uuid4().hex}"

    try:
        await client.create_collection(
            name=name,
            vector_dimension=await text_embedder.get_dimension(),
            distance_metric="cosine",
            quantization_type="scalar",
            quantization_config={"quantile": 0.99, "always_ram": False},
            payload_indexes=[{"field": "domain", "schema_type": "keyword"}],
            **_DEFAULT_HNSW,
        )
        await client.upsert_chunks(
            name,
            text_embedder,
            ["A garantia padrão dos geradores é de 12 meses contra defeitos de fabricação."],
            source="politicas_troca_garantia.txt",
            domain="atendimento",
            document_id="doc-1",
        )

        resultado = await client.search(name, text_embedder, "qual o prazo de garantia?", domain="atendimento")

        assert len(resultado) == 1
        assert "garantia" in resultado[0].content.lower()
    finally:
        await client.drop_collection(name)


async def test_upsert_chunks_grava_document_id_no_payload_do_ponto(
    qdrant: QdrantRAGClient, text_embedder: TextEmbedder
):
    name = await _cria_collection(qdrant, await text_embedder.get_dimension())
    await qdrant.upsert_chunks(
        name, text_embedder, ["conteúdo de teste"], source="arquivo.txt", domain="vendas", document_id="doc-xyz"
    )

    pontos, _ = await qdrant._client.scroll(name, limit=10)

    assert len(pontos) == 1
    assert pontos[0].payload["document_id"] == "doc-xyz"


async def test_delete_by_document_id_remove_so_os_pontos_daquele_documento(
    qdrant: QdrantRAGClient, text_embedder: TextEmbedder
):
    name = await _cria_collection(qdrant, await text_embedder.get_dimension())
    await qdrant.upsert_chunks(
        name, text_embedder, ["conteúdo do documento A"], source="a.txt", domain="vendas", document_id="doc-a"
    )
    await qdrant.upsert_chunks(
        name, text_embedder, ["conteúdo do documento B"], source="b.txt", domain="vendas", document_id="doc-b"
    )

    await qdrant.delete_by_document_id(name, "doc-a")

    resultado = await qdrant.search(name, text_embedder, "conteúdo", domain="vendas")
    assert len(resultado) == 1
    assert resultado[0].source == "b.txt"


async def test_delete_by_document_id_sem_collection_nao_levanta_erro(qdrant: QdrantRAGClient):
    # Collection inexistente — deve ser um no-op silencioso, mesmo espírito
    # de `search` sem nada indexado.
    await qdrant.delete_by_document_id("nome_inexistente", "doc-inexistente")


async def test_delete_by_document_id_erro_de_conexao_vira_rag_connection_error():
    client = QdrantRAGClient(host="localhost", port=1)

    with pytest.raises(RAGConnectionError):
        await client.delete_by_document_id("qualquer_nome", "doc-1")
