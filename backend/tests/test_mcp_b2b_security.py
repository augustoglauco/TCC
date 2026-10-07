"""Testes de caracterização de abuso das ferramentas MCP B2B (R12) — ver
docs/superpowers/specs/2026-10-07-seguranca-prompt-injection-mcp-design.md
§3.4/§4.2. Confirma que a validação Pydantic JÁ EXISTENTE nos schemas de
entrada (`app.models.mcp_b2b`) rejeita tipo errado, quantidade inválida e
produto inexistente — nenhum código de produção é alterado por esta task.

Comportamento verificado manualmente contra o servidor real antes de
escrever este arquivo (python -c chamando `server.call_tool` diretamente):
campo extra não declarado é silenciosamente ignorado pelo Pydantic (não
rejeitado) — documentado no teste correspondente como achado, não como bug
a corrigir (fora do escopo desta task: exigiria `model_config =
{"extra": "forbid"}` em todos os schemas de entrada, uma mudança de
comportamento não pedida pela spec).
"""

from decimal import Decimal

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from qdrant_client import AsyncQdrantClient

from app.db.catalog import criar_produto
from app.db.engine import create_db_engine, create_session_factory
from app.db.models import Base
from app.mcp_server.b2b import create_b2b_mcp_server
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient


async def _engine_e_sessionmaker_vazios():
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, create_session_factory(engine)


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


async def test_cotar_com_tipo_errado_em_quantidade_levanta_tool_error(factory, qdrant, embedders):
    produto_id = await _cria_produto_completo(factory)
    server = create_b2b_mcp_server(factory, qdrant, embedders)

    with pytest.raises(ToolError, match="unable to parse string as an integer"):
        await server.call_tool(
            "cotar", {"itens": [{"produto_id": produto_id, "quantidade": "cem"}]}
        )


async def test_cotar_com_quantidade_negativa_levanta_tool_error(factory, qdrant, embedders):
    produto_id = await _cria_produto_completo(factory)
    server = create_b2b_mcp_server(factory, qdrant, embedders)

    with pytest.raises(ToolError, match="greater than 0"):
        await server.call_tool(
            "cotar", {"itens": [{"produto_id": produto_id, "quantidade": -5}]}
        )


async def test_reservar_pedido_com_produto_id_tipo_errado_levanta_tool_error(
    factory, qdrant, embedders
):
    server = create_b2b_mcp_server(factory, qdrant, embedders)

    with pytest.raises(ToolError):
        await server.call_tool(
            "reservar_pedido",
            {
                "itens": [
                    {
                        "produto_id": "abc",
                        "quantidade": 1,
                        "centro_distribuicao": "CD-SP",
                    }
                ]
            },
        )


async def test_cotar_ignora_silenciosamente_campo_extra_nao_declarado(factory, qdrant, embedders):
    # Achado (não um bug a corrigir nesta task — ver docstring do módulo):
    # campos extras no payload não fazem a ferramenta falhar, são só
    # descartados pelo Pydantic antes de chegar à lógica de negócio. Este
    # teste documenta o comportamento real, para que uma mudança futura que
    # o altere (ex.: adicionar `extra="forbid"`) quebre este teste de
    # propósito, em vez de passar silenciosamente despercebida.
    produto_id = await _cria_produto_completo(factory)
    server = create_b2b_mcp_server(factory, qdrant, embedders)

    resultado = await server.call_tool(
        "cotar",
        {"itens": [{"produto_id": produto_id, "quantidade": 1, "campo_nao_declarado": "x"}]},
    )

    assert resultado.structured_content["total"] == "24900.00"
