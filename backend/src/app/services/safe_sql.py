"""Motor de validação léxica e execução segura de consultas SQL somente-leitura
para o Agente Analítico de Gráficos Dinâmicos.
"""

import logging
import re
from decimal import Decimal
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("assistente.safe_sql")


class SQLSecurityError(ValueError):
    """Exceção levantada quando uma consulta viola as regras de segurança."""

    pass


ALLOWED_TABLES = {
    "produtos",
    "produto_estoque",
    "cliente_compras",
    "clientes",
    "pedidos",
    "pedido_itens",
    "agendamentos",
    "conversa_mensagens",
}

BLOCKED_PATTERNS = [
    r"\b(insert|update|delete|drop|alter|truncate|grant|revoke|create|replace)\b",
    r"\b(execute|exec|call|copy|vacuum|reindex|lock|pg_sleep)\b",
    # `SELECT ... INTO <tabela>` cria uma tabela nova a partir da consulta
    # (efetivamente DDL) — começa com SELECT como qualquer leitura legítima,
    # então sem este bloqueio passava pela checagem de "deve iniciar com
    # SELECT" acima sem cair em nenhum dos padrões de escrita (achado da
    # revisão de 2026-10-04).
    r"\binto\b",
    r"--",  # comentários de linha
    r"/\*",  # comentários em bloco
]

# Nomes de identificador simples (sem aspas/schema) usados para extrair
# tabelas referenciadas em FROM/JOIN e validar contra ALLOWED_TABLES abaixo.
_IDENTIFIER_RE = r"[a-zA-Z_][a-zA-Z0-9_]*"


def _validar_tabelas_permitidas(cleaned: str) -> None:
    """Garante que toda tabela referenciada em FROM/JOIN está em
    `ALLOWED_TABLES` — defesa em profundidade além do bloqueio de palavras-
    chave de escrita acima: mesmo um SELECT "limpo" não pode ler tabelas
    fora do esquema exposto ao LLM via `get_catalog_schema_prompt` (achado
    da revisão de 2026-10-04: `ALLOWED_TABLES` existia mas nunca era usado).

    # MVP: extração de tabelas por regex sobre FROM/JOIN, não um parser SQL
    completo — suficiente para o conjunto de consultas geradas pelo Agente
    Analítico (sem SQL dinâmico vindo do usuário final, só do LLM a partir
    do esquema fixo documentado).
    """
    cte_names = {
        nome.lower()
        for nome in re.findall(rf"\b({_IDENTIFIER_RE})\s+as\s*\(", cleaned, re.IGNORECASE)
    }
    tabelas_referenciadas = {
        nome.lower()
        for nome in re.findall(rf"\b(?:from|join)\s+({_IDENTIFIER_RE})", cleaned, re.IGNORECASE)
    }
    nao_permitidas = tabelas_referenciadas - cte_names - ALLOWED_TABLES
    if nao_permitidas:
        raise SQLSecurityError(
            f"Tabela(s) não permitida(s) na consulta: {', '.join(sorted(nao_permitidas))}."
        )


def validate_readonly_sql(sql: str) -> str:
    """Valida se a instrução SQL é estritamente de leitura (SELECT), sem injeção,
    sem múltiplos comandos e com limitação de registros.
    """
    if not sql or not sql.strip():
        raise SQLSecurityError("Consulta SQL vazia.")

    cleaned = sql.strip()

    # Remove ponto e vírgula no final se houver
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()

    # Bloqueia ponto e vírgula interno (múltiplas instruções)
    if ";" in cleaned:
        raise SQLSecurityError("Múltiplas instruções SQL não são permitidas.")

    # Deve começar com SELECT ou WITH (CTE iniciando consulta de leitura)
    if not re.match(r"^(select|with)\b", cleaned, re.IGNORECASE):
        raise SQLSecurityError("Comando não permitido: a consulta deve iniciar com SELECT.")

    # Verifica palavras-chave perigosas de escrita/DDL/funções de sistema
    for pattern in BLOCKED_PATTERNS:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            raise SQLSecurityError(
                f"Comando não permitido: instrução perigosa detectada ({match.group(0)})."
            )

    _validar_tabelas_permitidas(cleaned)

    # Garante limite máximo de 50 registros
    limit_match = re.search(r"\blimit\s+(\d+)\b", cleaned, re.IGNORECASE)
    if limit_match:
        val = int(limit_match.group(1))
        if val > 50:
            cleaned = re.sub(r"\blimit\s+\d+\b", "LIMIT 50", cleaned, flags=re.IGNORECASE)
    else:
        cleaned = f"{cleaned}\nLIMIT 50"

    return cleaned


async def execute_readonly_sql(session: AsyncSession, sql: str) -> list[dict[str, Any]]:
    """Executa de forma segura uma consulta SQL somente-leitura e retorna
    uma lista de dicionários com tipos serializáveis em JSON.
    """
    safe_query = validate_readonly_sql(sql)
    logger.info("executando_sql_analitico", extra={"sql": safe_query})

    res = await session.execute(text(safe_query))
    mappings = res.mappings().all()

    registros: list[dict[str, Any]] = []
    for row in mappings:
        item: dict[str, Any] = {}
        for key, val in row.items():
            if isinstance(val, Decimal):
                item[key] = float(val)
            elif hasattr(val, "isoformat"):
                item[key] = val.isoformat()
            else:
                item[key] = val
        registros.append(item)

    return registros


