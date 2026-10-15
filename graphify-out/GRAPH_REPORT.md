# Graph Report - TCC  (2026-10-14)

## Corpus Check
- 366 files · ~448,506 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2940 nodes · 6931 edges · 194 communities (164 shown, 30 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 471 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `512e2455`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- useChatStore.ts
- EmbedderRegistry
- comprovante_evaluator.py
- classifier.py
- b2b.py
- api/chat.py
- get_settings
- listar_ferramentas
- TextEmbedder
- RAGClient
- QdrantRAGClient
- Manual Didático: GitNexus no Ambiente de Desenvolvimento Agêntico (WSL2, Antigravity IDE, Claude CLI)
- sqlalchemy
- mcp_server/auth.py
- processar_conversao_comprovante
- ChatModal
- useAuthStore
- rag_collections.py
- db/catalog.py
- ai_usage_report.py
- metricas/page.tsx
- Guia Claude Code CLI
- OpenRouterModelCard.tsx
- ChatModal.tsx
- types/chat.ts
- models.py
- PullModelForm.tsx
- sales_catalog.py
- PlaygroundPanel.tsx
- post_converter_auto_admin
- OllamaClient
- Conversa
- ingestao/page.tsx
- agendamentos.py
- obter_produto
- api/crawler.ts
- LocalModelsTable.tsx
- api/orders.py
- B2BMCPClient
- adminAtendimento.ts
- OpenRouterClient
- ClipEmbedder
- orchestrator.py
- analytics_agent.py
- post_close_conversa
- models/rag.py
- dashboards/page.tsx
- collections_abc
- cliente_mcp_b2b.py
- characteristics.py
- orders.ts
- api/rag.ts
- .describe_image
- api/local_models.py
- adminPedidos.ts
- ClipImageStore
- getApiBaseUrl
- google_calendar.py
- types/rag.ts
- compilerOptions
- Base
- devDependencies
- api/image_search.py
- api/agendamentos.ts
- GoogleCalendarMCPClient
- app.py
- DocumentsTable.tsx
- whisper_client.py
- api/runtime_settings.py
- RagDocument Model (PostgreSQL)
- Refactoring with GitNexus
- Injeção de Dados Estruturados de Catálogo no Prompt
- scripts
- Manual Didático: Repowise no Ambiente de Desenvolvimento Agêntico (WSL2, Antigravity IDE, Claude CLI, Kiro CLI)
- GitNexus CLI Commands
- Especificação Arquitetural: Ledger Unificado de Uso de IA
- GitNexus Guide
- Aplicação Cliente Independente MCP B2B
- Manual do Administrador do Sistema
- Manual do Usuário e Cliente
- Mapeamento de Prompts e Instruções LLM
- Manual do Strata
- Protocolo Unificado de Streaming SSE no Chat
- Runtime In-Memory Model Switching
- dependencies
- chunk_size_search.py
- api/crawler.py
- pdf_extract.py
- next.config.ts
- _build_prompt
- Amarração Dual Postgres e Qdrant por Document ID
- Transbordo Human-in-the-Loop com Lock Atômico
- Contabilização Segregada de Tokens e Custos de LLM
- Transversal Tone Monitoring Architecture
- Crawler Human Review Queue for Uncertain Confidence
- Google Calendar MCP Client
- Multimodal Receipt Evaluation Pipeline
- AudioRecorder
- Bateria de Perguntas de Ground Truth RAG
- Plano de Implementação de Segurança Contra Prompt Injection e Abuso MCP
- Máquina de Estados de Agendamento por Slots
- SalesCatalogClient (Direct Database Access)
- Segregated Prompt & Completion Cost Calculation
- main.py
- g.sh
- Gerenciador Assíncrono de Modelos Ollama
- Serviço registrar_uso_ia e Gerenciamento de Sessão Global
- eslint.config.mjs
- .prettierrc.json
- rules/graphify.md
- LocalModel
- api/chat.ts
- workflows/graphify.md
- Ambiente Antigravity IDE
- Widget de Chat Multimodal
- Orquestrador Híbrido de LLM
- Router Orchestration Flow
- Benchmark de Acurácia do Roteador de Intenções
- extractor.py
- jsdom
- @playwright/test
- tailwindcss
- Regras de Escopo do MVP
- Endpoint GET /api/admin/metrics/ai-usage
- catalog_extractor/__init__.py
- src/__init__.py
- Assimetria Intencional dos Domínios no MVP
- Reaproveitamento de Visão no Modelo Residente
- Modelo AiUsageEvent e Migração Alembic 0024
- Migração sem Dual-Write de IngestionCostEvent
- Regras e Convenções de Agente Next.js
- postcss.config.mjs
- Requisito R10: Classificação do Perfil de Usuário
- Requisito R5: Transcrição STT Whisper
- Requisito R9: Memória de Sessão e Resumos
- Avaliação 3: Latência Local vs Externo
- Captura de Metadados de Uso do TypeSafe Jev
- Agregação Diária no Fuso Horário Local
- assistente-multimodal-backend
- cliente-mcp-b2b
- @testing-library/react
- @testing-library/user-event
- @types/react-dom
- typescript
- ambiguous_python_import_63d38ea20e69
- Impact Analysis with GitNexus
- get_escalonamentos
- SearchableSelect.tsx
- api/auth.py
- catalog_extractor.py
- Debugging with GitNexus
- Exploring Codebases with GitNexus
- get_public_produtos
- CatalogImportModal.tsx
- atualizar_resumo
- GitNexus — Code Intelligence
- CalendarClient
- VisionResult
- useEstaNoCliente
- image_processor.py
- layout.tsx
- ._perguntar_systemone_jev
- db_connector.py
- pull_model_endpoint
- ferramentas/page.tsx
- store.py
- run_mcp_b2b_server.py
- .pull_model_streaming
- require_admin
- chat_closure_service.py
- settings.py
- get_model_catalog_http_client
- parceiro_atual
- EstoqueInsuficienteError
- admin_products.py
- detect_chart_request
- CategoryFilter.tsx
- eslint-config-next

## God Nodes (most connected - your core abstractions)
1. `getApiBaseUrl()` - 82 edges
2. `useAuthStore` - 78 edges
3. `QdrantRAGClient` - 58 edges
4. `OllamaClient` - 46 edges
5. `handle_message()` - 45 edges
6. `RAGConnectionError` - 45 edges
7. `create_b2b_mcp_server()` - 43 edges
8. `send_message()` - 42 edges
9. `Conversa` - 34 edges
10. `EmbedderRegistry` - 33 edges

## Surprising Connections (you probably didn't know these)
- `Otimização de Chunk Size por Bisseção` --conceptually_related_to--> `Requisito R4: RAG Multimodal Híbrido`  [INFERRED]
  backend/eval/rag_quality/README.md → docs/ARCHITECTURE.md
- `Políticas de Troca, Devolução e Garantia` --shares_data_with--> `Requisito R4: RAG Multimodal Híbrido`  [INFERRED]
  backend/scripts/sample_docs/atendimento/politicas_troca_garantia.txt → docs/ARCHITECTURE.md
- `Manual Técnico Resumido Gerador GD-30` --shares_data_with--> `Requisito R4: RAG Multimodal Híbrido`  [INFERRED]
  backend/scripts/sample_docs/suporte/manual_gerador_gd30.txt → docs/ARCHITECTURE.md
- `Catálogo de Geradores a Diesel Industrial` --shares_data_with--> `Requisito R4: RAG Multimodal Híbrido`  [INFERRED]
  backend/scripts/sample_docs/vendas/catalogo_geradores.txt → docs/ARCHITECTURE.md
- `Máquina de Estados de Agendamento por Slots` --semantically_similar_to--> `Resolução de Produtos em Duas Etapas (SQL + LLM)`  [INFERRED] [semantically similar]
  docs/superpowers/plans/2026-09-21-agendamento-mcp-calendar.md → docs/superpowers/plans/2026-09-24-orquestrador-mcp-b2b-vendas.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Ecossistema Tripartite de Desenvolvimento Agêntico** — docs_agentic_workflow_antigravity, docs_agentic_workflow_claude_cli, docs_agentic_workflow_kiro_cli [EXTRACTED 1.00]
- **Padrão de Arquitetura Dual MCP (Cliente e Servidor)** — docs_architecture_r11_mcp_calendar, docs_architecture_r12_mcp_b2b, goup_calendar_mcp_service, goup_mcp_b2b_service [EXTRACTED 1.00]
- **Baterias de Avaliação Experimental do TCC** — docs_evaluation_eval1_router, docs_evaluation_eval2_rag, docs_evaluation_eval3_latency, docs_evaluation_eval4_prompt_injection [EXTRACTED 1.00]
- **Customer Support Escalation and Human Handoff Flow** — docs_superpowers_specs_2026_09_23_monitor_de_tom_design_spec, docs_superpowers_specs_2026_10_03_atendimento_humano_transbordo_design_spec, docs_superpowers_specs_2026_09_29_gestao_agendamentos_design_spec [EXTRACTED 1.00]
- **MCP B2B Integration & Transactional Ecosystem** — docs_superpowers_specs_2026_09_21_ingestao_mcp_b2b_design_spec, docs_superpowers_specs_2026_09_24_orquestrador_mcp_b2b_vendas_design_spec, docs_superpowers_specs_2026_09_29_cliente_mcp_b2b_design_spec, docs_superpowers_specs_2026_10_05_conversao_reserva_venda_design_spec [EXTRACTED 1.00]
- **RAG Document Lifecycle from Ingestion to User Retrieval** — docs_superpowers_specs_2026_09_14_registro_documentos_rag_design_spec, docs_superpowers_specs_2026_09_15_rag_collections_config_design_spec, docs_superpowers_specs_2026_09_19_crawler_paginas_design_spec, docs_superpowers_specs_2026_10_04_download_documentos_rag_chat_design_spec [EXTRACTED 1.00]
- **Pipeline e Arquitetura do Ledger Unificado de Uso de IA** — docs_superpowers_specs_2026_10_08_ledger_uso_ia_origem_ambiente_modelo_design_dimensoes_ledger, docs_superpowers_plans_2026_10_08_ledger_uso_ia_item_a_fundacao_funcao_registrar_uso_ia, docs_superpowers_specs_2026_10_08_ledger_uso_ia_item_e_painel_design_semantica_null_vs_zero, docs_manuais_howto_administrador_metricas_ledger_painel [EXTRACTED 1.00]
- **Pipeline de Defesa e Segurança Contra Prompt Injection** — docs_superpowers_plans_2026_10_07_seguranca_prompt_injection_mcp_modulo_prompt_safety, docs_superpowers_plans_2026_10_07_seguranca_prompt_injection_mcp_sandwich_prompting, docs_manuais_prompts_e_instrucoes_llm_prompt_orchestrator, docs_manuais_prompts_e_instrucoes_llm_prompt_injection_judge [EXTRACTED 1.00]
- **Ciclo de Vendas B2B, Integração MCP e Conversão Financeira** — docs_superpowers_plans_2026_09_24_orquestrador_mcp_b2b_vendas_injecao_catalogo_paralela, docs_superpowers_plans_2026_09_25_admin_produtos_catalogo_extracao_multimodal_catalogo, docs_superpowers_plans_2026_09_29_cliente_mcp_b2b_cliente_independente_streamlit, docs_superpowers_plans_2026_10_05_conversao_reserva_venda_comprovante_evaluator_multimodal [INFERRED 0.85]
- **Ciclo de Vida Conversacional, Escalonamento Humano e Auditoria de Custos** — docs_superpowers_plans_2026_09_23_monitor_de_tom_analise_paralela_sentimento, docs_superpowers_plans_2026_10_03_contabilizador_tokens_custos_ciclo_inatividade_conversa, docs_superpowers_plans_2026_10_05_atendimento_humano_transbordo_transbordo_human_in_the_loop [INFERRED 0.85]
- **Stack de Inferência Local e Otimização de Memória CUDA / MoE** — docs_manuais_strata_manual_strata_cuda_engine, docs_manuais_strata_manual_strata_memory_lifecycle, docs_manuais_headroom_manual_headroom_context_optimization, docs_manuais_howto_administrador_gestao_modelos_ia [INFERRED 0.85]
- **Evolução do Pipeline e Gestão de Documentos RAG** — docs_superpowers_plans_2026_09_14_registro_documentos_rag_registro_postgres_qdrant, docs_superpowers_plans_2026_09_15_rag_collections_config_perfis_collection, docs_superpowers_plans_2026_09_19_crawler_paginas_crawler_bfs, docs_superpowers_plans_2026_10_04_download_documentos_rag_chat_download_direto_chat [INFERRED 0.85]

## Communities (194 total, 30 thin omitted)

### Community 0 - "useChatStore.ts"
Cohesion: 0.19
Nodes (12): FAQ_ITEMS, ChatWidget(), fetchConversationSnapshot(), getOrCreateConversationId(), getUserConversationStorageKey(), getVisitPrompt(), HumanAttendanceStatus, LEGACY_STORAGE_KEY (+4 more)

### Community 1 - "EmbedderRegistry"
Cohesion: 0.12
Nodes (26): AsyncEngine, main(), _parse_args(), Script de ingestão das linhas de uma tabela do banco relacional no RAG (R4 —…, main(), main(), create_db_engine(), create_session_factory() (+18 more)

### Community 2 - "comprovante_evaluator.py"
Cohesion: 0.14
Nodes (15): Envolve `content` nas tags de `label`, escapando qualquer ocorrência literal de…, wrap_untrusted(), ComprovanteEvaluator, ParecerComprovante, _parse_decimal(), Any, Decimal, Serviço de análise, extração e auditoria financeira de comprovantes de… (+7 more)

### Community 3 - "classifier.py"
Cohesion: 0.08
Nodes (46): Any, Fire-and-forget helper para tasks disparadas por um endpoint HTTP sem que a…, spawn_background_task(), AiUsageEvent, Ledger unificado de uso de IA — todo ponto do sistema que chama um…, classify_page(), Classificação de domínio de páginas crawleadas via LLM externo (R4, Fase 2) —…, Classifica o texto de uma página crawleada. Qualquer falha de parse do JSON… (+38 more)

### Community 4 - "b2b.py"
Cohesion: 0.10
Nodes (41): create_b2b_mcp_server(), host_somente_local(), Any, async_sessionmaker, AsyncSession, AuthSettings, Servidor MCP B2B provido pela empresa (R12, Fase 5) — expõe os 4 recursos de…, `True` se o servidor, escutando em `host`, só aceita conexões da própria… (+33 more)

### Community 5 - "api/chat.py"
Cohesion: 0.04
Nodes (87): _carregar_contexto_anterior_seguro(), _carregar_contexto_seguro(), _carregar_conversa_db_segura(), _carregar_dados_cliente_seguro(), deletar_conversa(), _escalar_conversa_em_background(), fechar_conversa_endpoint(), get_calendar_client() (+79 more)

### Community 6 - "get_settings"
Cohesion: 0.14
Nodes (21): main(), Script para zerar totalmente os produtos no Postgres e os pontos no Qdrant.…, reset_ambiente(), post_confirmar_catalogo(), _get_base_dir(), obter_imagem_produto(), obter_imagem_temporaria(), get (+13 more)

### Community 7 - "listar_ferramentas"
Cohesion: 0.16
Nodes (15): _caminho_grafo_graphify(), FerramentasResposta, FerramentaStatus, listar_ferramentas(), obter_grafo_graphify(), BaseModel, get, Path (+7 more)

### Community 8 - "TextEmbedder"
Cohesion: 0.10
Nodes (24): chunk_text(), _normalizar_preservando_linhas(), Chunking de texto para ingestão no RAG (R4). # MVP: divisão por tamanho fixo de…, Colapsa espaços/tabs repetidos dentro de cada linha (como antes), mas preserva…, Divide `text` em pedaços de até `chunk_size` caracteres, com overlap.…, SentenceTransformer, Wrapper fino sobre `sentence-transformers`, com carga lazy do modelo. A…, Gera um embedding por texto de `texts`, na mesma ordem de entrada. (+16 more)

### Community 9 - "RAGClient"
Cohesion: 0.25
Nodes (7): _buscar_documentos_rag(), e_referencia_anterior(), _extrair_produtos_do_contexto(), _filtrar_documentos_relevantes_ao_contexto(), Extrai nomes/códigos de produtos citados no histórico recente ou na mensagem…, Protocol, RAGClient

### Community 10 - "QdrantRAGClient"
Cohesion: 0.06
Nodes (42): asyncio, _FixedCollectionRagClient, Implementa o Protocol `RAGClient` apontando para UMA collection fixa pelo nome,…, Script de ingestão de um pequeno conjunto de documentos de exemplo no RAG, na…, ActiveCollectionRagClient, async_sessionmaker, Adapter que implementa o Protocol `RAGClient` (usado pelo orchestrator)…, AdminAllCollectionsRagClient (+34 more)

### Community 11 - "Manual Didático: GitNexus no Ambiente de Desenvolvimento Agêntico (WSL2, Antigravity IDE, Claude CLI)"
Cohesion: 0.08
Nodes (24): 📌 1. Sumário de Recursos, Portas e Convivência no Ecossistema, 🔄 2. Convivência e Papéis: GitNexus vs. Repowise vs. Graphify, 3.1 Inicialização Interativa (Primeiro Plano), 3.2 Inicialização com Porta Customizada ou Acesso em Rede, 3.3 Inicialização em Segundo Plano (Background / Daemon), 3.4 Acesso no Navegador, 🌐 3. Inicialização e Uso da Interface Web (`gitnexus serve`), 4.1 Indexação Completa do Repositório (+16 more)

### Community 12 - "sqlalchemy"
Cohesion: 0.03
Nodes (4): alembic, sqlalchemy, sqlalchemy_dialects, sqlalchemy_dialects_postgresql

### Community 13 - "mcp_server/auth.py"
Cohesion: 0.06
Nodes (44): AccessToken, AutenticacaoMcpB2B, carregar_chaves_parceiros(), ChaveParceiroVerifier, ChavesParceirosInvalidasError, configuracao_auth(), _origem(), preparar_autenticacao() (+36 more)

### Community 14 - "processar_conversao_comprovante"
Cohesion: 0.33
Nodes (5): processar_conversao_comprovante(), Any, async_sessionmaker, AsyncSession, Avalia o comprovante de pagamento via ComprovanteEvaluator e converte o status…

### Community 15 - "ChatModal"
Cohesion: 0.14
Nodes (14): ChatModal(), handleClearHistory(), handleCloseConversation(), handleDrop(), handleRetry(), handleSolicitarAtendente(), submitAudio(), garantirBolha() (+6 more)

### Community 16 - "useAuthStore"
Cohesion: 0.13
Nodes (19): AdminUsuariosPage(), CadastroPage(), DEMO_ACCOUNTS, LoginPage(), PerfilPage(), HistoricoPedidosContent(), AdminGearMenu(), Header() (+11 more)

### Community 17 - "rag_collections.py"
Cohesion: 0.16
Nodes (30): activate_collection_endpoint(), create_collection_endpoint(), delete_collection_endpoint(), list_collections_endpoint(), AsyncSession, delete, get, post (+22 more)

### Community 18 - "db/catalog.py"
Cohesion: 0.10
Nodes (37): adicionar_desconto_volume(), atualizar_estoque(), atualizar_produto(), calcular_item_cotacao(), criar_compatibilidade(), criar_pedido(), criar_produto(), listar_categorias_distintas() (+29 more)

### Community 19 - "ai_usage_report.py"
Cohesion: 0.11
Nodes (28): AiUsageReport, get_ai_usage_metrics(), get, Request, Uso de IA do período, estratificado por origem × ambiente × modelo × operação,…, _Acumulador, _agrupar(), AiUsageReport (+20 more)

### Community 20 - "metricas/page.tsx"
Cohesion: 0.13
Nodes (29): AdminMetricasPage(), CardMetrica(), CardMetricaProps, AMBIENTES_CONHECIDOS, BLOCO_ZERADO, Props, ROTULOS, SecaoPorAmbiente() (+21 more)

### Community 21 - "Guia Claude Code CLI"
Cohesion: 0.06
Nodes (38): Regras de Workspace Antigravity, Princípio docs/ como Fonte Única da Verdade, Container PostgreSQL 15 (Porta 5433), Container Qdrant Vector DB (Porta 6335), Benchmark de Resiliência a Prompt Injection, Isolamento Sintático por Delimitador, Vulnerabilidade a Injeção Indireta via RAG, Otimização de Chunk Size por Bisseção (+30 more)

### Community 22 - "OpenRouterModelCard.tsx"
Cohesion: 0.12
Nodes (26): RagSearchConfigSection(), carregar(), handleToggle(), FREE_MODELS, OpenRouterModelCard(), init(), OpenRouterModelCardProps, POPULAR_MODELS (+18 more)

### Community 23 - "ChatModal.tsx"
Cohesion: 0.15
Nodes (16): RFC-4180, ChatModalProps, PendingError, PendingRetry, WELCOME_MESSAGE, EscalonamentoBanner(), EscalonamentoBannerProps, ImageUploader() (+8 more)

### Community 24 - "types/chat.ts"
Cohesion: 0.12
Nodes (23): AppointmentCard(), formatarDataHora(), ChatCard(), DocumentDownloadCard(), formatarTamanhoArquivo(), ProductCard(), QuoteCard(), BACKEND_LABELS (+15 more)

### Community 25 - "models.py"
Cohesion: 0.12
Nodes (36): delete_document_endpoint(), _document_to_response(), download_document_endpoint(), get_document_content_endpoint(), get_documents(), alias, AsyncSession, delete (+28 more)

### Community 26 - "PullModelForm.tsx"
Cohesion: 0.10
Nodes (31): CardComCaracteristicas(), formatarContexto(), formatarDataRelativa(), MODALIDADES_NAO_TEXTO, ModelCharacteristicsPanel(), ModelCharacteristicsPanelProps, NOMES_MODALIDADE, CardComCaracteristicas() (+23 more)

### Community 27 - "sales_catalog.py"
Cohesion: 0.07
Nodes (51): _buscar_detalhes(), _documento_relevante_para_produto(), _ficha_do_banco(), formatar_ficha_produto(), identify_product_by_image(), ImageIdentificationResult, _parse_vision_answer(), _produto_id_pelo_nome() (+43 more)

### Community 28 - "PlaygroundPanel.tsx"
Cohesion: 0.15
Nodes (8): ComparisonResultCard(), getScoreBadge(), PlaygroundForm(), PlaygroundManualModal(), PlaygroundManualModalProps, PlaygroundPanel(), handleSubmit(), PlaygroundResultItem

### Community 29 - "post_converter_auto_admin"
Cohesion: 0.14
Nodes (28): _calcular_total_pedido(), ConfirmarConversaoRequest, listar_pedidos_admin(), obter_pedido_admin(), post_analisar_comprovante(), post_confirmar_conversao(), post_converter_auto_admin(), post_converter_manual_simples() (+20 more)

### Community 30 - "OllamaClient"
Cohesion: 0.14
Nodes (7): OllamaClient, AsyncClient, setter, Descarrega o modelo da VRAM imediatamente (keep_alive: 0)., Consulta GET /api/ps para verificar se o modelo ativo está carregado na VRAM., Checa se `self._model` já está carregado na memória do Ollama (`GET /api/ps` —…, Cliente para o backend local via Ollama (docs/ARCHITECTURE.md §2). Além de…

### Community 31 - "Conversa"
Cohesion: 0.14
Nodes (31): Conversa, ConversaMensagem, Uma conversa do chat (R9, Fase 6) — ver decisão de 2026-09-25 em…, Uma mensagem de uma conversa: do cliente, a resposta do assistente (IA) ou de…, _carregar_clientes_por_email(), claim_conversa(), _com_fuso(), devolver_para_ia() (+23 more)

### Community 32 - "ingestao/page.tsx"
Cohesion: 0.14
Nodes (20): AbaConfiguracao(), AbaDocumentosIngeridos(), DOMAIN_OPTIONS, IngestaoDocumentosPage(), ModelosPage(), DocumentsTable(), confirmarExclusao(), Tabs (+12 more)

### Community 33 - "agendamentos.py"
Cohesion: 0.16
Nodes (21): admin_consultar_eventos_google(), admin_criar_agendamento_manual(), admin_listar_agendamentos(), AgendamentoManualCreate, AgendamentoOut, cancelar_agendamento(), get_calendar_client(), listar_meus_agendamentos() (+13 more)

### Community 34 - "obter_produto"
Cohesion: 0.14
Nodes (25): CompatibilidadePayload, delete_admin_produto(), delete_compatividade(), delete_desconto_volume(), delete_imagem_produto(), DescontoVolumePayload, EstoqueUpdatePayload, get_admin_categorias() (+17 more)

### Community 35 - "api/crawler.ts"
Cohesion: 0.14
Nodes (24): CrawlerPanel(), handleSubmit(), marcarAtividade(), LiveProgress, PROGRESSO_INICIAL, CrawlerReviewQueue(), handleApprove(), handleReject() (+16 more)

### Community 36 - "LocalModelsTable.tsx"
Cohesion: 0.13
Nodes (21): formatarDataRelativa(), formatarTamanho(), LocalModelsTable(), handleAtivar(), handleBaixarPreset(), LocalModelsTableProps, POPULAR_LOCAL_PRESETS, PresetLocalModel (+13 more)

### Community 37 - "api/orders.py"
Cohesion: 0.17
Nodes (27): calculate_freight_endpoint(), calculate_quote_endpoint(), create_order_endpoint(), get_order_endpoint(), list_orders_endpoint(), _map_order_to_out(), AsyncSession, get (+19 more)

### Community 38 - "B2BMCPClient"
Cohesion: 0.16
Nodes (7): B2BMCPClient, B2BMCPError, Any, Exception, Erro geral de comunicação com o MCP B2B., `itens`: `[{"produto_id": int, "quantidade": int, "centro_distribuicao": str}]`., Converte uma reserva pendente em venda concluída através de comprovante…

### Community 39 - "adminAtendimento.ts"
Cohesion: 0.17
Nodes (22): AdminAtendimentoPage(), ContextoClientePanel(), ContextoClientePanelProps, FilaEsperaPanel(), FilaEsperaPanelProps, formatEspera(), MeusChatsTabs(), MeusChatsTabsProps (+14 more)

### Community 40 - "OpenRouterClient"
Cohesion: 0.16
Nodes (6): OpenRouterClient, AsyncClient, setter, Envia uma imagem + prompt a um modelo de visão e devolve o texto cru. Usado…, `stream: true` no formato OpenAI-compatible — a resposta já vem em SSE (`data:…, Cliente para o backend externo via OpenRouter (docs/ARCHITECTURE.md §2).…

### Community 41 - "ClipEmbedder"
Cohesion: 0.17
Nodes (8): ClipEmbedder, InvalidImageError, Exception, SentenceTransformer, Gera um embedding CLIP por texto (mesmo espaço vetorial das imagens)., Bytes fornecidos não são uma imagem decodificável pelo PIL. Erro de entrada…, Wrapper fino sobre CLIP via sentence-transformers, com carga lazy. Mesmo padrão…, Gera um embedding CLIP por imagem (bytes PNG/JPG/WEBP).

### Community 42 - "orchestrator.py"
Cohesion: 0.06
Nodes (65): Agendamento, Registro de agendamento de visita técnica ou comercial (R11, Fase 7).…, GoogleCalendarConnectionError, Exception, Falha de rede/protocolo ao falar com o MCP do Google Calendar, ou a tool…, CardAgendamento, RagChunkMetric, Fonte (arquivo ingerido) e score de um chunk usado no contexto do RAG. (+57 more)

### Community 43 - "analytics_agent.py"
Cohesion: 0.07
Nodes (45): AdminChartCreate, AdminChartOut, AdminChartUpdate, create_admin_chart(), delete_admin_chart(), list_admin_charts(), AsyncSession, BaseModel (+37 more)

### Community 44 - "post_close_conversa"
Cohesion: 0.16
Nodes (20): ClaimRequest, CloseRequest, get_detalhes_conversa(), get_fila_espera(), get_meus_chats(), MensagemAtendenteRequest, post_claim_conversa(), post_close_conversa() (+12 more)

### Community 45 - "models/rag.py"
Cohesion: 0.13
Nodes (24): playground_search(), AsyncSession, post, Playground de busca comparativo entre collections (Entregas B+C+D, além do MVP)…, BinaryQuantizationRequest, CollectionCreateRequest, DocumentIngestResponse, HnswConfigRequest (+16 more)

### Community 46 - "dashboards/page.tsx"
Cohesion: 0.14
Nodes (25): AdminDashboardsPage(), CreateChartModal(), CreateChartModalProps, DataRow, AdminChartData, DynamicChartCard(), DynamicChartCardProps, TIPO_LABELS (+17 more)

### Community 47 - "collections_abc"
Cohesion: 0.13
Nodes (21): _avaliar_cliente(), _carregar_casos(), _julgar_resposta(), main(), Avalia resiliência comportamental a prompt injection (Fase 10, avaliação…, _avaliar_provider(), _carregar_casos(), main() (+13 more)

### Community 48 - "cliente_mcp_b2b.py"
Cohesion: 0.27
Nodes (11): argparse, _descrever_erro(), main(), Cliente de teste do MCP B2B (R12, Fase 5): faz o que a IA de um revendedor…, Um POST `initialize` cru e devolve só o status HTTP — para conferir o `401` sem…, Sessão MCP completa com a chave: `initialize`, `tools/list` (as 4 ferramentas)…, ResultadoMcp, status_sem_sessao() (+3 more)

### Community 49 - "characteristics.py"
Cohesion: 0.13
Nodes (27): get_characteristics(), AsyncSession, get, ModelCharacteristics, post, refresh_characteristics(), _to_response(), ModelCharacteristics (+19 more)

### Community 50 - "orders.ts"
Cohesion: 0.09
Nodes (33): PedidosPageContent(), ProdutoDetalhePage(), ProdutoPageProps, ProdutosPage(), ImageZoomModal(), ImageZoomModalProps, ProductCard(), ProductCardProps (+25 more)

### Community 51 - "api/rag.ts"
Cohesion: 0.12
Nodes (20): AbaEnviarDocumento(), handleCriarCollectionRapida(), handleSelectCollectionChange(), handleSubmit(), CollectionFormModal(), handleSubmit(), resetar(), CollectionsTable() (+12 more)

### Community 52 - ".describe_image"
Cohesion: 0.12
Nodes (8): LocalVisionResult, Any, str, Subclasse de str que preserva o texto retornado por…, Carrega o modelo na memória/VRAM com o keep_alive configurado (elimina cold-…, Envia uma imagem + prompt ao modelo local (Ollama) e devolve o texto cru —…, Mesmo `/api/generate`, mas com `stream: true` — devolve um `LLMStreamChunk` por…, Detalhes completos de um modelo já baixado (`POST /api/show`) — usado pelo…

### Community 53 - "api/local_models.py"
Cohesion: 0.20
Nodes (16): get_ollama_client(), get_pull_progress_store(), list_local_models_endpoint(), pull_status_endpoint(), get, Request, Endpoints HTTP do gerenciador de modelos locais (Ollama, além do MVP) — listar,…, ActivateModelRequest (+8 more)

### Community 54 - "adminPedidos.ts"
Cohesion: 0.20
Nodes (18): AdminPedidosPage(), ModalConversaoPedido(), handleAuditarIA(), handleConfirmarComIA(), handleConverterAuto(), handleConverterSimples(), ModalConversaoPedidoProps, analisarComprovante() (+10 more)

### Community 55 - "ClipImageStore"
Cohesion: 0.11
Nodes (14): ClipImageStore, ImageSearchResult, AsyncQdrantClient, BaseModel, Embeda e grava uma imagem. Retorna o `image_id` gerado., Exclui um ponto por ID da collection CLIP., Exclui todos os pontos da collection CLIP pertencentes ao produto_id., Exclui pontos da collection CLIP por imagem_url. (+6 more)

### Community 56 - "getApiBaseUrl"
Cohesion: 0.13
Nodes (41): AdminProdutosPage(), CATEGORIAS_PADRAO, ProductFormModal(), ProductFormModalProps, ProductListTable(), ProductListTableProps, StockDetailBadgeProps, addAdminProductCompatibility() (+33 more)

### Community 57 - "google_calendar.py"
Cohesion: 0.20
Nodes (10): Cliente MCP do Google Calendar (R11, Fase 4A) — consome um servidor MCP de…, _probe_status_http(), Cliente assíncrono para o Servidor MCP B2B Corporativo., POST `initialize` cru (sem sessão MCP) só para ler o status HTTP — mesma…, contextlib, httpx2, mcp, mcp_client_session (+2 more)

### Community 58 - "types/rag.ts"
Cohesion: 0.09
Nodes (27): CollectionFormModalProps, CURATED_MODELS, PAYLOAD_INDEXES_PADRAO, SCHEMA_TYPES, TEXT_PARAMS_PADRAO, subscribeNoop(), Tooltip(), TooltipAlign (+19 more)

### Community 59 - "compilerOptions"
Cohesion: 0.07
Nodes (28): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+20 more)

### Community 60 - "Base"
Cohesion: 0.16
Nodes (16): deletar_produto(), Remove o produto e os registros filhos (estoque/descontos/…, Base, PedidoItem, ProdutoCompatibilidade, ProdutoDescontoVolume, ProdutoEstoque, ProdutoImagem (+8 more)

### Community 61 - "devDependencies"
Cohesion: 0.11
Nodes (19): eslint, eslint-config-prettier, devDependencies, eslint, eslint-config-prettier, prettier, @tailwindcss/postcss, @testing-library/jest-dom (+11 more)

### Community 62 - "api/image_search.py"
Cohesion: 0.19
Nodes (18): _get_clip_embedder(), _get_clip_store(), _get_rag_client(), _get_vision_client(), identify_image(), ingest_image(), post, Request (+10 more)

### Community 63 - "api/agendamentos.ts"
Cohesion: 0.29
Nodes (13): AdminAgendamentosPage(), formatarDataHora(), AgendamentosPage(), formatarDataHora(), cancelarAgendamento(), criarAgendamentoManual(), fetchAdminAgendamentos(), fetchGoogleCalendarEvents() (+5 more)

### Community 64 - "GoogleCalendarMCPClient"
Cohesion: 0.29
Nodes (4): GoogleCalendarMCPClient, is_system_event(), Any, Verifica se o evento do Google Calendar pertence ao sistema. Identifica pela…

### Community 65 - "app.py"
Cohesion: 0.16
Nodes (17): calcular_resumo_cotacao(), calcular_total_pedido(), formatar_itens_carrinho(), formatar_itens_pedido(), formatar_moeda(), main(), Aplicação Streamlit do Cliente Independente MCP B2B., Formata valor numérico para o padrão de moeda brasileiro R$ X.XXX,XX. (+9 more)

### Community 66 - "DocumentsTable.tsx"
Cohesion: 0.12
Nodes (24): DocumentsTableProps, DOMAIN_OPTIONS, detectarTipoArquivo(), DocumentViewModal(), DocumentViewModalProps, FileType, parseCSV(), parseLinhaCSV() (+16 more)

### Community 67 - "whisper_client.py"
Cohesion: 0.16
Nodes (10): Exception, Wrapper de STT (R5) via faster-whisper, rodando na mesma GPU do modelo local.…, Falha de infraestrutura ao carregar o modelo ou transcrever o áudio. Análogo a…, Cliente STT local via faster-whisper. Suporta qualquer formato de áudio que o…, Transcreve `audio_bytes` (ex.: wav, mp3) para texto em português. # MVP: sem…, SttIndisponivelError, WhisperSttClient, faster_whisper (+2 more)

### Community 68 - "api/runtime_settings.py"
Cohesion: 0.22
Nodes (18): _build_response(), _get_clients(), get_runtime_settings(), preload_local_model(), get, post, put, Request (+10 more)

### Community 69 - "RagDocument Model (PostgreSQL)"
Cohesion: 0.23
Nodes (12): Qdrant Point Deletion by Document ID, RagDocument Model (PostgreSQL), Design — Registro e Exclusão de Documentos Ingeridos no RAG, EmbedderRegistry Cache, RagCollection Profile (Immutable Config), RAG Comparative Search Playground, Design — Perfis de Collection Configuráveis + Playground de Busca, Collection Purpose Isolation (Chat vs MCP B2B) (+4 more)

### Community 70 - "Refactoring with GitNexus"
Cohesion: 0.17
Nodes (11): Bind the repository first, Checklists, Example: Rename `validateUser` to `authenticateUser`, Extract Module, Refactoring with GitNexus, Rename Symbol, Risk Rules, Split Function/Service (+3 more)

### Community 71 - "Injeção de Dados Estruturados de Catálogo no Prompt"
Cohesion: 0.20
Nodes (11): Injeção de Dados Estruturados de Catálogo no Prompt, Plano de Implementação: Orquestrador MCP B2B em Vendas, Resolução de Produtos em Duas Etapas (SQL + LLM), Pipeline de Extração Multimodal de Catálogo, Plano de Implementação: Gestão de Produtos e Catálogos Multimodais, RAG Visual com Qdrant CLIP, Exposição de Tráfego JSON-RPC para Auditoria, Cliente MCP Streamlit Isolado (+3 more)

### Community 72 - "scripts"
Cohesion: 0.13
Nodes (14): name, private, scripts, build, dev, format, format:check, lint (+6 more)

### Community 73 - "Manual Didático: Repowise no Ambiente de Desenvolvimento Agêntico (WSL2, Antigravity IDE, Claude CLI, Kiro CLI)"
Cohesion: 0.08
Nodes (23): 📌 1. Sumário de Recursos, Portas e Convivência no Ecossistema, 2.1 Repowise vs. Graphify: Como se Complementam?, 2.2 Repowise + Headroom: Economia de Tokens em Camadas, 2.3 Repowise + Provedores Locais (Strata e Ollama), 🔄 2. Convivência e Uso Simultâneo com Outras Ferramentas, 3.1 Inicialização Passo a Passo, 3.2 Validação da Integridade do Setup, 🚀 3. Inicialização e Configuração Segura no Repositório (+15 more)

### Community 74 - "GitNexus CLI Commands"
Cohesion: 0.18
Nodes (10): After Indexing, analyze — Build or refresh the index, clean — Delete the index, Commands, GitNexus CLI Commands, Index storage and retention, list — Show all indexed repos, status — Check index freshness (+2 more)

### Community 75 - "Especificação Arquitetural: Ledger Unificado de Uso de IA"
Cohesion: 0.20
Nodes (10): Painel de Métricas e Ledger Unificado de Uso de IA, Plano do Ledger de Uso de IA: Item A - Fundação, Plano do Ledger de Uso de IA: Item B - Origem Chat, Plano do Ledger de Uso de IA: Item D - Origem Admin, Plano do Ledger de Uso de IA: Item E - Painel, Especificação Arquitetural: Ledger Item B - Origem Chat, Especificação Arquitetural: Ledger Item D - Origem Admin, Semântica de Null (Não Medido) vs Zero (Grátis) (+2 more)

### Community 76 - "GitNexus Guide"
Cohesion: 0.18
Nodes (10): Always Start Here, Control & data dependence (`pdg_query`), GitNexus Guide, Graph Schema, Paginating `list_repos`, Resources Reference, Shortest path between two symbols (`trace`), Skills (+2 more)

### Community 77 - "Aplicação Cliente Independente MCP B2B"
Cohesion: 0.28
Nodes (9): Aplicação Cliente Independente MCP B2B, Padrão de Cliente B2B Desacoplado, Dependências PIP do Cliente MCP B2B, Requisito R11: Agendamento via Cliente MCP, Requisito R12: Provedor MCP B2B Corporativo, Proxy Reverso Caddy HTTPS (Porta 8443), Serviço calendar-mcp-server (Porta 8090), Serviço mcp-b2b-server (Porta 8100) (+1 more)

### Community 78 - "Manual do Administrador do Sistema"
Cohesion: 0.22
Nodes (9): Catálogo B2B e Ferramentas MCP, Dashboards e Gráficos Dinâmicos via Chat, Gestão da Base de Conhecimento e Ingestão RAG, Gestão de Usuários e Permissões, Manual do Administrador do Sistema, Parametrização do Web Crawler, Prompt Text-to-SQL de Gráficos Analíticos (analytics_agent.py), Prompts de Extração de Catálogo Textual e Visual (extractor.py) (+1 more)

### Community 79 - "Manual do Usuário e Cliente"
Cohesion: 0.22
Nodes (9): Monitor de Tom e Gestão de Sessões, Widget do Assistente Virtual Multimodal, Cards Ricos e Interativos no Chat, Manual do Usuário e Cliente, Interação Multimodal por Texto, Áudio e Foto, Transbordo para Suporte Especializado, Montagem Dinâmica e Sanitização de Prompt (orchestrator.py), Prompt do Monitor de Tom Emocional (tone_monitor.py) (+1 more)

### Community 80 - "Mapeamento de Prompts e Instruções LLM"
Cohesion: 0.22
Nodes (9): Mapeamento de Prompts e Instruções LLM, Critérios e Prompt do Classificador de Intenção (classifier.py), Prompts de Auditoria de Comprovantes Financeiros (comprovante_evaluator.py), Prompt de Visão para Identificação de Produtos (image_identification.py), Prompt LLM-as-Judge de Qualidade RAG (eval/rag_quality/run_eval.py), Prompt de Consolidação de Resumo (resumo.py), Prompt de Extração de Intenções de Vendas (sales_catalog.py), Prompt de Extração de Agendamento (scheduling.py) (+1 more)

### Community 81 - "Manual do Strata"
Cohesion: 0.29
Nodes (8): Otimização de Janela de Contexto Headroom, Modos de Operação do Proxy Headroom, Manual do Headroom, Gerenciamento e Parametrização da IA em Runtime, Manual do Strata, Motor de Inferência CUDA Strata MoE, Gerenciamento de Ciclo de Vida de Memória (Lazy / Idle Unload), Modelo Swift 1.5 MoE Quantizado

### Community 82 - "Protocolo Unificado de Streaming SSE no Chat"
Cohesion: 0.25
Nodes (8): Plano de Implementação: Streaming SSE da Resposta do Chat, Isolamento de Streaming: RAG Síncrono e Geração Reativa, Protocolo Unificado de Streaming SSE no Chat, Monitor de Tom e Sentimento em Paralelo, Escalonamento Imediato via SSE e Banco, Plano de Implementação: Monitor de Tom, Download Seguro de Arquivos RAG via Chat, Plano de Implementação: Download Direto de Documentos RAG

### Community 83 - "Runtime In-Memory Model Switching"
Cohesion: 0.29
Nodes (8): Background Model Pull with Polling, Runtime In-Memory Model Switching, Design — Gerenciador de Modelos Locais (Ollama), Ollama Model Cold-Start Detection, Streaming (SSE) da Resposta do Chat — Design, ModelCharacteristics Persistent Cache, Input/Output Modality Mapping per Source, Design — Características de Modelo (Multimodalidade) no Hover

### Community 84 - "dependencies"
Cohesion: 0.13
Nodes (15): dependencies, next, @radix-ui/react-dialog, @radix-ui/react-tabs, react, react-dom, recharts, zustand (+7 more)

### Community 85 - "chunk_size_search.py"
Cohesion: 0.26
Nodes (13): _apagar_collection(), _avaliar_chunk_size(), _criar_e_popular_collection(), main(), Path, Busca por bisseção do `chunk_size` que maximiza a qualidade do RAG (R4, Fase…, _carregar_casos(), _fonte_e_correta() (+5 more)

### Community 86 - "api/crawler.py"
Cohesion: 0.08
Nodes (46): ApprovedPageResponse, approve_pending(), get_pending(), AsyncSession, get, Path, post, Request (+38 more)

### Community 87 - "pdf_extract.py"
Cohesion: 0.21
Nodes (12): _detectar_gap_coluna(), extract_text_from_pdf(), _extrair_texto_pagina(), PdfExtractionError, Exception, Path, Extração de texto de PDF para ingestão no RAG (R4). # MVP: extração via…, Levantado quando o PDF não pode ser aberto ou processado. (+4 more)

### Community 89 - "_build_prompt"
Cohesion: 0.24
Nodes (9): _build_prompt(), Domain, Monta o prompt final: prompt de sistema do domínio (playbook) + dados do…, build_system_prompt(), get_playbook(), Domain, Playbooks e prompts de sistema por domínio de atendimento (R7, Fase 3). Cada…, Retorna o bloco de instruções de sistema do domínio, ou None. Retorna o… (+1 more)

### Community 90 - "Amarração Dual Postgres e Qdrant por Document ID"
Cohesion: 0.29
Nodes (7): Exclusão Definitiva de Vetores e Metadados sem Soft Delete, Plano de Implementação: Registro e Exclusão de Documentos RAG, Amarração Dual Postgres e Qdrant por Document ID, Adapter de Coleção Ativa em Runtime, Perfis Imutáveis de Coleções Vetoriais, Plano de Implementação: Perfis de Collection Configuráveis e Playground, Playground Comparativo de Busca RAG

### Community 91 - "Transbordo Human-in-the-Loop com Lock Atômico"
Cohesion: 0.33
Nodes (7): Crawler BFS de Páginas Web, Fila de Revisão Humana de Páginas por Confiança, Plano de Implementação: Crawler de Páginas para RAG, Ciclo de Vida de Sessões e Encerramento por Inatividade, Plano de Implementação: Contabilizador de Tokens e Custos, Plano de Implementação: Atendimento Humano e Transbordo Dinâmico, Transbordo Human-in-the-Loop com Lock Atômico

### Community 92 - "Contabilização Segregada de Tokens e Custos de LLM"
Cohesion: 0.29
Nodes (7): Contabilização Segregada de Tokens e Custos de LLM, Contabilização Financeira de Visão Computacional, Plano de Implementação: Custos de Visão Externa, Dashboards Dinâmicos Persistentes com Recharts, Plano de Implementação: Dashboards Dinâmicos Admin, Agente Analítico com Text-to-SQL Seguro, Plano de Implementação: Agente Analítico de Gráficos Dinâmicos com LLM

### Community 93 - "Transversal Tone Monitoring Architecture"
Cohesion: 0.33
Nodes (7): Single POST text/event-stream Transport, Design — Monitor de Tom (R8), Tom Escalonamentos Model & Persistence, Transversal Tone Monitoring Architecture, CLIP Visual Catalog in Qdrant, Hybrid PDF/Image Catalog Extraction with SSE, Design — Gestão de Produtos no Admin, Ingestão de Catálogos e RAG Visual CLIP

### Community 94 - "Crawler Human Review Queue for Uncertain Confidence"
Cohesion: 0.29
Nodes (7): Same-Host BFS Web Crawler, Crawler Human Review Queue for Uncertain Confidence, Crawler de Páginas para o RAG — Design, Crawler URL Deduplication and Replacement, AI Generation Pausing on Human Takeover, Atomic Conversation Claim with Concurrency Lock, Especificação: Transbordo para Atendimento Humano e Fila de Suporte

### Community 95 - "Google Calendar MCP Client"
Cohesion: 0.48
Nodes (7): Booking Slots State Machine & Extraction, Google Calendar MCP Client, Business Hours & Schedule Conflict Validation, Design — Agendamento via MCP Calendar (R11), Agendamento Model & PostgreSQL Synchronization, Graceful Appointment Cancellation Flow, Design — Gestão de Agendamentos (Fase 7)

### Community 96 - "Multimodal Receipt Evaluation Pipeline"
Cohesion: 0.33
Nodes (7): Five Conversion Modalities Architecture, Multimodal Receipt Evaluation Pipeline, Especificação: Conversão de Reserva em Venda com Comprovação Multimodal, High-Confidence Injection Attempt Logging, Sandwich System Prompt Defense, Especificação: Resiliência a Prompt Injection e Abuso MCP, Untrusted Delimiter Tag Wrapping (wrap_untrusted)

### Community 97 - "AudioRecorder"
Cohesion: 0.43
Nodes (6): AudioRecorder(), handleClick(), startRecording(), stopRecording(), AudioRecorderProps, blobToBase64()

### Community 98 - "Bateria de Perguntas de Ground Truth RAG"
Cohesion: 0.33
Nodes (6): Bateria de Perguntas de Ground Truth RAG, Parâmetros Ópticos da Tabela DORI, Tecnologia de Busca por IA InSearch, Benchmark de Qualidade do RAG, Avaliação via LLM-as-Judge, Avaliação 2: Qualidade do RAG

### Community 99 - "Plano de Implementação de Segurança Contra Prompt Injection e Abuso MCP"
Cohesion: 0.33
Nodes (6): Prompt LLM-as-Judge de Resiliência a Injeção (eval/prompt_injection/run_eval.py), Prompts de Sistema e Playbooks por Domínio (playbooks.py), Avaliação Experimental de Resiliência a Injeções, Plano de Implementação de Segurança Contra Prompt Injection e Abuso MCP, Técnica de Sandwich Prompting Anti-Injeção, Validação Robusta de Schemas de Entrada MCP B2B

### Community 100 - "Máquina de Estados de Agendamento por Slots"
Cohesion: 0.40
Nodes (6): Máquina de Estados de Agendamento por Slots, Cliente MCP Google Calendar Streamable HTTP, Plano de Implementação: Agendamento via MCP Calendar, Degradação Graciosa em Instabilidade do Barramento MCP, Plano de Implementação: Gestão Completa de Agendamentos, Sincronização Híbrida de Agendamentos Postgres e Google Calendar

### Community 101 - "SalesCatalogClient (Direct Database Access)"
Cohesion: 0.47
Nodes (6): SalesCatalogClient (Direct Database Access), Design — Orquestrador como Integrador do MCP B2B em Vendas, Two-Stage Product Resolution (SQL + LLM), B2BMCPClient Python SDK, Streamlit Partner Portal Application, Design — Cliente Independente MCP B2B com Interface Web

### Community 102 - "Segregated Prompt & Completion Cost Calculation"
Cohesion: 0.40
Nodes (6): Chat Inactivity 30-Minute Auto-Closure Worker, Segregated Prompt & Completion Cost Calculation, Design — Contabilizador de Tokens, Custos Segregados e Chats Encerrados, AdminChart PostgreSQL Model, Natural Language Chat Chart Synthesis, Design — Dashboards e Gráficos Dinâmicos Gerados via Chat

### Community 103 - "main.py"
Cohesion: 0.08
Nodes (45): Endpoints REST administrativos para a Central de Atendimento Humano e Fila de…, is_admin_request(), alias, AsyncSession, Header, Query, Dependência FastAPI compartilhada para restringir endpoints a administradores…, Extrai o token admin de `Authorization`/`X-Auth-Token`/`?token=` (nessa… (+37 more)

### Community 104 - "g.sh"
Cohesion: 0.60
Nodes (5): checar_servico(), falha(), main(), passo(), g.sh script

### Community 105 - "Gerenciador Assíncrono de Modelos Ollama"
Cohesion: 0.40
Nodes (5): Gerenciador Assíncrono de Modelos Ollama, Plano de Implementação: Gerenciador de Modelos Locais, Troca de Modelo em Runtime sem Persistência, Cache de Características e Multimodalidade de Modelos, Plano de Implementação: Características de Modelo no Hover

### Community 106 - "Serviço registrar_uso_ia e Gerenciamento de Sessão Global"
Cohesion: 0.40
Nodes (5): Serviço registrar_uso_ia e Gerenciamento de Sessão Global, Conexão dos 10 Pontos de IA da Origem Chat, Instrumentação de Gráficos e Extração no Ledger, Mapeamento das Famílias de IA do Chat, Padrão de Sessão Assíncrona e Fallback Global

### Community 108 - ".prettierrc.json"
Cohesion: 0.40
Nodes (4): printWidth, semi, singleQuote, trailingComma

### Community 110 - "LocalModel"
Cohesion: 0.50
Nodes (3): LocalModel, Modelos já baixados localmente (`GET /api/tags`)., Um modelo já baixado localmente no Ollama (`GET /api/tags`).

### Community 111 - "api/chat.ts"
Cohesion: 0.19
Nodes (13): MessageBubbleProps, API_BASE_URL, ConversationSnapshot, fetchConversationHistory(), mapHistoricoMensagens(), SendChatMessageParams, ChatState, ChatDoneEventData (+5 more)

### Community 113 - "Ambiente Antigravity IDE"
Cohesion: 0.50
Nodes (4): Ambiente Antigravity IDE, Mecanismo de Artifacts de Revisão, Claude Code CLI, Kiro CLI

### Community 114 - "Widget de Chat Multimodal"
Cohesion: 0.50
Nodes (4): Requisito R2: Entrada Multimodal de Chat, Widget de Chat Multimodal, Componentes de Cards Ricos no Chat, Streaming Server-Sent Events (SSE)

### Community 115 - "Orquestrador Híbrido de LLM"
Cohesion: 0.67
Nodes (4): Classificador de Intenção e Complexidade, Princípio de Falha Dura em Infraestrutura (Sem Fallback Silencioso), Orquestrador Híbrido de LLM, Plano de Implementação: Roteador Básico

### Community 116 - "Router Orchestration Flow"
Cohesion: 0.83
Nodes (4): Intent Classifier (Domain & Complexity), LLMClient Protocol, Router Orchestration Flow, Design — Fase 1: Modelo Local e Roteador Básico

### Community 117 - "Benchmark de Acurácia do Roteador de Intenções"
Cohesion: 0.67
Nodes (3): Benchmark de Acurácia do Roteador de Intenções, Matriz de Confusão 4x4 do Roteador, Avaliação 1: Acurácia do Roteador

### Community 118 - "extractor.py"
Cohesion: 0.18
Nodes (17): _blocos_de_texto(), extract_catalog_stream(), extract_page_products_local(), extract_page_products_vision(), _extrair_figuras_pagina(), _parse_page_range(), _parse_products_json(), Any (+9 more)

### Community 122 - "Regras de Escopo do MVP"
Cohesion: 0.67
Nodes (3): Regras de Escopo do MVP, Exclusões Formais de Escopo do MVP, Padrão de Comentários de Escopo # MVP

### Community 123 - "Endpoint GET /api/admin/metrics/ai-usage"
Cohesion: 0.67
Nodes (3): Endpoint GET /api/admin/metrics/ai-usage, Reconstrução do Painel /admin/metricas no Frontend, Serviço de Roll-up Puro ai_usage_report

### Community 161 - "Impact Analysis with GitNexus"
Cohesion: 0.20
Nodes (9): Bind the repository first, Checklist, Example: "What breaks if I change validateUser?", Impact Analysis with GitNexus, Risk Assessment, Tools, Understanding Output, When to Use (+1 more)

### Community 162 - "get_escalonamentos"
Cohesion: 0.40
Nodes (5): get_escalonamentos(), AsyncSession, get, listar_escalonamentos(), AsyncSession

### Community 163 - "SearchableSelect.tsx"
Cohesion: 0.40
Nodes (3): SearchableSelect(), SearchableSelectOption, SearchableSelectProps

### Community 164 - "api/auth.py"
Cohesion: 0.09
Nodes (46): get_current_user_endpoint(), list_users_endpoint(), login_endpoint(), obter_perfil_cliente(), AsyncSession, get, post, Endpoints REST para autenticação simples e mockada de usuários (R10, Fase 7). #… (+38 more)

### Community 165 - "catalog_extractor.py"
Cohesion: 0.23
Nodes (11): CatalogConfirmItem, CatalogConfirmRequest, CatalogConfirmResponse, CatalogPageResult, ExtractedProduct, BaseModel, Resultado processado de uma única página ou imagem., Item a ser persistido na confirmação. (+3 more)

### Community 166 - "Debugging with GitNexus"
Cohesion: 0.22
Nodes (8): Bind the repository first, Checklist, Debugging Patterns, Debugging with GitNexus, Example: "Payment endpoint returns 500 intermittently", Tools, When to Use, Workflow

### Community 167 - "Exploring Codebases with GitNexus"
Cohesion: 0.22
Nodes (8): Bind the repository first, Checklist, Example: "How does payment processing work?", Exploring Codebases with GitNexus, Resources, Tools, When to Use, Workflow

### Community 168 - "get_public_produtos"
Cohesion: 0.24
Nodes (10): get_public_categorias(), get_public_produto(), get_public_produtos(), _ordenar_estoque_nome_key(), AsyncSession, description, ge, get (+2 more)

### Community 169 - "CatalogImportModal.tsx"
Cohesion: 0.22
Nodes (12): arquivoAceito(), CatalogImportModal(), CatalogImportModalProps, CatalogPriceInput(), CatalogPriceInputProps, chaveArquivo(), formatarMoedaInput(), ModalStep (+4 more)

### Community 170 - "atualizar_resumo"
Cohesion: 0.50
Nodes (4): atualizar_resumo(), async_sessionmaker, AsyncSession, Reescreve o resumo com as mensagens ainda não resumidas. Nunca levanta: roda em…

### Community 171 - "GitNexus — Code Intelligence"
Cohesion: 0.33
Nodes (5): Always Do, CLI, GitNexus — Code Intelligence, Never Do, Resources

### Community 172 - "CalendarClient"
Cohesion: 0.38
Nodes (3): CalendarClient, datetime, Protocol

### Community 173 - "VisionResult"
Cohesion: 0.50
Nodes (3): str, Subclasse de str que preserva o texto retornado e carrega telemetria de tokens…, VisionResult

### Community 174 - "useEstaNoCliente"
Cohesion: 0.23
Nodes (9): CollectionOptionCard(), CollectionOptionCardProps, DOMAIN_OPTIONS, PlaygroundFormProps, PURPOSE_OPTIONS, StockDetailBadge(), subscribeNoop(), useEstaNoCliente() (+1 more)

### Community 175 - "image_processor.py"
Cohesion: 0.23
Nodes (11): extract_text_from_base64(), extract_text_from_bytes(), ImageFormatError, OcrIndisponivelError, ValueError, OCR para imagens dirigidas (R6) — extrai texto de PNG/JPG via pytesseract. #…, Formato de imagem não suportado ou dados corrompidos., pytesseract/Tesseract não está instalado ou não pode ser executado. (+3 more)

### Community 176 - "layout.tsx"
Cohesion: 0.29
Nodes (5): frontend_app_globals, geistMono, geistSans, metadata, Footer()

### Community 177 - "._perguntar_systemone_jev"
Cohesion: 0.38
Nodes (4): Any, Faz uma pergunta tipada via TypeSafe Jev, endpoint dedicado do OpenRouter…, Classifica o domínio via TypeSafe Jev — ver `_perguntar_systemone_jev`., Avalia urgência/insatisfação via TypeSafe Jev (R8, Fase 4B) — mesmo endpoint…

### Community 178 - "db_connector.py"
Cohesion: 0.33
Nodes (6): AsyncConnection, Conector de leitura a um banco de dados relacional para o RAG (R4). # MVP:…, Transforma uma linha (dict coluna -> valor) em texto plano, pronto para…, Lê todas as linhas de `table_name` e devolve uma lista de textos (um por linha,…, read_table_as_text(), row_to_text()

### Community 179 - "pull_model_endpoint"
Cohesion: 0.40
Nodes (5): activate_model_endpoint(), _consumir_pull(), pull_model_endpoint(), post, Roda em background (`asyncio.create_task`) — nunca é aguardada pela requisição…

### Community 180 - "ferramentas/page.tsx"
Cohesion: 0.36
Nodes (6): AdminFerramentasPage(), ICONES, FerramentasResposta, FerramentaStatus, fetchFerramentas(), urlDeVisualizacao()

### Community 181 - "store.py"
Cohesion: 0.11
Nodes (28): Grava a troca antes do `done`: a próxima mensagem sempre encontra esta no…, _registrar_troca_segura(), precisa_resumir(), carregar_contexto(), contar_mensagens(), ContextoConversa, gravar_aviso_assistente(), gravar_mensagem_cliente() (+20 more)

### Community 182 - "run_mcp_b2b_server.py"
Cohesion: 0.16
Nodes (8): do_run_migrations(), run_migrations_online(), Sobe o servidor MCP B2B (R12, Fase 5) como processo próprio, escutando em…, ConversationIdFilter, JsonFormatter, Formatter JSON com merge de campos estruturados do roteador. Campos extras…, contextvars, LogRecord

### Community 183 - ".pull_model_streaming"
Cohesion: 0.50
Nodes (3): PullProgressLine, Baixa `name` (biblioteca do Ollama ou `hf.co/usuario/repo[:tag]` do Hugging…, Uma linha do stream NDJSON de `POST /api/pull` — ver…

### Community 184 - "require_admin"
Cohesion: 0.40
Nodes (5): alias, AsyncSession, Header, Query, require_admin()

### Community 185 - "chat_closure_service.py"
Cohesion: 0.32
Nodes (7): fechar_conversas_inativas(), inactivity_closure_worker(), async_sessionmaker, AsyncSession, Serviço de encerramento de conversas (manual e automático por inatividade)., Encerra conversas com status='aberta' cuja última atualização foi há mais de…, Worker em background executado periodicamente para fechar conversas inativas.

### Community 186 - "settings.py"
Cohesion: 0.42
Nodes (9): AppSetting, Parâmetros de configuração e execução persistidos no banco., get_all_app_settings(), get_app_setting(), Any, AsyncSession, Persistência de configurações de execução no PostgreSQL., save_multiple_app_settings() (+1 more)

### Community 187 - "get_model_catalog_http_client"
Cohesion: 0.50
Nodes (4): get_model_catalog_http_client(), get_ollama_client(), AsyncClient, Request

### Community 188 - "parceiro_atual"
Cohesion: 0.33
Nodes (6): parceiro_atual(), Nome do parceiro autenticado na requisição em andamento, ou `"sem-…, Uma linha de log `mcp_b2b_ferramenta` por chamada: parceiro que chamou (da…, _registrar_chamada(), P, R

### Community 189 - "EstoqueInsuficienteError"
Cohesion: 0.40
Nodes (5): EstoqueInsuficienteError, ProdutoInexistenteError, Exception, Levantada por `criar_pedido` quando algum item da reserva pede mais quantidade…, Levantada por `criar_pedido` quando um `produto_id` referenciado num item não…

### Community 190 - "admin_products.py"
Cohesion: 0.12
Nodes (27): _get_clip_embedder(), _get_clip_store(), post_admin_produto(), post_extrair_catalogo_stream(), put_admin_produto(), post, put, Request (+19 more)

### Community 191 - "detect_chart_request"
Cohesion: 0.50
Nodes (3): detect_chart_request(), Gate de intenção para o Agente Analítico de Gráficos Dinâmicos…, Identifica se o prompt do usuário expressa a intenção explícita de gerar ou…

## Knowledge Gaps
- **368 isolated node(s):** `assistente-multimodal-backend`, `cliente-mcp-b2b`, `semi`, `singleQuote`, `trailingComma` (+363 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **30 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `QdrantRAGClient` connect `QdrantRAGClient` to `EmbedderRegistry`, `api/runtime_settings.py`, `b2b.py`, `main.py`, `TextEmbedder`, `models/rag.py`, `rag_collections.py`, `chunk_size_search.py`, `api/crawler.py`, `models.py`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **Why does `useAuthStore` connect `useAuthStore` to `useChatStore.ts`, `metricas/page.tsx`, `OpenRouterModelCard.tsx`, `ChatModal.tsx`, `PullModelForm.tsx`, `PlaygroundPanel.tsx`, `ingestao/page.tsx`, `api/crawler.ts`, `LocalModelsTable.tsx`, `adminAtendimento.ts`, `CatalogImportModal.tsx`, `dashboards/page.tsx`, `orders.ts`, `api/rag.ts`, `ferramentas/page.tsx`, `adminPedidos.ts`, `getApiBaseUrl`, `types/rag.ts`, `api/agendamentos.ts`, `DocumentsTable.tsx`?**
  _High betweenness centrality (0.014) - this node is a cross-community bridge._
- **Why does `OllamaClient` connect `OllamaClient` to `EmbedderRegistry`, `api/runtime_settings.py`, `main.py`, `LocalModel`, `collections_abc`, `characteristics.py`, `pull_model_endpoint`, `.describe_image`, `api/local_models.py`, `chunk_size_search.py`, `.pull_model_streaming`, `get_model_catalog_http_client`?**
  _High betweenness centrality (0.011) - this node is a cross-community bridge._
- **Are the 29 inferred relationships involving `QdrantRAGClient` (e.g. with `_FixedCollectionRagClient` and `main()`) actually correct?**
  _`QdrantRAGClient` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `OllamaClient` (e.g. with `main()` and `main()`) actually correct?**
  _`OllamaClient` has 17 INFERRED edges - model-reasoned connections that need verification._
- **What connects `assistente-multimodal-backend`, `cliente-mcp-b2b`, `semi` to the rest of the system?**
  _368 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `EmbedderRegistry` be split into smaller, more focused modules?**
  _Cohesion score 0.11724137931034483 - nodes in this community are weakly interconnected._