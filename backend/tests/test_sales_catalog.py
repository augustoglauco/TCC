"""Testes de app.router.sales_catalog (R12, Fase 5 — orquestrador como
integrador do MCP B2B em Vendas). Ver
docs/superpowers/specs/2026-09-24-orquestrador-mcp-b2b-vendas-design.md.
"""

from decimal import Decimal

import pytest

from app.db.catalog import (
    adicionar_desconto_volume,
    atualizar_estoque,
    criar_compatibilidade,
    criar_produto,
)
from app.db.engine import create_db_engine, create_session_factory
from app.db.models import Base
from app.router.llm_client import LLMResponse
from app.router.sales_catalog import (
    CandidatoProduto,
    SalesCatalogClient,
    VendaSlots,
    extract_sales_slots,
    extrair_termos_busca,
)


async def _cria_produto(session, **overrides):
    defaults = dict(
        nome="Gerador Diesel GD-15",
        descricao="Potência de 15 kVA.",
        preco=Decimal("24900.00"),
        categoria="geradores",
    )
    defaults.update(overrides)
    return await criar_produto(session, **defaults)


@pytest.fixture
async def factory():
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield create_session_factory(engine)
    await engine.dispose()


def test_extrair_termos_busca_remove_stopwords_e_palavras_curtas():
    termos = extrair_termos_busca("Olá, eu queria saber se vocês têm um gerador de 15 kVA")

    assert "gerador" in termos
    assert "ola" not in termos
    assert "queria" not in termos
    assert "um" not in termos
    assert "de" not in termos


def test_extrair_termos_busca_normaliza_acentos():
    termos = extrair_termos_busca("Preciso de uma cabine de insonorização")

    assert "insonorizacao" in termos


def test_extrair_termos_busca_mensagem_sem_termos_significativos_devolve_lista_vazia():
    assert extrair_termos_busca("Oi, tudo bem?") == []


def test_extrair_termos_busca_preserva_codigos_de_produto_com_digitos():
    termos = extrair_termos_busca("Preciso do GD-15")
    assert "15" in termos


async def test_buscar_candidatos_encontra_por_nome(factory):
    async with factory() as session:
        await _cria_produto(session, nome="Gerador Diesel GD-15")
        await _cria_produto(session, nome="Cabine de Insonorização", categoria="cabines")
    client = SalesCatalogClient(factory)

    candidatos = await client.buscar_candidatos(["gerador"])

    assert len(candidatos) == 1
    assert candidatos[0].nome == "Gerador Diesel GD-15"


async def test_buscar_candidatos_encontra_por_categoria(factory):
    async with factory() as session:
        await _cria_produto(session, nome="GD-15", categoria="geradores")
        await _cria_produto(session, nome="CI-30", categoria="cabines")
    client = SalesCatalogClient(factory)

    candidatos = await client.buscar_candidatos(["geradores"])

    assert len(candidatos) == 1
    assert candidatos[0].nome == "GD-15"


async def test_buscar_candidatos_respeita_o_limite(factory):
    async with factory() as session:
        for i in range(15):
            await _cria_produto(session, nome=f"Gerador {i}")
    client = SalesCatalogClient(factory)

    candidatos = await client.buscar_candidatos(["gerador"], limite=10)

    assert len(candidatos) == 10


async def test_buscar_candidatos_sem_termos_devolve_lista_vazia(factory):
    client = SalesCatalogClient(factory)

    assert await client.buscar_candidatos([]) == []


async def test_buscar_candidatos_sem_match_devolve_lista_vazia(factory):
    async with factory() as session:
        await _cria_produto(session, nome="Gerador Diesel GD-15")
    client = SalesCatalogClient(factory)

    assert await client.buscar_candidatos(["parafuso"]) == []


async def test_consultar_detalhes_produto_inexistente_devolve_none(factory):
    client = SalesCatalogClient(factory)

    assert await client.consultar_detalhes(999, None, None) is None


async def test_consultar_detalhes_soma_estoque_entre_centros(factory):
    async with factory() as session:
        produto = await _cria_produto(session)
        await atualizar_estoque(session, produto.id, "CD-SP", 5)
        await atualizar_estoque(session, produto.id, "CD-RJ", 3)
        produto_id = produto.id
    client = SalesCatalogClient(factory)

    dados = await client.consultar_detalhes(produto_id, None, None)

    assert dados.estoque_total == 8
    assert dados.cotacao is None
    assert dados.compativel is None


async def test_consultar_detalhes_com_quantidade_calcula_cotacao(factory):
    async with factory() as session:
        produto = await _cria_produto(session, preco=Decimal("100.00"))
        await adicionar_desconto_volume(session, produto.id, 10, Decimal("10.00"))
        produto_id = produto.id
    client = SalesCatalogClient(factory)

    dados = await client.consultar_detalhes(produto_id, None, 10)

    assert dados.cotacao == (Decimal("100.00"), Decimal("10.00"), Decimal("900.00"))
    assert dados.quantidade == 10


