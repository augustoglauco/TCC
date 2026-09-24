"""Testes do servidor MCP B2B (R12, Fase 5) — `app.mcp_server.b2b`.

Chama o servidor pela mesma superfície que um cliente MCP usaria
(`MCPServer.read_resource`, via `create_b2b_mcp_server`), não só a camada de
dados por baixo (já coberta por `test_catalog.py`). Mesmo espírito de
`test_google_calendar_client.py`, mas do lado servidor.
"""

import json
import uuid
from decimal import Decimal

import pytest
from mcp.server.mcpserver.exceptions import ResourceError, ResourceNotFoundError
from qdrant_client import AsyncQdrantClient

from app.db.catalog import adicionar_desconto_volume, atualizar_estoque, criar_produto
from app.db.engine import create_db_engine, create_session_factory
from app.db.models import Base, RagCollection
from app.mcp_server.b2b import create_b2b_mcp_server
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.embeddings import TextEmbedder
from app.rag.qdrant_client import QdrantRAGClient
from app.router.rag_client import RAGConnectionError

_DEFAULT_HNSW = dict(
    hnsw_m=16,
    hnsw_ef_construct=100,
    hnsw_full_scan_threshold=10000,
    hnsw_max_indexing_threads=0,
    hnsw_on_disk=False,
    hnsw_payload_m=None,
)


async def _engine_e_sessionmaker_vazios():
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, create_session_factory(engine)


def _conteudo_texto(resultado) -> str:
    [item] = resultado
    return item.content


@pytest.fixture
async def factory():
    engine, factory = await _engine_e_sessionmaker_vazios()
    yield factory
    await engine.dispose()


@pytest.fixture
def qdrant() -> QdrantRAGClient:
    return QdrantRAGClient(host="unused", port=0, client=AsyncQdrantClient(location=":memory:"))


@pytest.fixture
def embedders() -> EmbedderRegistry:
    return EmbedderRegistry()


async def _cria_produto_completo(factory, **overrides):
    defaults = dict(
        nome="Gerador Diesel GD-15",
        descricao="Potência de 15 kVA.",
        preco=Decimal("24900.00"),
        categoria="geradores",
        especificacoes_tecnicas="15 kVA, monofásico",
        dimensoes_cm="120x80x100",
        peso_kg=Decimal("350.00"),
    )
    defaults.update(overrides)
    async with factory() as session:
        produto = await criar_produto(session, **defaults)
        return produto.id


# --- Recurso 1: catálogo ----------------------------------------------------


async def test_catalogo_produtos_lista_todos(factory, qdrant, embedders):
    await _cria_produto_completo(factory, nome="Gerador A")
    await _cria_produto_completo(factory, nome="Gerador B")
    server = create_b2b_mcp_server(factory, qdrant, embedders)

    resultado = await server.read_resource("catalogo://produtos")

    itens = json.loads(_conteudo_texto(resultado))
    assert [item["nome"] for item in itens] == ["Gerador A", "Gerador B"]
    # Recurso de catálogo não expõe preço (recurso próprio "precos://").
    assert "preco" not in itens[0]


async def test_catalogo_produtos_filtra_por_categoria(factory, qdrant, embedders):
    await _cria_produto_completo(factory, nome="Gerador A", categoria="geradores")
    await _cria_produto_completo(factory, nome="Cabine", categoria="acessórios")
    server = create_b2b_mcp_server(factory, qdrant, embedders)

    resultado = await server.read_resource("catalogo://produtos?categoria=acess%C3%B3rios")

    itens = json.loads(_conteudo_texto(resultado))
    assert [item["nome"] for item in itens] == ["Cabine"]


async def test_catalogo_produto_detalhe_existente(factory, qdrant, embedders):
    produto_id = await _cria_produto_completo(factory)
    server = create_b2b_mcp_server(factory, qdrant, embedders)

    resultado = await server.read_resource(f"catalogo://produtos/{produto_id}")

    item = json.loads(_conteudo_texto(resultado))
    assert item["id"] == produto_id
    assert item["especificacoes_tecnicas"] == "15 kVA, monofásico"


async def test_catalogo_produto_detalhe_inexistente_levanta_not_found(factory, qdrant, embedders):
    server = create_b2b_mcp_server(factory, qdrant, embedders)

    with pytest.raises(ResourceNotFoundError):
        await server.read_resource("catalogo://produtos/999")


