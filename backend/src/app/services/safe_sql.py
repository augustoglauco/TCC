"""Motor de validação léxica e execução segura de consultas SQL somente-leitura
para o Agente Analítico de Gráficos Dinâmicos.
"""

import logging
import re
from decimal import Decimal
from typing import Any

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
            raise SQLSecurityError(f"Comando não permitido: instrução perigosa detectada ({match.group(0)}).")

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


async def execute_readonly_sql(
    session: AsyncSession, sql: str
) -> list[dict[str, Any]]:
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


def get_catalog_schema_prompt() -> str:
    """Retorna o esquema descritivo das tabelas disponíveis no PostgreSQL para que
    o LLM consiga formular consultas Text-to-SQL analíticas precisas.
    """
    return """
Tabelas e Colunas disponíveis para consulta (PostgreSQL):

1. produtos
   - id (INTEGER, PK)
   - nome (VARCHAR): Nome completo do produto (ex: 'Gerador Diesel GD-15')
   - descricao (TEXT)
   - preco (NUMERIC(10,2)): Preço unitário em Reais (R$)
   - preco_promocional (NUMERIC(10,2))
   - categoria (VARCHAR): Categoria do produto (ex: 'geradores', 'acessórios', 'Controle de Acesso')
   - ativo (BOOLEAN)

2. produto_estoque
   - produto_id (INTEGER, FK -> produtos.id)
   - centro_distribuicao (VARCHAR): Nome do CD (ex: 'CD-SP', 'CD-RJ')
   - quantidade (INTEGER): Quantidade física disponível em estoque

3. cliente_compras (Histórico de Vendas Concluídas)
   - id (INTEGER, PK)
   - cliente_id (INTEGER, FK -> clientes.id)
   - produto_id (INTEGER, FK -> produtos.id)
   - quantidade (INTEGER): Quantidade de unidades compradas
   - valor_total (NUMERIC(12,2)): Valor total da compra em Reais (R$)
   - comprado_em (TIMESTAMP WITH TIME ZONE)

4. clientes
   - id (INTEGER, PK)
   - nome (VARCHAR)
   - email (VARCHAR)

5. pedidos (Reservas e Pedidos de Venda)
   - id (UUID, PK)
   - status (VARCHAR): 'reservado', 'aprovado', 'cancelado'
   - user_email (VARCHAR)
   - criado_em (TIMESTAMP WITH TIME ZONE)

6. pedido_itens (Itens de Pedidos / Reservas)
   - id (UUID, PK)
   - pedido_id (UUID, FK -> pedidos.id)
   - produto_id (INTEGER, FK -> produtos.id)
   - centro_distribuicao (VARCHAR)
   - quantidade (INTEGER): Quantidade de unidades no pedido
   - preco_unitario (NUMERIC(10,2))

7. agendamentos
   - id (UUID, PK)
   - user_email (VARCHAR)
   - nome_cliente (VARCHAR)
   - status (VARCHAR): 'confirmado', 'cancelado'
   - data_hora_inicio (TIMESTAMP WITH TIME ZONE)

Regras para gerar SQL:
- Utilize apenas comandos SELECT.
- Para vendas totais por produto, cruze 'produtos' com 'cliente_compras' e/ou 'pedido_itens'.
- Sempre agrupe (GROUP BY) quando usar funções de agregação como SUM(quantidade), COUNT(*), SUM(valor_total).
- Ordene de forma decrescente pelo volume ou valor (ORDER BY ... DESC).
- Limite os resultados aos 10 ou 15 principais (LIMIT 15).
"""
