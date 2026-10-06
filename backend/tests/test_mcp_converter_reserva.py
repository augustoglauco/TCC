import base64
import json
import uuid
from decimal import Decimal

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

    assert (
        "divergência" in str(exc_info.value).lower() or "divergente" in str(exc_info.value).lower()
    )

    async with factory() as session:
        pedido_db = await session.get(Pedido, uuid.UUID(pedido_id_str))
        assert pedido_db.status == "pagamento_divergente"


class _FakeLLMClient:
    """Simula um cliente de texto (`OllamaClient`/`OpenRouterClient`) —
    usado para provar que `converter_reserva_venda` agora de fato chama um
    LLM, em vez de só o fallback heurístico por regex (achado de
    2026-10-06, docs/ARCHITECTURE.md §4)."""

    def __init__(self, texto_resposta: str) -> None:
        self._texto = texto_resposta
        self.chamado = False

    async def generate(self, prompt: str):
        self.chamado = True

        class _Resp:
            text = self._texto

        return _Resp()


class _FakeVisionClient:
    """Simula um cliente de visão (local ou externo) — `describe_image`."""

    def __init__(self, resposta: str | None = None, erro: Exception | None = None) -> None:
        self._resposta = resposta
        self._erro = erro
        self.chamado = False

    async def describe_image(self, image_bytes: bytes, prompt: str) -> str:
        self.chamado = True
        if self._erro:
            raise self._erro
        return self._resposta


@pytest.mark.asyncio
async def test_mcp_tool_converter_reserva_venda_usa_llm_local_quando_disponivel(
    factory, qdrant, embedders
):
    """Achado de 2026-10-06: antes, `converter_reserva_venda` nunca recebia
    nenhum `llm_client` — passava direto para o fallback heurístico por
    regex. Agora, com `local_client` fornecido, o LLM é de fato chamado."""
    async with factory() as session:
        produto = await criar_produto(
            session,
            nome="Inversor Solar 5kW",
            descricao="Inversor grid-tie",
            preco=Decimal("2000.00"),
            categoria="solar",
        )
        await atualizar_estoque(session, produto.id, "CD-SP", 10)
        pedido = await criar_pedido(session, [(produto.id, 1, "CD-SP")])
        pedido_id_str = str(pedido.id)

    fake_llm = _FakeLLMClient(
        texto_resposta=json.dumps(
            {
                "comprovante_valido": True,
                "valor_pago": 2000.00,
                "codigo_transacao": "LLM-TX-001",
                "justificativa": "Comprovante validado pelo LLM local.",
            }
        )
    )
    server = create_b2b_mcp_server(factory, qdrant, embedders, local_client=fake_llm)

    resultado = await server.call_tool(
        "converter_reserva_venda",
        {
            "pedido_id": pedido_id_str,
            "comprovante_base64_ou_texto": "Comprovante qualquer, formato livre.",
            "nome_arquivo": "comprovante.txt",
        },
    )

    assert fake_llm.chamado is True
    saida = resultado.structured_content
    assert saida["sucesso"] is True
    assert saida["status"] == "venda_concluida"


@pytest.mark.asyncio
async def test_mcp_tool_converter_reserva_venda_imagem_usa_visao_local_antes_da_externa(
    factory, qdrant, embedders
):
    """Comprovante enviado como imagem (sem texto extraível por OCR) —
    tenta visão LOCAL primeiro; se ela resolver, a externa nunca é chamada."""
    async with factory() as session:
        produto = await criar_produto(
            session,
            nome="Controlador de Carga MPPT",
            descricao="60A",
            preco=Decimal("500.00"),
            categoria="solar",
        )
        await atualizar_estoque(session, produto.id, "CD-SP", 10)
        pedido = await criar_pedido(session, [(produto.id, 1, "CD-SP")])
        pedido_id_str = str(pedido.id)

    local_vision = _FakeVisionClient(
        resposta=json.dumps(
            {
                "comprovante_valido": True,
                "valor_pago": 500.00,
                "codigo_transacao": "VISION-LOCAL-001",
                "justificativa": "ok",
            }
        )
    )
    external_vision = _FakeVisionClient(erro=AssertionError("não deveria chamar visão externa"))
    server = create_b2b_mcp_server(
        factory, qdrant, embedders, local_client=local_vision, external_client=external_vision
    )

    imagem_base64 = base64.b64encode(b"fake-jpg-content-sem-texto-legivel").decode("utf-8")

    resultado = await server.call_tool(
        "converter_reserva_venda",
        {
            "pedido_id": pedido_id_str,
            "comprovante_base64_ou_texto": imagem_base64,
            "nome_arquivo": "comprovante.jpg",
        },
    )

    assert local_vision.chamado is True
    assert external_vision.chamado is False
    saida = resultado.structured_content
    assert saida["sucesso"] is True
    assert saida["status"] == "venda_concluida"


@pytest.mark.asyncio
async def test_mcp_tool_converter_reserva_venda_imagem_cai_para_visao_externa_quando_local_falha(
    factory, qdrant, embedders
):
    async with factory() as session:
        produto = await criar_produto(
            session,
            nome="String Box Solar",
            descricao="2 strings",
            preco=Decimal("250.00"),
            categoria="solar",
        )
        await atualizar_estoque(session, produto.id, "CD-SP", 10)
        pedido = await criar_pedido(session, [(produto.id, 1, "CD-SP")])
        pedido_id_str = str(pedido.id)

    local_vision = _FakeVisionClient(erro=RuntimeError("modelo local sem visão"))
    external_vision = _FakeVisionClient(
        resposta=json.dumps(
            {
                "comprovante_valido": True,
                "valor_pago": 250.00,
                "codigo_transacao": "VISION-EXT-001",
                "justificativa": "ok",
            }
        )
    )
    server = create_b2b_mcp_server(
        factory, qdrant, embedders, local_client=local_vision, external_client=external_vision
    )

    imagem_base64 = base64.b64encode(b"fake-jpg-content-sem-texto-legivel").decode("utf-8")

    resultado = await server.call_tool(
        "converter_reserva_venda",
        {
            "pedido_id": pedido_id_str,
            "comprovante_base64_ou_texto": imagem_base64,
            "nome_arquivo": "comprovante.jpg",
        },
    )

    assert local_vision.chamado is True
    assert external_vision.chamado is True
    saida = resultado.structured_content
    assert saida["sucesso"] is True
    assert saida["status"] == "venda_concluida"


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