async def test_catalogo_produto_detalhe_id_invalido_levanta_resource_error(
    factory, qdrant, embedders
):
    server = create_b2b_mcp_server(factory, qdrant, embedders)

    with pytest.raises(ResourceError):
        await server.read_resource("catalogo://produtos/abc")


# --- Recurso 2: estoque ------------------------------------------------------


async def test_estoque_produto_lista_centros_de_distribuicao(factory, qdrant, embedders):
    produto_id = await _cria_produto_completo(factory)
    async with factory() as session:
        await atualizar_estoque(session, produto_id, "CD-SP", 12)
        await atualizar_estoque(session, produto_id, "CD-RJ", 5)
    server = create_b2b_mcp_server(factory, qdrant, embedders)

    resultado = await server.read_resource(f"estoque://produtos/{produto_id}")

    item = json.loads(_conteudo_texto(resultado))
    assert item["produto_id"] == produto_id
    assert {c["centro_distribuicao"]: c["quantidade"] for c in item["centros"]} == {
        "CD-SP": 12,
        "CD-RJ": 5,
    }


async def test_estoque_produto_inexistente_levanta_not_found(factory, qdrant, embedders):
    server = create_b2b_mcp_server(factory, qdrant, embedders)

    with pytest.raises(ResourceNotFoundError):
        await server.read_resource("estoque://produtos/999")


# --- Recurso 3: preços --------------------------------------------------------


async def test_precos_produto_inclui_promocao_e_descontos_volume(factory, qdrant, embedders):
    produto_id = await _cria_produto_completo(factory, preco_promocional=Decimal("19900.00"))
    async with factory() as session:
        await adicionar_desconto_volume(session, produto_id, 5, Decimal("5.00"))
        await adicionar_desconto_volume(session, produto_id, 10, Decimal("10.00"))
    server = create_b2b_mcp_server(factory, qdrant, embedders)

    resultado = await server.read_resource(f"precos://produtos/{produto_id}")

    item = json.loads(_conteudo_texto(resultado))
    assert item["preco"] == "24900.00"
    assert item["preco_promocional"] == "19900.00"
    assert [
        (d["quantidade_minima"], d["percentual_desconto"]) for d in item["descontos_volume"]
    ] == [(5, "5.00"), (10, "10.00")]


async def test_precos_produto_inexistente_levanta_not_found(factory, qdrant, embedders):
    server = create_b2b_mcp_server(factory, qdrant, embedders)

    with pytest.raises(ResourceNotFoundError):
        await server.read_resource("precos://produtos/999")


# --- Recurso 4: manuais (busca semântica) -------------------------------------


async def _cria_collection_com_conteudo(
    factory,
    qdrant: QdrantRAGClient,
    text_embedder: TextEmbedder,
    *,
    name: str,
    purpose: str,
    is_active: bool,
    conteudo: str,
    source: str,
    document_id: str,
    domain: str = "vendas",
) -> None:
    dimension = await text_embedder.get_dimension()
    async with factory() as session:
        session.add(
            RagCollection(
                id=uuid.uuid4(),
                name=name,
                embedding_model=text_embedder.model_name,
                vector_dimension=dimension,
                distance_metric="cosine",
                chunk_size=800,
                chunk_overlap=100,
                quantization_type="none",
                quantization_config={},
                payload_indexes=[],
                is_active=is_active,
                purpose=purpose,
                **_DEFAULT_HNSW,
            )
        )
        await session.commit()
    await qdrant.create_collection(
        name=name,
        vector_dimension=dimension,
        distance_metric="cosine",
        quantization_type="none",
        quantization_config={},
        payload_indexes=[],
        **_DEFAULT_HNSW,
    )
    await qdrant.upsert_chunks(
        name, text_embedder, [conteudo], source=source, domain=domain, document_id=document_id
    )


async def test_manuais_busca_encontra_conteudo_da_collection_mcp_b2b(
    factory, qdrant, embedders, text_embedder: TextEmbedder
):
    await _cria_collection_com_conteudo(
        factory,
        qdrant,
        text_embedder,
        name=f"manual_{uuid.uuid4().hex}",
        purpose="mcp_b2b",
        is_active=False,
        conteudo="Manual de instalação do gerador diesel GD-15",
        source="manual_gd15.pdf",
        document_id="doc-manual",
    )
    server = create_b2b_mcp_server(factory, qdrant, embedders)

    resultado = await server.read_resource(
        "manuais://busca/vendas?query=instala%C3%A7%C3%A3o%20gerador"
    )

    item = json.loads(_conteudo_texto(resultado))
    assert len(item["resultados"]) == 1
    assert item["resultados"][0]["source"] == "manual_gd15.pdf"


