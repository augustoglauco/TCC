"""Agente Analítico para Geração Dinâmica de Gráficos orientado por LLM.

Permite que o Administrador gere gráficos customizados a partir de:
1. Dados digitados diretamente no prompt (chave-valor, listas, tabelas);
2. Consultas Text-to-SQL seguras no PostgreSQL (produtos, compras, pedidos, estoque, etc.);
3. Fallback analítico resiliente.
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.background_tasks import spawn_background_task
from app.db.models import AdminChart
from app.services.ai_usage import registrar_uso_ia
from app.services.safe_sql import (
    SQLSecurityError,
    execute_readonly_sql,
    get_catalog_schema_prompt,
)

logger = logging.getLogger("assistente.analytics_agent")

_PALETTE = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4"]
_CMD_PREFIXES = ["dados:", "dados", "valores:", "valores", "gráfico:", "grafico:"]
_INLINE_PATTERN = (
    r"([A-Za-zÀ-ÖØ-öø-ÿ0-9\s\-_/]+)\s*[:=\-]\s*(?:R\$\s*)?"
    r"([\d\.,]+)\s*(%|h|unid|unidades|itens)?"
)


def _detect_chart_type(texto: str) -> str:
    t = texto.lower()
    if "pizza" in t or "circular" in t:
        return "pie"
    elif "donut" in t or "rosquinha" in t:
        return "donut"
    elif "linha" in t or "linhas" in t:
        return "line"
    elif "área" in t or "area" in t:
        return "area"
    return "bar"


def _clean_label(label_raw: str) -> str:
    label = label_raw.strip()
    for prefix in _CMD_PREFIXES:
        if label.lower().startswith(prefix):
            return label[len(prefix) :].strip()
    return label


def _parse_value(val_raw: str) -> float | None:
    clean = val_raw.replace(".", "").replace(",", ".") if "," in val_raw else val_raw
    try:
        return float(clean)
    except ValueError:
        return None


def _parse_inline_matches(matches: list[tuple[str, str, str]]) -> list[dict[str, Any]]:
    dados: list[dict[str, Any]] = []
    for label_raw, val_raw, _ in matches:
        label = _clean_label(label_raw)
        val = _parse_value(val_raw)
        if val is not None:
            dados.append({"categoria": label, "valor": val})
    return dados


def _build_inline_chart_spec(
    texto: str, dados: list[dict[str, Any]], formato: str, tipo_grafico: str
) -> dict[str, Any]:
    titulo = "Gráfico Personalizado"
    primeira_parte = texto.split(":")[0].strip()
    if len(primeira_parte) < 60 and (
        "gráfico" in primeira_parte.lower() or "grafico" in primeira_parte.lower()
    ):
        titulo = primeira_parte.capitalize()

    return {
        "titulo": titulo,
        "descricao": "Dados fornecidos diretamente no chat",
        "tipo_grafico": tipo_grafico,
        "config": {
            "x_key": "categoria",
            "y_keys": ["valor"],
            "labels": {"valor": "Valor"},
            "format": formato,
            "palette": _PALETTE,
        },
        "dados": dados,
        "sql_query": "dynamic_user_data",
    }


def extract_prompt_inline_data(prompt: str) -> dict[str, Any] | None:
    """Extrai pares de chave-valor numéricos digitados diretamente pelo usuário no texto.

    Exemplos aceitos:
    - 'São Paulo: 150, Rio de Janeiro: 90, Belo Horizonte: 60'
    - 'Projeto A = 40h\\nProjeto B = 65h\\nProjeto C = 20h'
    - 'Jan: R$ 1000, Fev: R$ 1500, Mar: R$ 1200'
    """
    if not prompt or len(prompt.strip()) < 8:
        return None

    texto = prompt.strip()
    matches = re.findall(_INLINE_PATTERN, texto, re.IGNORECASE)
    if len(matches) < 2:
        return None

    tem_moeda = "r$" in texto.lower() or "reais" in texto.lower()
    tem_pct = "%" in texto
    formato = "currency" if tem_moeda else ("percent" if tem_pct else "number")

    dados = _parse_inline_matches(matches)
    if len(dados) < 2:
        return None

    return _build_inline_chart_spec(texto, dados, formato, _detect_chart_type(texto))


async def _collect_stream_fields(
    llm_client: Any, system_instruction: str
) -> tuple[str, int | None, int | None, float | None, str | None]:
    """Drena o stream do LLM e devolve (raw_text, prompt_tokens, completion_tokens,
    estimated_cost_usd, model_name)."""
    raw_text = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    estimated_cost_usd: float | None = None
    model_name: str | None = None

    async for chunk in llm_client.generate_stream(system_instruction):
        if chunk.text:
            raw_text += chunk.text
        # Mesmo padrão do stream principal (orchestrator.py): tokens só
        # vêm populados no chunk final.
        if getattr(chunk, "prompt_tokens", None) is not None:
            prompt_tokens = chunk.prompt_tokens
        if getattr(chunk, "completion_tokens", None) is not None:
            completion_tokens = chunk.completion_tokens
        if getattr(chunk, "estimated_cost_usd", None) is not None:
            estimated_cost_usd = chunk.estimated_cost_usd
        if getattr(chunk, "model_name", None) is not None:
            model_name = chunk.model_name

    return raw_text, prompt_tokens, completion_tokens, estimated_cost_usd, model_name


async def _generate_sql_with_llm(
    llm_client: Any, prompt: str, session: AsyncSession, ambiente: str
) -> tuple[dict[str, Any] | None, int | None, int | None]:
    """Solicita ao LLM que gere a consulta Text-to-SQL e a especificação do
    gráfico. Devolve também `prompt_tokens`/`completion_tokens` usados pela
    chamada (achado de 2026-10-05: eram descartados, então essas chamadas ao
    modelo local nunca contavam em Métricas → Tokens Internos).

    `ambiente` ("interno"/"externo") é obrigatório porque o chamador já
    sabe qual cliente resolveu (`analytics_llm = local_client if
    local_client is not None else external_client` em
    `app.router.orchestrator`) — esta função não tem como inferir sozinha
    qual objeto recebeu."""
    if not llm_client or not hasattr(llm_client, "generate_stream"):
        return None, None, None

    schema_prompt = await get_catalog_schema_prompt(session)
    system_instruction = f"""Você é um analista de dados especialista em PostgreSQL e \
