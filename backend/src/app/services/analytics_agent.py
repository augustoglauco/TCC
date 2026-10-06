"""Agente Analítico para Geração Dinâmica de Gráficos orientado por LLM.

Permite que o Administrador gere gráficos customizados a partir de:
1. Dados digitados diretamente no prompt (chave-valor, listas, tabelas);
2. Consultas Text-to-SQL seguras no PostgreSQL (produtos, compras, pedidos, estoque, etc.);
3. Fallback analítico resiliente.
"""

import json
import logging
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AdminChart
from app.services.safe_sql import (
    SQLSecurityError,
    execute_readonly_sql,
    get_catalog_schema_prompt,
)

logger = logging.getLogger("assistente.analytics_agent")


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


def extract_prompt_inline_data(prompt: str) -> dict[str, Any] | None:
    """Extrai pares de chave-valor numéricos digitados diretamente pelo usuário no texto.

    Exemplos aceitos:
    - 'São Paulo: 150, Rio de Janeiro: 90, Belo Horizonte: 60'
    - 'Projeto A = 40h\nProjeto B = 65h\nProjeto C = 20h'
    - 'Jan: R$ 1000, Fev: R$ 1500, Mar: R$ 1200'
    """
    if not prompt or len(prompt.strip()) < 8:
        return None

    texto = prompt.strip()
    # Padrão: Nome da categoria seguido por : ou = ou - e o valor numérico
    # Ex: 'São Paulo: 150', 'Item A: R$ 1.500,50', 'Fev: 30%'
    pattern = r"([A-Za-zÀ-ÖØ-öø-ÿ0-9\s\-_/]+)\s*[:=\-]\s*(?:R\$\s*)?([\d\.,]+)\s*(%|h|unid|unidades|itens)?"

    matches = re.findall(pattern, texto, re.IGNORECASE)
    if len(matches) < 2:
        return None

    # Detecta formato dominante
    tem_moeda = "r$" in texto.lower() or "reais" in texto.lower()
    tem_pct = "%" in texto

    formato = "currency" if tem_moeda else ("percent" if tem_pct else "number")
    tipo_grafico = _detect_chart_type(texto)

    dados: list[dict[str, Any]] = []
    for label_raw, val_raw, _ in matches:
        label = label_raw.strip()
        # Remove palavras de comando que possam ter ficado no primeiro label
        for prefix in ["dados:", "dados", "valores:", "valores", "gráfico:", "grafico:"]:
            if label.lower().startswith(prefix):
                label = label[len(prefix) :].strip()

        # Converte número considerando formato brasileiro (1.000,50) ou padrão (1000.50)
        clean_num = val_raw.replace(".", "").replace(",", ".") if "," in val_raw else val_raw
        try:
            val_float = float(clean_num)
        except ValueError:
            continue

        dados.append({"categoria": label, "valor": val_float})

    if len(dados) < 2:
        return None

    titulo = "Gráfico Personalizado"
    # Tenta extrair um título significativo do início da frase
    primeira_parte = texto.split(":")[0].strip()
    if len(primeira_parte) < 60 and (
        "gráfico" in primeira_parte.lower() or "grafico" in primeira_parte.lower()
    ):
        titulo = primeira_parte.capitalize()

    config = {
        "x_key": "categoria",
        "y_keys": ["valor"],
        "labels": {"valor": "Valor"},
        "format": formato,
        "palette": ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4"],
    }

    return {
        "titulo": titulo,
        "descricao": "Dados fornecidos diretamente no chat",
        "tipo_grafico": tipo_grafico,
        "config": config,
        "dados": dados,
        "sql_query": "dynamic_user_data",
    }