# Descrições curtas de cada tabela (contexto de negócio que a introspecção
# do banco não traz sozinha).
_TABLE_DESCRIPTIONS: dict[str, str] = {
    "produtos": "Catálogo de produtos.",
    "produto_estoque": "Estoque de cada produto por centro de distribuição.",
    "cliente_compras": "Histórico de compras já concluídas de clientes antigos (dados fixos).",
    "clientes": "Clientes cadastrados.",
    "pedidos": "Cabeçalho de reservas/pedidos feitos pelo chat ou site.",
    "pedido_itens": "Itens de cada pedido/reserva — uma linha por produto no carrinho.",
    "agendamentos": "Agendamentos de visita.",
    "conversa_mensagens": "Mensagens trocadas no chat (cliente e assistente).",
}

# Notas semânticas curadas à mão para colunas "tipo enum" sem CHECK
# constraint no banco — a introspecção automática abaixo não tem de onde
# descobrir os valores válidos desses campos. Decisão registrada em
# docs/ARCHITECTURE.md §5 ("Agente Analítico de Gráficos Dinâmicos",
# 2026-10-06): achado concreto que motivou isso — o texto anterior (escrito
# à mão, sem introspecção nenhuma) descrevia `pedidos.status` como
# 'reservado'/'aprovado'/'cancelado', sem o valor real `venda_concluida`
# usado em todo o resto do sistema, então o LLM nunca tinha como filtrar
# venda efetivada corretamente.
# `# MVP: exige atualização manual se um novo valor de status for
# introduzido — risco aceito, mesmo padrão de documentação manual já usado
# em outras partes do projeto.`
_SEMANTIC_NOTES: dict[str, str] = {
    "pedidos": (
        "   Nota: `status` é texto livre (sem constraint no banco). Valores reais "
        "usados pelo sistema: 'reservado' (reserva ainda não paga), "
        "'venda_concluida' (ÚNICO valor que representa venda efetivada) e "
        "'pagamento_divergente'. Para 'vendas'/'faturamento' reais a partir de "
        "pedido_itens, SEMPRE filtre pedidos.status = 'venda_concluida'."
    ),
    "cliente_compras": (
        "   Nota: toda linha aqui já é uma venda concluída (histórico fixo) — "
        "não precisa (nem existe) filtro de status nesta tabela."
    ),
}

_SCHEMA_RULES = """
Regras para gerar SQL:
- Utilize apenas comandos SELECT.
- Para vendas totais por produto, cruze 'produtos' com 'cliente_compras' e/ou
  'pedido_itens' (filtrando pedidos.status = 'venda_concluida' ao usar pedido_itens).
- Sempre agrupe (GROUP BY) quando usar funções de agregação como SUM(quantidade),
  COUNT(*), SUM(valor_total).
- Ordene de forma decrescente pelo volume ou valor (ORDER BY ... DESC).
- Limite os resultados aos 10 ou 15 principais (LIMIT 15).
"""


async def get_catalog_schema_prompt(session: AsyncSession) -> str:
    """Gera a descrição do esquema das tabelas permitidas a partir do banco de
    dados real, para que o LLM formule consultas Text-to-SQL precisas.

    Introspecção via `sqlalchemy.inspect` (dialect-agnostic — roda igual
    contra Postgres em produção e SQLite nos testes), restrita às mesmas
    tabelas de `ALLOWED_TABLES` (a whitelist de segurança não muda, só a
    fonte da descrição de colunas/tipos deixa de ser um texto escrito à
    mão). Decisão registrada em docs/ARCHITECTURE.md §5, 2026-10-06.
    """
    conn = await session.connection()

    def _reflect(sync_conn: Any) -> dict[str, list[dict[str, Any]]]:
        inspector = sa_inspect(sync_conn)
        return {
            tabela: inspector.get_columns(tabela)
            for tabela in sorted(ALLOWED_TABLES)
            if inspector.has_table(tabela)
        }

    tabelas_colunas = await conn.run_sync(_reflect)

    linhas = ["Tabelas e Colunas disponíveis para consulta:\n"]
    for i, (tabela, colunas) in enumerate(tabelas_colunas.items(), start=1):
        descricao = _TABLE_DESCRIPTIONS.get(tabela, "")
        cabecalho = f"{i}. {tabela}" + (f" ({descricao})" if descricao else "")
        linhas.append(cabecalho)
        for col in colunas:
            nullable = "" if col.get("nullable", True) else ", NOT NULL"
            linhas.append(f"   - {col['name']} ({col['type']}{nullable})")
        if tabela in _SEMANTIC_NOTES:
            linhas.append(_SEMANTIC_NOTES[tabela])
        linhas.append("")

    linhas.append(_SCHEMA_RULES.strip())
    return "\n".join(linhas)
