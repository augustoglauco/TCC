"""Sobe o servidor MCP B2B (R12, Fase 5) como processo próprio, escutando em
`MCP_B2B_HOST:MCP_B2B_PORT` (default `127.0.0.1:8100`, ver `.env.example`) via
transporte `streamable-http` — mesmo transporte já usado pelo
`calendar-mcp-server` consumido em R11 (`app.mcp_client.google_calendar`).

# MVP: processo próprio (não embutido no backend FastAPI principal), mesmo
padrão de execução já usado para `calendar-mcp-server` (ver `goup.md`) —
mantém o MCP B2B isolado do processo do chat (falhas/reinícios de um não
afetam o outro) e reflete o papel de R12 como um serviço voltado a
consumidores externos (IAs de parceiros), distinto da API HTTP do chat.
Sem autenticação por parceiro nem exposição pública (ver
`docs/ARCHITECTURE.md` §5/§6): escuta só na própria máquina por padrão, e
qualquer outro `MCP_B2B_HOST` gera um aviso no log.

Uso (a partir de `backend/`, com o Postgres/Qdrant do docker-compose no ar e
a migração do Alembic já aplicada):

    .venv/bin/python scripts/run_mcp_b2b_server.py
"""

import logging

from app.config import get_settings
from app.db.engine import create_db_engine, create_session_factory
from app.logging_config import configure_logging
from app.mcp_server.b2b import create_b2b_mcp_server, host_somente_local
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    db_engine = create_db_engine(settings.postgres_dsn)
    session_factory = create_session_factory(db_engine)
    qdrant = QdrantRAGClient(
        host=settings.qdrant_host, port=settings.qdrant_port, timeout_s=settings.qdrant_timeout_s
    )
    embedders = EmbedderRegistry()

    server = create_b2b_mcp_server(session_factory, qdrant, embedders)

    logger.info(
        "mcp_b2b_server_iniciando host=%s port=%s", settings.mcp_b2b_host, settings.mcp_b2b_port
    )
    if not host_somente_local(settings.mcp_b2b_host):
        # MVP: não bloqueia (pode ser útil testar a partir de outra máquina),
        # mas deixa explícito que isso sai do escopo do MVP.
        logger.warning(
            "mcp_b2b_server_exposto_na_rede host=%s — sem autenticação por parceiro "
            "(MVP): qualquer máquina que alcance esta porta pode reservar pedidos "
            "e baixar estoque. Use MCP_B2B_HOST=127.0.0.1 fora de testes.",
            settings.mcp_b2b_host,
        )
    server.run(transport="streamable-http", host=settings.mcp_b2b_host, port=settings.mcp_b2b_port)


if __name__ == "__main__":
    main()