visualizações de dados.
O usuário solicitou um gráfico: "{prompt}".

{schema_prompt}

Responda OBRIGATORIAMENTE em formato JSON válido contendo:
{{
  "sql": "sua consulta SELECT otimizada aqui",
  "titulo": "Título claro do gráfico",
  "descricao": "Breve descrição dos dados",
  "tipo_grafico": "bar" ou "line" ou "pie" ou "donut" ou "area",
  "x_key": "nome da coluna no eixo X",
  "y_keys": ["nome da coluna métrica no eixo Y"],
  "format": "number" ou "currency" ou "percent",
  "labels": {{ "coluna_y": "Rótulo Amigável" }},
  "explicacao": "Uma frase resumindo os dados apresentados."
}}
NÃO inclua nada fora do bloco JSON.
"""
    try:
        (
            raw_text,
            prompt_tokens,
            completion_tokens,
            estimated_cost_usd,
            model_name,
        ) = await _collect_stream_fields(llm_client, system_instruction)
    except Exception as exc:
        logger.warning("falha_stream_llm_text_to_sql", extra={"erro": str(exc)})
        return None, None, None

    spawn_background_task(
        registrar_uso_ia(
            origem="admin",
            ambiente=ambiente,
            modelo=model_name or "desconhecido",
            operacao="geracao_grafico_dinamico",
            tokens_entrada=prompt_tokens,
            tokens_saida=completion_tokens,
            custo_usd=estimated_cost_usd,
            referencia_id=None,
            session=None,
            session_factory=None,
            commit=False,
        )
    )

    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        return None, prompt_tokens, completion_tokens
    try:
        return json.loads(match.group(0)), prompt_tokens, completion_tokens
    except json.JSONDecodeError as exc:
        logger.warning("falha_parse_json_llm_text_to_sql", extra={"erro": str(exc)})
        return None, prompt_tokens, completion_tokens


@dataclass
class _NovoGrafico:
    titulo: str
    descricao: str
    tipo_grafico: str
    config_json: dict[str, Any]
    dados_json: list[dict[str, Any]]
    sql_query: str
    criado_por: str


async def _persist_chart(session: AsyncSession, novo: _NovoGrafico) -> AdminChart:
    chart = AdminChart(
        titulo=novo.titulo,
        descricao=novo.descricao,
        tipo_grafico=novo.tipo_grafico,
        config_json=novo.config_json,
        dados_json=novo.dados_json,
        sql_query=novo.sql_query,
        fixado=True,
        ordem=0,
        criado_por=novo.criado_por,
    )
    session.add(chart)
    await session.commit()
    await session.refresh(chart)
    return chart


_MSG_INLINE_OK = (
    "Gerei o gráfico com os dados que você informou no chat. "
    "Ele já está salvo no seu painel de Dashboards."
)
_MSG_LLM_INDISPONIVEL = (
    "Não consegui gerar esse gráfico agora: o modelo de análise não "
    "está disponível no momento. Tente novamente em instantes."
)
_MSG_PEDIDO_NAO_INTERPRETADO = (
    "Não consegui interpretar esse pedido de gráfico. Tente "
    "descrever de forma mais específica o que você quer visualizar "
    "(ex.: 'gráfico de vendas por categoria nos últimos 30 dias')."
)
_MSG_SQL_BLOQUEADO = (
    "O modelo tentou gerar uma consulta que não é permitida por "
    "segurança. Tente reformular o pedido."
)
_MSG_SQL_FALHOU = (
    "Houve uma falha ao consultar o banco de dados para gerar esse gráfico. Tente novamente."
)
_MSG_SEM_DADOS = (
    "Não encontrei dados para esse pedido com os filtros atuais do "
    "sistema. Tente um período ou critério diferente."
)


async def _executar_sql_do_llm(
    session: AsyncSession, llm_spec: dict[str, Any]
) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Executa o SQL gerado pelo LLM. Devolve (dados, None) ou (None, mensagem de erro)."""
    try:
        return await execute_readonly_sql(session, llm_spec["sql"]), None
    except SQLSecurityError as exc:
        # Achado da revisão de 2026-10-04: antes caía no mesmo `except
        # Exception` genérico de baixo (falha de infraestrutura) — um sinal
        # de segurança (o LLM gerou SQL que tenta ler fora do esquema
        # permitido ou fazer escrita) ficava indistinguível de uma falha
        # transitória de banco no log, e a sessão nunca era revertida.
        await session.rollback()
        logger.warning(
            "sql_dinamico_bloqueado_por_seguranca",
            extra={"erro": str(exc), "sql": llm_spec.get("sql")},
        )
        return None, _MSG_SQL_BLOQUEADO
    except Exception as exc:
        # Intencional: qualquer falha de execução (banco, driver) vira mensagem
        # amigável ao admin, com rollback e log — nunca derruba o chat.
        await session.rollback()
        logger.warning("falha_execucao_sql_dinamico", extra={"erro": str(exc)})
        return None, _MSG_SQL_FALHOU


