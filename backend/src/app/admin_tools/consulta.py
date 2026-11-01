"""Consulta SELECT pedida pelo Admin no chat (leitura, sem confirmação)."""

import json
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.safe_sql import execute_readonly_sql

TEMPO_MAX_MS = 5000

_PROMPT = """Você é um analista de dados PostgreSQL. O administrador perguntou: "{pergunta}".

{schema}

Responda APENAS com JSON válido: {{"sql": "SELECT ..."}}. Só SELECT; sem texto fora do JSON.
"""


async def executar_consulta(session: AsyncSession, sql: str) -> list[dict[str, Any]]:
    """Valida (safe_sql) e executa o SELECT com tempo máximo no Postgres.

    # MVP: o limite de tempo só existe no Postgres (`SET LOCAL statement_timeout`)
    # e a transação somente-leitura (`SET TRANSACTION READ ONLY`);
    # nos testes com SQLite a consulta roda sem ele.
    """
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        await session.execute(text(f"SET LOCAL statement_timeout = {TEMPO_MAX_MS}"))
        await session.execute(text("SET TRANSACTION READ ONLY"))
    return await execute_readonly_sql(session, sql)


async def gerar_sql(llm_client: Any, pergunta: str, schema: str) -> str | None:
    """Pede ao LLM o SELECT que responde `pergunta`; None se a resposta não for o JSON esperado."""
    resposta = await llm_client.generate(_PROMPT.format(pergunta=pergunta, schema=schema))
    bruto = getattr(resposta, "response", getattr(resposta, "text", str(resposta)))
    achado = re.search(r"\{.*\}", bruto, re.DOTALL)
    if not achado:
        return None
    try:
        sql = json.loads(achado.group(0)).get("sql")
    except json.JSONDecodeError:
        return None
    return sql.strip() if isinstance(sql, str) and sql.strip() else None