async def test_consultar_detalhes_com_produto_relacionado_compativel(factory):
    async with factory() as session:
        produto = await _cria_produto(session, nome="QTA-100")
        relacionado = await _cria_produto(session, nome="GD-15")
        await criar_compatibilidade(session, produto.id, relacionado.id)
        produto_id, relacionado_id = produto.id, relacionado.id
    client = SalesCatalogClient(factory)

    dados = await client.consultar_detalhes(produto_id, relacionado_id, None)

    assert dados.produto_relacionado_nome == "GD-15"
    assert dados.compativel is True


async def test_consultar_detalhes_produto_relacionado_nao_compativel(factory):
    async with factory() as session:
        produto = await _cria_produto(session, nome="QTA-100")
        relacionado = await _cria_produto(session, nome="Cabine de Insonorização")
        produto_id, relacionado_id = produto.id, relacionado.id
    client = SalesCatalogClient(factory)

    dados = await client.consultar_detalhes(produto_id, relacionado_id, None)

    assert dados.compativel is False


async def test_consultar_detalhes_produto_relacionado_inexistente_ignora_compatibilidade(factory):
    async with factory() as session:
        produto = await _cria_produto(session)
        produto_id = produto.id
    client = SalesCatalogClient(factory)

    dados = await client.consultar_detalhes(produto_id, 999, None)

    assert dados.produto_relacionado_nome is None
    assert dados.compativel is None


class _FakeLLMClient:
    def __init__(self, response_text: str) -> None:
        self._text = response_text
        self.last_prompt: str | None = None

    async def generate(self, prompt: str) -> LLMResponse:
        self.last_prompt = prompt
        return LLMResponse(text=self._text, total_duration_ms=10.0)


async def test_extract_sales_slots_escolhe_o_produto_certo_entre_candidatos():
    candidatos = [
        CandidatoProduto(id=1, nome="Gerador Diesel GD-15", categoria="geradores"),
        CandidatoProduto(id=2, nome="Cabine de Insonorização", categoria="cabines"),
    ]
    llm = _FakeLLMClient('{"produto_id": 1, "produto_relacionado_id": null, "quantidade": 3}')

    slots = await extract_sales_slots("Quero 3 geradores GD-15", [], candidatos, llm)

    assert slots.produto_id == 1
    assert slots.quantidade == 3
    assert "Gerador Diesel GD-15" in llm.last_prompt
    assert "Cabine de Insonorização" in llm.last_prompt


async def test_extract_sales_slots_extrai_produto_relacionado_para_compatibilidade():
    candidatos = [
        CandidatoProduto(id=1, nome="QTA-100", categoria="quadros"),
        CandidatoProduto(id=2, nome="Gerador Diesel GD-15", categoria="geradores"),
    ]
    llm = _FakeLLMClient('{"produto_id": 1, "produto_relacionado_id": 2, "quantidade": null}')

    slots = await extract_sales_slots("O QTA-100 funciona com o GD-15?", [], candidatos, llm)

    assert slots.produto_id == 1
    assert slots.produto_relacionado_id == 2


async def test_extract_sales_slots_sem_match_devolve_produto_id_none():
    candidatos = [CandidatoProduto(id=1, nome="Gerador Diesel GD-15", categoria="geradores")]
    llm = _FakeLLMClient('{"produto_id": null, "produto_relacionado_id": null, "quantidade": null}')

    slots = await extract_sales_slots("Vocês vendem parafusos?", [], candidatos, llm)

    assert slots.produto_id is None


async def test_extract_sales_slots_resposta_nao_json_cai_em_fallback_vazio():
    candidatos = [CandidatoProduto(id=1, nome="Gerador Diesel GD-15", categoria="geradores")]
    llm = _FakeLLMClient("desculpe, não entendi")

    slots = await extract_sales_slots("oi", [], candidatos, llm)

    assert slots == VendaSlots()


async def test_extract_sales_slots_ignora_id_inventado_fora_da_lista_de_candidatos():
    # Achado de robustez (mesmo espírito de scheduling.py): o LLM pode
    # "inventar" um ID que não está na lista de candidatos apesar da
    # instrução do prompt — valida contra os IDs reais antes de devolver.
    candidatos = [CandidatoProduto(id=1, nome="Gerador Diesel GD-15", categoria="geradores")]
    llm = _FakeLLMClient('{"produto_id": 999, "produto_relacionado_id": null, "quantidade": null}')

    slots = await extract_sales_slots("Quero o produto X", [], candidatos, llm)

    assert slots.produto_id is None