async def _persistir_grafico_do_llm(
    session: AsyncSession,
    llm_spec: dict[str, Any],
    dados: list[dict[str, Any]],
    prompt: str,
    user_email: str,
) -> AdminChart:
    colunas = list(dados[0].keys())
    return await _persist_chart(
        session,
        _NovoGrafico(
            titulo=llm_spec.get("titulo", "Gráfico Analítico"),
            descricao=llm_spec.get("descricao", "Gerado dinamicamente com base no banco de dados"),
            tipo_grafico=llm_spec.get("tipo_grafico", _detect_chart_type(prompt)),
            config_json={
                "x_key": llm_spec.get("x_key") or colunas[0],
                "y_keys": llm_spec.get("y_keys") or [colunas[1]],
                "labels": llm_spec.get("labels") or {},
                "format": llm_spec.get("format", "number"),
                "palette": _PALETTE,
            },
            dados_json=dados,
            sql_query=f"dynamic_sql: {llm_spec['sql']}",
            criado_por=user_email,
        ),
    )


async def _gerar_grafico_via_llm(
    session: AsyncSession, prompt: str, user_email: str, llm_client: Any, ambiente: str
) -> tuple[AdminChart | None, str, int | None, int | None]:
    """Trilha Text-to-SQL: LLM gera o SQL, executa read-only e persiste o gráfico."""
    llm_spec, prompt_tokens, completion_tokens = await _generate_sql_with_llm(
        llm_client, prompt, session, ambiente
    )
    if not llm_spec or "sql" not in llm_spec:
        return None, _MSG_PEDIDO_NAO_INTERPRETADO, prompt_tokens, completion_tokens

    dados, erro = await _executar_sql_do_llm(session, llm_spec)
    if erro:
        return None, erro, prompt_tokens, completion_tokens
    if not dados:
        return None, _MSG_SEM_DADOS, prompt_tokens, completion_tokens

    chart = await _persistir_grafico_do_llm(session, llm_spec, dados, prompt, user_email)
    explicacao = llm_spec.get("explicacao") or (
        f"Gerei o gráfico '{chart.titulo}' a partir de consulta direta ao banco de dados."
    )
    return chart, explicacao, prompt_tokens, completion_tokens


