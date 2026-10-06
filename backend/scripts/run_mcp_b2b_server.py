"""Sobe o servidor MCP B2B (R12, Fase 5) como processo próprio, escutando em
`MCP_B2B_HOST:MCP_B2B_PORT` (default `127.0.0.1:8100`, ver `.env.example`) via
transporte `streamable-http` — mesmo transporte já usado pelo
`calendar-mcp-server` consumido em R11 (`app.mcp_client.google_calendar`).

# MVP: processo próprio (não embutido no backend FastAPI principal), mesmo
padrão de execução já usado para `calendar-mcp-server` (ver `goup.md`) —
mantém o MCP B2B isolado do processo do chat (falhas/reinícios de um não
afetam o outro) e reflete o papel de R12 como um serviço voltado a
consumidores externos (IAs de parceiros), distinto da API HTTP do chat.

# MVP: exposição pública só com chave estática por parceiro (ver decisão de
2026-09-25 em `docs/ARCHITECTURE.md` §6). O servidor escuta em `127.0.0.1` e
os parceiros chegam pelo Caddy (HTTPS, `infra/caddy/Caddyfile`). Toda
requisição precisa de `Authorization: Bearer <chave>` (`MCP_B2B_PARTNER_KEYS`);
sem nenhuma chave configurada, o servidor não sobe. Outro `MCP_B2B_HOST`
gera um aviso no log, porque contorna o HTTPS do Caddy.

Uso (a partir de `backend/`, com o Postgres/Qdrant do docker-compose no ar e
a migração do Alembic já aplicada):

    .venv/bin/python scripts/run_mcp_b2b_server.py
"""

import logging
import sys

from app.config import get_settings
from app.db.engine import create_db_engine, create_session_factory
from app.logging_config import configure_logging
from app.mcp_server.auth import ChavesParceirosInvalidasError, preparar_autenticacao
from app.mcp_server.b2b import create_b2b_mcp_server, host_somente_local
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient
from app.router.ollama_client import OllamaClient
from app.router.openrouter_client import OpenRouterClient

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    try:
        autenticacao = preparar_autenticacao(
            settings.mcp_b2b_partner_keys,
            settings.mcp_b2b_public_url,
            settings.mcp_b2b_host,
            settings.mcp_b2b_port,
        )
    except ChavesParceirosInvalidasError as exc:
        # Falha fechada: melhor não subir do que subir aberto.
        logger.error("mcp_b2b_server_sem_autenticacao: %s", exc)
        sys.exit(1)

    db_engine = create_db_engine(settings.postgres_dsn)
    session_factory = create_session_factory(db_engine)
    qdrant = QdrantRAGClient(
        host=settings.qdrant_host, port=settings.qdrant_port, timeout_s=settings.qdrant_timeout_s
    )
    embedders = EmbedderRegistry()

    # Mesmos clientes que o backend FastAPI principal monta em `app.main`
    # (processo separado, não herda `app.state`) — usados só pela ferramenta
    # `converter_reserva_venda` (comprovante de pagamento), política de
    # custo mínimo registrada em docs/ARCHITECTURE.md §4 (achado de
    # 2026-10-06: antes não existiam aqui, então essa ferramenta nunca tinha
    # LLM nem visão nenhuma, só o fallback heurístico por regex).
    local_client = OllamaClient(
        base_url=settings.local_model_base_url,
        model=settings.local_model_name,
        timeout_s=settings.local_llm_timeout_s,
        temperature=settings.local_llm_temperature,
        num_ctx=settings.local_llm_num_ctx,
        top_p=settings.local_llm_top_p,
        top_k=settings.local_llm_top_k,
        repeat_penalty=settings.local_llm_repeat_penalty,
        seed=settings.local_llm_seed,
        keep_alive=settings.local_llm_keep_alive,
    )
    external_client = OpenRouterClient(
        base_url=settings.external_model_base_url,
        api_key=settings.external_model_api_key,
        model=settings.external_model_name,
        timeout_s=settings.external_llm_timeout_s,
        price_per_1k_input_tokens=settings.external_model_price_per_1k_input_tokens,
        price_per_1k_output_tokens=settings.external_model_price_per_1k_output_tokens,
        vision_model=settings.external_vision_model_name,
        price_per_1k_vision_input_tokens=settings.external_vision_model_price_per_1k_input_tokens,
        price_per_1k_vision_output_tokens=settings.external_vision_model_price_per_1k_output_tokens,
    )

    server = create_b2b_mcp_server(
        session_factory,
        qdrant,
        embedders,
        token_verifier=autenticacao.verificador,
        auth=autenticacao.auth,
        local_client=local_client,
        external_client=external_client,
    )

    logger.info(
        "mcp_b2b_server_iniciando host=%s port=%s url_publica=%s parceiros=%s",
        settings.mcp_b2b_host,
        settings.mcp_b2b_port,
        settings.mcp_b2b_public_url or "(só local)",
        ",".join(autenticacao.parceiros),
    )
    if not host_somente_local(settings.mcp_b2b_host):
        # Não bloqueia (a chave continua exigida), mas fora de 127.0.0.1 o
        # acesso não passa pelo HTTPS do Caddy e a chave trafega em claro.
        logger.warning(
            "mcp_b2b_server_exposto_na_rede host=%s — acesso direto sem HTTPS: a chave "
            "do parceiro trafega em texto claro. Use MCP_B2B_HOST=127.0.0.1 e o Caddy "
            "(infra/caddy/Caddyfile) na frente.",
            settings.mcp_b2b_host,
        )
    server.run(
        transport="streamable-http",
        host=settings.mcp_b2b_host,
        port=settings.mcp_b2b_port,
        transport_security=autenticacao.seguranca,
    )


if __name__ == "__main__":
    main()
