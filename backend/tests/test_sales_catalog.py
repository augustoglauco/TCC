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
from app.router.sales_catalog import SalesCatalogClient, extrair_termos_busca


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
