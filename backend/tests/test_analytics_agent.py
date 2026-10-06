import json
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models import AdminChart, Produto
from app.services.analytics_agent import (
    extract_prompt_inline_data,
    process_dynamic_chart_request,
)


class _FakeChunk:
    def __init__(
        self,
        text: str,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
    ) -> None:
        self.text = text
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class _FakeLLMClientSql:
    """Simula um LLM cuja SQL gerada será rejeitada por `safe_sql` —
    usado para confirmar que o `SQLSecurityError` não derruba a sessão
    (achado da revisão de 2026-10-04: faltava `session.rollback()`)."""

    def __init__(self, sql: str) -> None:
        self._sql = sql

    async def generate_stream(self, prompt: str):
        payload = {
            "sql": self._sql,
            "titulo": "Gráfico Bloqueado",
            "x_key": "a",
            "y_keys": ["b"],
        }
        yield _FakeChunk(json.dumps(payload))


class _FakeLLMClientSqlComTokens:
    """Simula um LLM local que reporta uso de tokens no chunk final do
    stream — mesmo formato de `OllamaClient.generate_stream` (tokens só no
    último chunk, os demais vêm com `None`)."""

    async def generate_stream(self, prompt: str):
        payload = {
            "sql": "SELECT categoria, COUNT(*) as total FROM produtos GROUP BY categoria",
            "titulo": "Produtos por Categoria",
            "x_key": "categoria",
            "y_keys": ["total"],
        }
        yield _FakeChunk(json.dumps(payload))
        yield _FakeChunk("", prompt_tokens=120, completion_tokens=45)


def test_extract_prompt_inline_data_key_value():
    prompt = "crie um gráfico de barras com os dados: São Paulo: 150, Rio de Janeiro: 90, Belo Horizonte: 60"
    res = extract_prompt_inline_data(prompt)
    assert res is not None
    assert res["tipo_grafico"] == "bar"
    assert len(res["dados"]) == 3
    assert res["dados"][0]["categoria"] == "São Paulo"
    assert res["dados"][0]["valor"] == 150.0
    assert res["config"]["format"] == "number"


def test_extract_prompt_inline_data_currency():
    prompt = "gráfico de pizza: Vendas SP: R$ 5000, Vendas RJ: R$ 3200, Vendas MG: R$ 1800"
    res = extract_prompt_inline_data(prompt)
    assert res is not None
    assert res["tipo_grafico"] == "pie"
    assert len(res["dados"]) == 3
    assert res["config"]["format"] == "currency"


def test_extract_prompt_inline_data_none_when_no_data():
    prompt = "qual é o horário de atendimento?"
    assert extract_prompt_inline_data(prompt) is None

    prompt_sem_valores = "mostre o estoque de geradores"
    assert extract_prompt_inline_data(prompt_sem_valores) is None


@pytest.mark.asyncio
async def test_process_dynamic_chart_request_inline_data(db_session):
    prompt = "gere gráfico de barras: Projeto A: 40h, Projeto B: 65h, Projeto C: 20h"
    chart, explicacao, _prompt_tokens, _completion_tokens = await process_dynamic_chart_request(
        session=db_session,
        prompt=prompt,
        user_email="admin@teste.com",
        llm_client=None,
    )
    assert chart is not None
    assert isinstance(chart, AdminChart)
    assert chart.tipo_grafico == "bar"
    assert chart.sql_query == "dynamic_user_data"
    assert len(chart.dados_json) == 3
    assert chart.dados_json[1]["categoria"] == "Projeto B"
    assert chart.dados_json[1]["valor"] == 65.0


@pytest.mark.asyncio
async def test_process_dynamic_chart_request_sql_data(db_session):
    p1 = Produto(
        nome="Gerador Turbo 1",
        descricao="Gerador potente",
        preco=Decimal("5000.00"),
        categoria="Geradores",
    )
    p2 = Produto(
        nome="Gerador Turbo 2",
        descricao="Gerador potente",
        preco=Decimal("8000.00"),
        categoria="Geradores",
    )
    db_session.add_all([p1, p2])
    await db_session.commit()

    llm_client = _FakeLLMClientSql(
        sql="SELECT nome AS produto, preco AS total FROM produtos ORDER BY preco DESC"
    )

    prompt = "gere gráfico de produtos por faturamento"
    chart, explicacao, _prompt_tokens, _completion_tokens = await process_dynamic_chart_request(
        session=db_session,
        prompt=prompt,
        user_email="admin@teste.com",
        llm_client=llm_client,
    )
    assert chart is not None
    assert chart.sql_query.startswith("dynamic_sql:")
    assert len(chart.dados_json) >= 2
    assert (
        "produto" in chart.dados_json[0]
        or "nome" in chart.dados_json[0]
        or "categoria" in chart.dados_json[0]
    )


