from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    local_model_base_url: str = "http://localhost:11434"
    local_model_name: str = "llama3.1:8b"

    external_model_base_url: str = "https://openrouter.ai/api/v1"
    external_model_api_key: str = "changeme"
    # MVP: sem default fixado — decidir o modelo (formato "provider/model" do
    # OpenRouter, ex.: "anthropic/claude-3.5-haiku") na hora do benchmark real
    # (ver docs/superpowers/specs/2026-09-05-roteador-basico-design.md §6).
    external_model_name: str = ""
    external_model_price_per_1k_input_tokens: float = 0.0
    external_model_price_per_1k_output_tokens: float = 0.0

    # --- Identificação de produto por imagem (R6, Fase 3) ---
    # Fluxo: imagem espontânea = identificação (padrão); OCR só quando o
    # sistema solicita comprovante (ver docs/ARCHITECTURE.md §4). Os três
    # parâmetros abaixo têm default aqui só para popular o frontend; são
    # ajustáveis em runtime via PUT /api/admin/runtime-settings.
    # Modelo de visão via OpenRouter (formato "provider/model", ex.:
    # "openai/gpt-4o-mini"). Vazio = fallback externo indisponível (o motor
    # responde "não identificado" em vez de chamar o externo).
    external_vision_model_name: str = ""
    external_vision_model_price_per_1k_input_tokens: float = 0.0
    external_vision_model_price_per_1k_output_tokens: float = 0.0
    # Limiar alto de aceite do catálogo interno (CLIP): melhor score >= este
    # valor aceita o interno sem chamar o externo.
    image_internal_confidence: float = 0.30
    # Confiança mínima que o modelo de visão externo precisa reportar para o
    # resultado ser aceito.
    image_external_confidence: float = 0.80

    # Provedor alternativo do classificador de intenção (além do MVP, ver
    # docs/ARCHITECTURE.md §5, decisão 2026-09-23). Reaproveita
    # external_model_api_key/external_model_base_url (mesma conta OpenRouter).
    # O til em "~typesafe/jev-latest" é parte do slug do modelo, não um
    # artefato de URL — sem ele o OpenRouter devolve 400 "Model ... does not
    # exist" (achado na verificação E2E da Task 6, confirmado com chamada
    # real à API).
    jev_model_name: str = "~typesafe/jev-latest"
    # Orçamento de timeout próprio do Jev, menor que o do LLM de chat externo
    # (achado da revisão final) — evita que um travamento na chamada custe
    # até external_llm_timeout_s (30s default) ao visitante antes do
    # fallback gracioso disparar.
    jev_timeout_s: float = 10.0

    # Monitor de Tom (R8, Fase 4B, além do MVP original — ver
    # docs/ARCHITECTURE.md §5, decisão 2026-09-23, e
    # docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md). Mesmo
    # padrão de dois provedores do classificador de intenção acima
    # (heuristica_llm/jev_openrouter) — ajustável em runtime via
    # PUT /api/admin/runtime-settings (ver app/api/runtime_settings.py).
    tone_monitor_enabled: bool = True
    tone_monitor_provider: Literal["heuristica_llm", "jev_openrouter"] = "heuristica_llm"

    # Tipado como Literal para falhar na carga das settings (erro claro) em vez
    # de estourar um ValueError obscuro dentro do classificador em runtime.
    router_complexity_strategy: Literal["heuristic", "llm"] = "heuristic"
    local_llm_timeout_s: float = 30.0
    external_llm_timeout_s: float = 30.0
    # MVP: sem default fixado — `None` mantém o comportamento de sempre
    # (usa a temperatura padrão do próprio modelo no Ollama, sem mandar
    # `options.temperature`). Ajustável em runtime via
    # `PUT /api/admin/runtime-settings` (ver `app/api/runtime_settings.py`).
    local_llm_temperature: float | None = None
    # 8192: com RAG top_k 5 e chunks de 768 tokens o prompt passa de 4 mil tokens, e o
    # padrão do Ollama (4096) corta o prompt em silêncio (resposta truncada, medido
    # em 2026-10-28). `None` volta ao padrão do Ollama.
    local_llm_num_ctx: int | None = 8192
    local_llm_top_p: float | None = None
    local_llm_top_k: int | None = None
    local_llm_repeat_penalty: float | None = None
    local_llm_seed: int | None = None
    # Keep-alive do modelo no Ollama: "-1" mantém na VRAM permanentemente (sem descarregar);
    # "5m" é o default do Ollama; "0" descarrega imediatamente após cada resposta.
    local_llm_keep_alive: str = "-1"
    # Pré-carregar modelo local na VRAM na inicialização do servidor (sem cold start).
    local_llm_warmup_on_startup: bool = True

    # MVP: tamanho fixo por config, sem troca automática por VRAM disponível
    # em runtime (ver docs/ARCHITECTURE.md §7).
    stt_model_size: str = "small"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    # Default da lib qdrant-client é 5s; em dev (WSL2), resolver "localhost"
    # às vezes demora mais que isso (ver `app/rag/qdrant_client.py`).
    qdrant_timeout_s: float = 10.0
    # Achado na revisão de robustez da Fase 9 (docs/ROADMAP.md): ao contrário
    # das outras dependências externas, a carga/inferência do CLIP não tinha
    # teto de tempo nenhum (ver `app/rag/clip_embedder.py`).
    clip_timeout_s: float = 30.0
    rag_top_k: int = 5
    rag_score_threshold: float = 0.35
    # Limiar de confiança do card de download do documento-fonte no chat
    # (Fase 8, além do MVP — ver docs/ARCHITECTURE.md §7): score do melhor
    # chunk >= este valor anexa `CardDocumentoDownload` à resposta.
    # MVP: limiar fixo, não editável em runtime (ao contrário de
    # rag_score_threshold) — sem decisão de arquitetura nova pedindo isso.
    rag_download_confidence_threshold: float = 0.65
    # MVP: desligado por padrão — o comportamento documentado em
    # docs/ARCHITECTURE.md (RAG vazio para o domínio → escala pro modelo
    # externo) depende da busca filtrada por domínio poder retornar vazio de
    # verdade. Ligar isso faz `search()` reforçar com uma segunda busca SEM
    # filtro de domínio quando a filtrada não acha nada — sacrifica o
    # isolamento entre domínios (pode trazer conteúdo de outro domínio) e
    # corrompe esse sinal de escalonamento (a busca quase nunca fica vazia).
    # Existe como flag para comparação/experimento (ver
    # `app.rag.qdrant_client.QdrantRAGClient.search`), não como recomendação.
    rag_search_domain_fallback: bool = False

    postgres_dsn: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/assistente"

    # MVP: disco local gerenciado pelo processo do backend, sem object
    # storage — coerente com o ambiente de desenvolvimento único deste
    # protótipo de TCC (ver
    # docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §3).
    rag_uploads_dir: str = "./data/rag_uploads"
    product_images_dir: str = "./data/product_images"

    # Agente autônomo de previsão de estoque (R13, docs/ARCHITECTURE.md).
    # E-mail por SMTP simples; sem `smtp_host`/`admin_alert_email` o alerta só
    # vai para a página /admin/mensagens. Valores reais só em `.env`.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True
    admin_alert_email: str = ""
    estoque_horizonte_dias: int = 10
    estoque_janela_consumo_dias: int = 30

    # Ferramentas de inteligência de código reunidas em `/admin/ferramentas`
    # (ver `app.api.admin_ferramentas`). O default do Graphify é relativo
    # ao diretório de onde o backend sobe (`backend/`). As duas URLs são as
    # PORTAS INTERNAS das UIs (Repowise 3012, GitNexus 4757), usadas para
    # sondar e para abrir quando o navegador está nesta máquina; de fora da
    # rede o frontend troca host e porta pelas públicas do Caddy (3002 e
    # 4747, `infra/caddy/Caddyfile.ferramentas`). A URL do Repowise aponta
    # para a visão geral DESTE repositório, cujo id vem do índice local.
    # MVP: sem descoberta de porta dinâmica; se a ferramenta subir em outra
    # porta, ajuste a variável de ambiente correspondente.
    graphify_out_dir: str = "../graphify-out"
    # Diretório dos resultados da avaliação experimental (Fase 10), lido pela
    # página pública `/avaliacao` — ver `app.api.avaliacao`.
    eval_dir: str = "eval"
    repowise_web_url: str = "http://localhost:3012/repos/98bf7b208ee54e9a840110278f8d9641/overview"
    gitnexus_web_url: str = "http://localhost:4757"

    # MVP: teto default (não rígido — o form do admin pode pedir mais por
    # execução, ver `app.api.crawler`) de páginas por execução do crawler de
    # páginas (R4). Ajustável em runtime via `PUT /api/admin/runtime-settings`
    # (ver docs/superpowers/specs/2026-09-19-crawler-paginas-design.md).
    crawler_max_pages: int = 20
    # Limiar de confiança do classificador de domínio do crawler:
    # `confidence >= limiar` ingere direto, abaixo vai pra fila de revisão
    # manual. Ajustável em runtime via `PUT /api/admin/runtime-settings`.
    crawler_confidence_threshold: float = 0.7

    # URL do servidor MCP de terceiro `calendar-mcp-server` (pacote PyPI,
    # https://github.com/deciduus/calendar-mcp), rodando localmente via
    # `calendar-mcp-server serve --transport http --port 8090` — substitui o
    # MCP oficial do Google (`calendarmcp.googleapis.com`), que está em
    # Developer Preview e não aceita contas Gmail pessoais (achado em
    # docs/ARCHITECTURE.md §5, 2026-09-23). Autenticação OAuth é gerenciada
    # pelo próprio `calendar-mcp-server` (`calendar-mcp-server auth`), não
    # por este backend.
    calendar_mcp_url: str = "http://127.0.0.1:8090/mcp"
    google_calendar_calendar_id: str = "primary"
    # Achado na revisão de robustez da Fase 9 (docs/ROADMAP.md): sem isso, o
    # cliente MCP herda o timeout de leitura padrão do SDK `mcp` (300s) — um
    # `calendar-mcp-server` travado (não caído, só sem responder) poderia
    # prender um turno de agendamento por até 5 minutos antes de cair em
    # `GoogleCalendarConnectionError`. Mesma ordem de grandeza dos outros
    # timeouts de dependência externa deste projeto (qdrant_timeout_s,
    # local/external_llm_timeout_s), não o padrão do SDK.
    calendar_mcp_timeout_s: float = 15.0

    # --- Validação de horário do agendamento (R11, Fase 4A) ---
    agendamento_timezone: str = "America/Sao_Paulo"
    agendamento_expediente_dias: str = "seg-sex"
    agendamento_expediente_inicio: str = "09:00"
    agendamento_expediente_fim: str = "18:00"

    # Só a própria máquina: os parceiros chegam pelo Caddy (HTTPS), que
    # repassa para cá (docs/ARCHITECTURE.md §6). Com `0.0.0.0` o acesso
    # direto pularia o HTTPS e a chave trafegaria em claro; outro valor gera
    # um aviso no log de `scripts/run_mcp_b2b_server.py`.
    mcp_b2b_host: str = "127.0.0.1"
    mcp_b2b_port: int = 8100
    # MVP: chave estática por parceiro (`nome:chave,nome2:chave2`), enviada
    # como `Authorization: Bearer <chave>`. Vazio = o servidor não sobe
    # (falha fechada, `app.mcp_server.auth.preparar_autenticacao`).
    mcp_b2b_partner_keys: str = ""
    # Endereço público pelo qual os parceiros chegam (via Caddy/HTTPS, ex.:
    # https://augustoglauco.duckdns.org:8443/mcp). Vazio = uso só local.
    mcp_b2b_public_url: str = ""

    # MVP: origens do frontend em dev, separadas por vírgula em uma única
    # variável — sem lista por ambiente/parceiro (isso seria necessário para
    # um deploy real, R2/R9). Mais de uma origem é necessária mesmo em dev
    # porque o mesmo frontend é acessado por localhost, IP da LAN e domínio
    # DuckDNS (achado do bug de acesso mobile, 2026-09-24).
    cors_allowed_origin: str = "http://localhost:3001"

    @property
    def cors_allowed_origins(self) -> list[str]:
        return [origem.strip() for origem in self.cors_allowed_origin.split(",") if origem.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