async def process_dynamic_chart_request(
    session: AsyncSession,
    prompt: str,
    user_email: str,
    llm_client: Any = None,
    *,
    ambiente: str,
) -> tuple[AdminChart | None, str, int | None, int | None]:
    """Processa a solicitação de gráfico do usuário, identificando a fonte de dados,
    executando as consultas necessárias e persistindo o AdminChart correspondente.

    Devolve também `(prompt_tokens, completion_tokens)` da chamada ao LLM —
    `None` quando a trilha percorrida não usa LLM (dados inline do usuário).

    Decisão registrada em docs/ARCHITECTURE.md §5 ("Agente Analítico de
    Gráficos Dinâmicos", 2026-10-06): não existe mais fallback para uma
    consulta hardcoded quando o Text-to-SQL falha — devolve `chart=None` com
    uma explicação do motivo, para o chamador informar o admin em vez de
    gerar um gráfico com dado potencialmente incorreto.
    """
    # 1. Verifica se o usuário forneceu dados no próprio texto
    inline_spec = extract_prompt_inline_data(prompt)
    if inline_spec:
        chart = await _persist_chart(
            session,
            _NovoGrafico(
                titulo=inline_spec["titulo"],
                descricao=inline_spec["descricao"],
                tipo_grafico=inline_spec["tipo_grafico"],
                config_json=inline_spec["config"],
                dados_json=inline_spec["dados"],
                sql_query="dynamic_user_data",
                criado_por=user_email,
            ),
        )
        return chart, _MSG_INLINE_OK, None, None

    # 2. Gera via Text-to-SQL dinâmico com o LLM — único caminho de geração
    # de gráfico novo a partir do banco (sem fallback hardcoded, ver docstring acima).
    if not llm_client or not hasattr(llm_client, "generate_stream"):
        return None, _MSG_LLM_INDISPONIVEL, None, None
    return await _gerar_grafico_via_llm(session, prompt, user_email, llm_client, ambiente)