async def test_manuais_busca_nao_encontra_conteudo_de_collection_chat(
    factory, qdrant, embedders, text_embedder: TextEmbedder
):
    """Isolamento simétrico ao já testado para o chat
    (`test_rag_active_collection_client.py`): o MCP B2B também não deveria
    misturar conteúdo `purpose="chat"` na busca de manuais."""
    await _cria_collection_com_conteudo(
        factory,
        qdrant,
        text_embedder,
        name=f"chat_{uuid.uuid4().hex}",
        purpose="chat",
        is_active=True,
        conteudo="conteúdo público sobre instalação de gerador",
        source="publico.txt",
        document_id="doc-chat",
    )
    server = create_b2b_mcp_server(factory, qdrant, embedders)

    resultado = await server.read_resource(
        "manuais://busca/vendas?query=instala%C3%A7%C3%A3o%20gerador"
    )

    item = json.loads(_conteudo_texto(resultado))
    assert item["resultados"] == []


async def test_manuais_busca_sem_query_levanta_resource_error(factory, qdrant, embedders):
    server = create_b2b_mcp_server(factory, qdrant, embedders)

    with pytest.raises(ResourceError):
        await server.read_resource("manuais://busca/vendas")


async def test_manuais_busca_agrega_varias_collections_mcp_b2b(
    factory, qdrant, embedders, text_embedder: TextEmbedder
):
    await _cria_collection_com_conteudo(
        factory,
        qdrant,
        text_embedder,
        name=f"manual_a_{uuid.uuid4().hex}",
        purpose="mcp_b2b",
        is_active=False,
        conteudo="Manual de instalação do gerador diesel GD-15",
        source="manual_a.pdf",
        document_id="doc-a",
    )
    await _cria_collection_com_conteudo(
        factory,
        qdrant,
        text_embedder,
        name=f"manual_b_{uuid.uuid4().hex}",
        purpose="mcp_b2b",
        is_active=False,
        conteudo="Esquema elétrico do gerador diesel GD-15",
        source="manual_b.pdf",
        document_id="doc-b",
    )
    server = create_b2b_mcp_server(factory, qdrant, embedders)

    resultado = await server.read_resource("manuais://busca/vendas?query=gerador%20diesel%20GD-15")

    item = json.loads(_conteudo_texto(resultado))
    fontes = {r["source"] for r in item["resultados"]}
    assert fontes == {"manual_a.pdf", "manual_b.pdf"}


async def test_manuais_busca_ignora_collection_com_falha_e_devolve_as_demais(
    factory, qdrant, embedders, text_embedder: TextEmbedder, monkeypatch
):
    # Achado no code-review (2026-09-24): a busca em múltiplas collections
    # passou a rodar em paralelo (asyncio.gather) em vez de sequencial —
    # este teste cobre especificamente que uma falha (RAGConnectionError)
    # numa collection não derruba as demais nem o resultado agregado,
    # comportamento que o código sequencial anterior também tinha, mas que
    # o gather-based precisa preservar explicitamente.
    await _cria_collection_com_conteudo(
        factory,
        qdrant,
        text_embedder,
        name=f"manual_ok_{uuid.uuid4().hex}",
        purpose="mcp_b2b",
        is_active=False,
        conteudo="Manual de instalação do gerador diesel GD-15",
        source="manual_ok.pdf",
        document_id="doc-ok",
    )
    nome_collection_falha = f"manual_falha_{uuid.uuid4().hex}"
    await _cria_collection_com_conteudo(
        factory,
        qdrant,
        text_embedder,
        name=nome_collection_falha,
        purpose="mcp_b2b",
        is_active=False,
        conteudo="Esquema elétrico do gerador diesel GD-15",
        source="manual_falha.pdf",
        document_id="doc-falha",
    )

    busca_original = qdrant.search

    async def _busca_com_falha_simulada(collection_name, *args, **kwargs):
        if collection_name == nome_collection_falha:
            raise RAGConnectionError("Qdrant indisponível (simulado)")
        return await busca_original(collection_name, *args, **kwargs)

    monkeypatch.setattr(qdrant, "search", _busca_com_falha_simulada)
    server = create_b2b_mcp_server(factory, qdrant, embedders)

    resultado = await server.read_resource("manuais://busca/vendas?query=gerador%20diesel%20GD-15")

    item = json.loads(_conteudo_texto(resultado))
    fontes = {r["source"] for r in item["resultados"]}
    assert fontes == {"manual_ok.pdf"}