@pytest.mark.asyncio
async def test_process_dynamic_chart_request_sql_inseguro_nao_gera_grafico_sem_quebrar_sessao(
    db_session,
):
    """Decisão de 2026-10-06 (docs/ARCHITECTURE.md §5): não existe mais
    fallback para uma consulta hardcoded quando o SQL gerado é rejeitado
    pela validação de segurança — o pedido simplesmente não gera gráfico, com
    uma explicação do motivo. A sessão precisa continuar utilizável depois
    (achado da revisão de 2026-10-04, `session.rollback()`)."""
    p1 = Produto(
        nome="Gerador Turbo 1",
        descricao="Gerador potente",
        preco=Decimal("5000.00"),
        categoria="Geradores",
    )
    db_session.add(p1)
    await db_session.commit()

    llm_client = _FakeLLMClientSql(sql="SELECT * FROM app_settings")

    chart, explicacao, _prompt_tokens, _completion_tokens = await process_dynamic_chart_request(
        session=db_session,
        prompt="gere gráfico de produtos por faturamento",
        user_email="admin@teste.com",
        llm_client=llm_client,
    )

    assert chart is None
    assert "não é permitida" in explicacao.lower() or "segurança" in explicacao.lower()
    # Sessão não ficou numa transação quebrada — ainda dá pra usar
    await db_session.execute(select(Produto))


@pytest.mark.asyncio
async def test_erro_de_execucao_sql_nao_gera_grafico_sem_quebrar_sessao(db_session):
    # Cobre o SQL gerado pelo LLM que passa a validação léxica mas falha na
    # execução real (coluna inexistente).
    # # MVP: roda contra SQLite em memória (ver docstring de `db_session` em
    # conftest.py) — não reproduz o `PendingRollbackError` específico do
    # dialeto Postgres (produção) que motivou o `session.rollback()`
    # adicionado no `except` genérico de `_generate_sql_with_llm`'s chamador
    # (achado da revisão de 2026-10-04); mantém a correção mesmo sem um
    # teste que a prove neste ambiente.
    p1 = Produto(
        nome="Gerador Turbo 1",
        descricao="Gerador potente",
        preco=Decimal("5000.00"),
        categoria="Geradores",
    )
    db_session.add(p1)
    await db_session.commit()

    llm_client = _FakeLLMClientSql(sql="SELECT coluna_que_nao_existe FROM produtos")

    chart, explicacao, _prompt_tokens, _completion_tokens = await process_dynamic_chart_request(
        session=db_session,
        prompt="gere gráfico de produtos por faturamento",
        user_email="admin@teste.com",
        llm_client=llm_client,
    )

    assert chart is None
    assert explicacao
    # Sessão não ficou numa transação quebrada — ainda dá pra usar
    await db_session.execute(select(Produto))


@pytest.mark.asyncio
async def test_process_dynamic_chart_request_sql_dinamico_retorna_tokens_usados(db_session):
    """Achado de 2026-10-05 (usuário reportou que os tokens do modelo
    interno não apareciam em Métricas): o uso de tokens do LLM local era
    descartado na trilha de Text-to-SQL dinâmico (gráfico via chat), então
    essas chamadas nunca contribuíam para 'Tokens Internos (GPU Local)'."""
    p1 = Produto(
        nome="Gerador X", descricao="Gerador", preco=Decimal("5000.00"), categoria="Geradores"
    )
    db_session.add(p1)
    await db_session.commit()

    llm_client = _FakeLLMClientSqlComTokens()

    chart, explicacao, prompt_tokens, completion_tokens = await process_dynamic_chart_request(
        session=db_session,
        prompt="gere gráfico de produtos por categoria",
        user_email="admin@teste.com",
        llm_client=llm_client,
    )

    assert chart is not None
    assert prompt_tokens == 120
    assert completion_tokens == 45


@pytest.mark.asyncio
async def test_process_dynamic_chart_request_sem_llm_nao_gera_grafico(db_session):
    """Sem dados inline e sem llm_client (ex.: modelo local indisponível no
    momento), não há mais fallback hardcoded — o pedido não gera gráfico."""
    chart, explicacao, prompt_tokens, completion_tokens = await process_dynamic_chart_request(
        session=db_session,
        prompt="gere gráfico de produtos por faturamento",
        user_email="admin@teste.com",
        llm_client=None,
    )

    assert chart is None
    assert explicacao
    assert prompt_tokens is None
    assert completion_tokens is None


@pytest.mark.asyncio
async def test_process_dynamic_chart_request_sql_sem_resultado_nao_gera_grafico(db_session):
    """SQL válido e seguro, mas que não retorna nenhuma linha — não deve
    gerar um gráfico vazio nem cair em dado hardcoded; só explica o motivo."""
    llm_client = _FakeLLMClientSql(
        sql="SELECT nome FROM produtos WHERE nome = 'Produto Inexistente'"
    )

    chart, explicacao, _prompt_tokens, _completion_tokens = await process_dynamic_chart_request(
        session=db_session,
        prompt="gere gráfico de um produto que não existe",
        user_email="admin@teste.com",
        llm_client=llm_client,
    )

    assert chart is None
    assert "não encontrei dados" in explicacao.lower()