async def _generate_sql_with_llm(
    llm_client: Any, prompt: str, session: AsyncSession
) -> tuple[dict[str, Any] | None, int | None, int | None]:
    """Solicita ao LLM que gere a consulta Text-to-SQL e a especificação do
    gráfico. Devolve também `prompt_tokens`/`completion_tokens` usados pela
    chamada (achado de 2026-10-05: eram descartados, então essas chamadas ao
    modelo local nunca contavam em Métricas → Tokens Internos)."""
    if not llm_client or not hasattr(llm_client, "generate_stream"):
        return None, None, None

    schema_prompt = await get_catalog_schema_prompt(session)
    system_instruction = f"""Você é um analista de dados especialista em PostgreSQL e visualizações de dados.
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
        raw_text = ""
        prompt_tokens: int | None = None
        completion_tokens: int | None = None
        async for chunk in llm_client.generate_stream(system_instruction):
            if chunk.text:
                raw_text += chunk.text
            # Mesmo padrão do stream principal (orchestrator.py): tokens só
            # vêm populados no chunk final.
            if getattr(chunk, "prompt_tokens", None) is not None:
                prompt_tokens = chunk.prompt_tokens
            if getattr(chunk, "completion_tokens", None) is not None:
                completion_tokens = chunk.completion_tokens

        # Extrai bloco JSON
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if match:
            return json.loads(match.group(0)), prompt_tokens, completion_tokens
    except Exception as exc:
        logger.warning("falha_llm_text_to_sql", extra={"erro": str(exc)})

    return None, None, None


async def process_dynamic_chart_request(
    session: AsyncSession,
    prompt: str,
    user_email: str,
    llm_client: Any = None,
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
        chart = AdminChart(
            titulo=inline_spec["titulo"],
            descricao=inline_spec["descricao"],
            tipo_grafico=inline_spec["tipo_grafico"],
            config_json=inline_spec["config"],
            dados_json=inline_spec["dados"],
            sql_query="dynamic_user_data",
            fixado=True,
            ordem=0,
            criado_por=user_email,
        )
        session.add(chart)
        await session.commit()
        await session.refresh(chart)
        explicacao = (
            "Gerei o gráfico com os dados que você informou no chat. "
            "Ele já está salvo no seu painel de Dashboards."
        )
        return chart, explicacao, None, None

    # 2. Gera via Text-to-SQL dinâmico com o LLM — único caminho de geração
    # de gráfico novo a partir do banco (sem fallback hardcoded, ver
    # docstring acima).
    if not llm_client or not hasattr(llm_client, "generate_stream"):
        return (
            None,
            "Não consegui gerar esse gráfico agora: o modelo de análise não "
            "está disponível no momento. Tente novamente em instantes.",
            None,
            None,
        )

    llm_spec, prompt_tokens, completion_tokens = await _generate_sql_with_llm(
        llm_client, prompt, session
    )
    if not llm_spec or "sql" not in llm_spec:
        return (
            None,
            "Não consegui interpretar esse pedido de gráfico. Tente "
            "descrever de forma mais específica o que você quer visualizar "
            "(ex.: 'gráfico de vendas por categoria nos últimos 30 dias').",
            prompt_tokens,
            completion_tokens,
        )

    try:
        sql_query = llm_spec["sql"]
        dados = await execute_readonly_sql(session, sql_query)
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
        return (
            None,
            "O modelo tentou gerar uma consulta que não é permitida por "
            "segurança. Tente reformular o pedido.",
            prompt_tokens,
            completion_tokens,
        )
    except Exception as exc:
        await session.rollback()
        logger.warning("falha_execucao_sql_dinamico", extra={"erro": str(exc)})
        return (
            None,
            "Houve uma falha ao consultar o banco de dados para gerar esse "
            "gráfico. Tente novamente.",
            prompt_tokens,
            completion_tokens,
        )

    if not dados:
        return (
            None,
            "Não encontrei dados para esse pedido com os filtros atuais do "
            "sistema. Tente um período ou critério diferente.",
            prompt_tokens,
            completion_tokens,
        )

    chart = AdminChart(
        titulo=llm_spec.get("titulo", "Gráfico Analítico"),
        descricao=llm_spec.get("descricao", "Gerado dinamicamente com base no banco de dados"),
        tipo_grafico=llm_spec.get("tipo_grafico", _detect_chart_type(prompt)),
        config_json={
            "x_key": llm_spec.get("x_key") or list(dados[0].keys())[0],
            "y_keys": llm_spec.get("y_keys") or [list(dados[0].keys())[1]],
            "labels": llm_spec.get("labels") or {},
            "format": llm_spec.get("format", "number"),
            "palette": ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4"],
        },
        dados_json=dados,
        sql_query=f"dynamic_sql: {sql_query}",
        fixado=True,
        ordem=0,
        criado_por=user_email,
    )
    session.add(chart)
    await session.commit()
    await session.refresh(chart)
    explicacao = llm_spec.get("explicacao") or (
        f"Gerei o gráfico '{chart.titulo}' a partir de consulta direta ao banco de dados."
    )
    return chart, explicacao, prompt_tokens, completion_tokens
