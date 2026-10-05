import base64
from datetime import UTC, datetime
from decimal import Decimal
import json
import uuid
import pytest
from mcp.server.mcpserver.exceptions import ToolError
from qdrant_client import AsyncQdrantClient

from app.db.catalog import atualizar_estoque, criar_pedido, criar_produto
from app.db.engine import create_db_engine, create_session_factory
from app.db.models import Base, Pedido
from app.mcp_server.b2b import create_b2b_mcp_server
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient


@pytest.fixture
async def factory():
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    yield factory
    await engine.dispose()


@pytest.fixture
def qdrant() -> QdrantRAGClient:
    return QdrantRAGClient(host="unused", port=0, client=AsyncQdrantClient(location=":memory:"))


@pytest.fixture
def embedders() -> EmbedderRegistry:
    return EmbedderRegistry()


@pytest.mark.asyncio
async def test_mcp_tool_converter_reserva_venda_sucesso_texto(factory, qdrant, embedders):
    async with factory() as session:
        produto = await criar_produto(
            session,
            nome="Módulo Solar B2B",
            descricao="Módulo 550W",
            preco=Decimal("300.00"),
            categoria="solar",
        )
        await atualizar_estoque(session, produto.id, "CD-SP", 20)
        pedido = await criar_pedido(session, [(produto.id, 1, "CD-SP")])
        pedido_id_str = str(pedido.id)

    server = create_b2b_mcp_server(factory, qdrant, embedders)

    comprovante_texto = (
        "Comprovante de Transferência PIX\n"
        "Valor Pago: R$ 300,00\n"
        "Código de Autenticação: PIX123456789\n"
        "Favorecido: Distribuidora Solar SA"
    )

    resultado = await server.call_tool(
        "converter_reserva_venda",
        {
            "pedido_id": pedido_id_str,
            "comprovante_base64_ou_texto": comprovante_texto,
            "nome_arquivo": "comprovante.txt",
        },
    )

    saida = resultado.structured_content
    assert saida["sucesso"] is True
    assert saida["status"] == "venda_concluida"
    assert saida["tipo_conversao"] == "auto_mcp_b2b"

    async with factory() as session:
        pedido_db = await session.get(Pedido, uuid.UUID(pedido_id_str))
        assert pedido_db.status == "venda_concluida"
        assert pedido_db.tipo_conversao == "auto_mcp_b2b"
        assert pedido_db.convertido_em is not None
        assert pedido_db.llm_parecer is not None


@pytest.mark.asyncio
async def test_mcp_tool_converter_reserva_venda_sucesso_base64(factory, qdrant, embedders):
    async with factory() as session:
        produto = await criar_produto(
            session,
            nome="Cabo Solar 6mm",
            descricao="Rolo 100m",
            preco=Decimal("150.00"),
            categoria="solar",
        )
        await atualizar_estoque(session, produto.id, "CD-SP", 10)
        pedido = await criar_pedido(session, [(produto.id, 2, "CD-SP")])
        pedido_id_str = str(pedido.id)

    server = create_b2b_mcp_server(factory, qdrant, embedders)

    texto_recibo = "Comprovante TED\nValor: R$ 300.00\nAutenticação: TED001122"
    base64_recibo = base64.b64encode(texto_recibo.encode("utf-8")).decode("utf-8")

    resultado = await server.call_tool(
        "converter_reserva_venda",
        {
            "pedido_id": pedido_id_str,
            "comprovante_base64_ou_texto": base64_recibo,
            "nome_arquivo": "recibo.txt",
        },
    )

    saida = resultado.structured_content
    assert saida["sucesso"] is True
    assert saida["status"] == "venda_concluida"
    assert saida["tipo_conversao"] == "auto_mcp_b2b"


@pytest.mark.asyncio
async def test_mcp_tool_converter_reserva_venda_divergencia(factory, qdrant, embedders):
    async with factory() as session:
        produto = await criar_produto(
            session,
            nome="Bateria Estacionária",
            descricao="12V 220Ah",
            preco=Decimal("1000.00"),
            categoria="baterias",
        )
        await atualizar_estoque(session, produto.id, "CD-SP", 5)
        pedido = await criar_pedido(session, [(produto.id, 1, "CD-SP")])
        pedido_id_str = str(pedido.id)

    server = create_b2b_mcp_server(factory, qdrant, embedders)

    comprovante_divergente = "Comprovante PIX\nValor: R$ 500,00\nAutenticação: ERR123"

    with pytest.raises(ToolError) as exc_info:
        await server.call_tool(
            "converter_reserva_venda",
            {
                "pedido_id": pedido_id_str,
                "comprovante_base64_ou_texto": comprovante_divergente,
                "nome_arquivo": "comprovante.txt",
            },
        )

    assert "divergência" in str(exc_info.value).lower() or "divergente" in str(exc_info.value).lower()

    async with factory() as session:
        pedido_db = await session.get(Pedido, uuid.UUID(pedido_id_str))
        assert pedido_db.status == "pagamento_divergente"


@pytest.mark.asyncio
async def test_mcp_tool_converter_reserva_venda_pedido_inexistente(factory, qdrant, embedders):
    server = create_b2b_mcp_server(factory, qdrant, embedders)

    with pytest.raises(ToolError) as exc_info:
        await server.call_tool(
            "converter_reserva_venda",
            {
                "pedido_id": str(uuid.uuid4()),
                "comprovante_base64_ou_texto": "Comprovante PIX R$ 100",
                "nome_arquivo": "recibo.txt",
            },
        )

    assert "não encontrado" in str(exc_info.value).lower()
