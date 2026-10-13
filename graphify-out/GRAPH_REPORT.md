# Graph Report - TCC  (2026-10-12)

## Corpus Check
- 353 files · ~430,244 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2811 nodes · 6755 edges · 200 communities (166 shown, 34 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 470 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `25e85920`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- ClipEmbedder
- comprovante_evaluator.py
- scheduling.py
- registrar_uso_ia
- b2b.py
- api/chat.py
- admin_products.py
- main.py
- ingest.py
- api/runtime_settings.py
- QdrantRAGClient
- CollectionsTable.tsx
- 0002_rag_collections.py
- mcp_server/auth.py
- api/auth.py
- typing
- useAuthStore
- approve_pending
- db/catalog.py
- ai_usage_report.py
- metricas/page.tsx
- Guia Claude Code CLI
- RuntimeSettingsForm.tsx
- upload_document
- types/chat.ts
- ChatModal.tsx
- OpenRouterModelCard.tsx
- sales_catalog.py
- rag_collections.py
- post_converter_auto_admin
- OllamaClient
- Conversa
- ingestao/page.tsx
- agendamentos.py
- AdminChart
- api/crawler.ts
- LocalModelsTable.tsx
- api/orders.py
- B2BMCPClient
- adminAtendimento.ts
- OpenRouterClient
- classifier.py
- extractor.py
- admin_atendimento.py
- models/rag.py
- dashboards/page.tsx
- getApiBaseUrl
- cliente_mcp_b2b.py
- api/model_catalog.py
- app/pedidos/page.tsx
- types/rag.ts
- pdf_extract.py
- api/local_models.py
- adminPedidos.ts
- ImageUploader.tsx
- orders.ts
- models.py
- CategoryFilter.tsx
- compilerOptions
- orchestrator.py
- devDependencies
- models/catalog.py
- api/agendamentos.ts
- CalendarClient
- app.py
- ConversaMensagem
- whisper_client.py
- CatalogImportModal.tsx
- RagDocument Model (PostgreSQL)
- layout.tsx
- Injeção de Dados Estruturados de Catálogo no Prompt
- scripts
- Manual Didático: Repowise no Ambiente de Desenvolvimento Agêntico (WSL2, Antigravity IDE, Claude CLI, Kiro CLI)
- inactivity_closure_worker
- Especificação Arquitetural: Ledger Unificado de Uso de IA
- criar_escalonamento
- Aplicação Cliente Independente MCP B2B
- Manual do Administrador do Sistema
- Manual do Usuário e Cliente
- Mapeamento de Prompts e Instruções LLM
- Manual do Strata
- Protocolo Unificado de Streaming SSE no Chat
- Runtime In-Memory Model Switching
- dependencies
- db_connector.py
- api/crawler.py
- ChatChartCard.tsx
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
- SearchableSelect.tsx
- g.sh
- Gerenciador Assíncrono de Modelos Ollama
- Serviço registrar_uso_ia e Gerenciamento de Sessão Global
- eslint.config.mjs
- .prettierrc.json
- rules/graphify.md
- LocalModel
- LocalVisionResult
- workflows/graphify.md
- Ambiente Antigravity IDE
- Widget de Chat Multimodal
- Orquestrador Híbrido de LLM
- Router Orchestration Flow
- Benchmark de Acurácia do Roteador de Intenções
- eslint-config-prettier
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
- RAGConnectionError
- chunk_size_search.py
- api/image_search.py
- classificacao.py
- useChatStore.ts
- image_processor.py
- uploads.py
- ImageSearchResult
- settings.py
- catalog_extractor.py
- apiBaseUrl.ts
- alembic
- collections_abc
- identify_product_by_image
- listar_estoque
- ExternalBackendIndisponivelError
- processar_conversao_comprovante
- require_admin
- exportMetrics.ts
- 0012_conversa_metricas.py
- ChatMessageRequest
- .pull_model_streaming
- VisionResult
- detect_chart_request

## God Nodes (most connected - your core abstractions)
1. `getApiBaseUrl()` - 79 edges
2. `useAuthStore` - 76 edges
3. `QdrantRAGClient` - 58 edges
4. `OllamaClient` - 46 edges
5. `handle_message()` - 45 edges
6. `RAGConnectionError` - 45 edges
7. `create_b2b_mcp_server()` - 43 edges
8. `send_message()` - 42 edges
9. `Conversa` - 33 edges
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

## Communities (200 total, 34 thin omitted)

### Community 0 - "ClipEmbedder"
Cohesion: 0.17
Nodes (8): ClipEmbedder, InvalidImageError, Exception, SentenceTransformer, Gera um embedding CLIP por texto (mesmo espaço vetorial das imagens)., Bytes fornecidos não são uma imagem decodificável pelo PIL. Erro de entrada…, Wrapper fino sobre CLIP via sentence-transformers, com carga lazy. Mesmo padrão…, Gera um embedding CLIP por imagem (bytes PNG/JPG/WEBP).

### Community 1 - "comprovante_evaluator.py"
Cohesion: 0.13
Nodes (16): Isolamento por delimitador e detecção log-only de tentativas de prompt…, Envolve `content` nas tags de `label`, escapando qualquer ocorrência literal de…, wrap_untrusted(), ComprovanteEvaluator, ParecerComprovante, _parse_decimal(), Any, Decimal (+8 more)

### Community 2 - "scheduling.py"
Cohesion: 0.11
Nodes (33): GoogleCalendarConnectionError, Exception, Falha de rede/protocolo ao falar com o MCP do Google Calendar, ou a tool…, _handle_agendamento(), datetime, Valida expediente e disponibilidade de agenda para `slots.data_hora`. Devolve o…, _validar_horario_para_agendamento(), BookingSlots (+25 more)

### Community 3 - "registrar_uso_ia"
Cohesion: 0.15
Nodes (17): Substituto de `analyze_tone()` quando `tone_monitor_enabled=False` — devolve um…, _sem_analise_de_tom(), analyze_tone(), _analyze_with_jev(), _analyze_with_llm(), _match_heuristic_signal(), _match_keyword_signal(), _match_structural_signal() (+9 more)

### Community 4 - "b2b.py"
Cohesion: 0.08
Nodes (47): parceiro_atual(), Nome do parceiro autenticado na requisição em andamento, ou `"sem-…, create_b2b_mcp_server(), host_somente_local(), Any, async_sessionmaker, AsyncSession, AuthSettings (+39 more)

### Community 5 - "api/chat.py"
Cohesion: 0.05
Nodes (59): _carregar_contexto_anterior_seguro(), _carregar_conversa_db_segura(), _carregar_dados_cliente_seguro(), deletar_conversa(), fechar_conversa_endpoint(), get_calendar_client(), get_clip_embedder(), get_clip_store() (+51 more)

### Community 6 - "admin_products.py"
Cohesion: 0.09
Nodes (53): CompatibilidadePayload, delete_admin_produto(), delete_compatividade(), delete_desconto_volume(), delete_imagem_produto(), DescontoVolumePayload, EstoqueUpdatePayload, get_admin_categorias() (+45 more)

### Community 7 - "main.py"
Cohesion: 0.07
Nodes (48): argparse, AsyncEngine, main(), _parse_args(), Script de ingestão das linhas de uma tabela do banco relacional no RAG (R4 —…, main(), Script de ingestão de um pequeno conjunto de documentos de exemplo no RAG, na…, main() (+40 more)

### Community 8 - "ingest.py"
Cohesion: 0.10
Nodes (39): RagDocument, Registro de um documento ingerido no RAG (R4, além do MVP). `id` também é…, chunk_text(), _normalizar_preservando_linhas(), Chunking de texto para ingestão no RAG (R4). # MVP: divisão por tamanho fixo de…, Colapsa espaços/tabs repetidos dentro de cada linha (como antes), mas preserva…, Divide `text` em pedaços de até `chunk_size` caracteres, com overlap.…, ingest_or_queue() (+31 more)

### Community 9 - "api/runtime_settings.py"
Cohesion: 0.22
Nodes (18): _build_response(), _get_clients(), get_runtime_settings(), preload_local_model(), get, post, put, Request (+10 more)

### Community 10 - "QdrantRAGClient"
Cohesion: 0.07
Nodes (27): ActiveCollectionRagClient, async_sessionmaker, Adapter que implementa o Protocol `RAGClient` (usado pelo orchestrator)…, AdminAllCollectionsRagClient, async_sessionmaker, Adapter `RAGClient` (mesmo Protocol de `ActiveCollectionRagClient`) usado só…, EmbedderRegistry, SentenceTransformer (+19 more)

### Community 11 - "CollectionsTable.tsx"
Cohesion: 0.12
Nodes (16): AbaEnviarDocumento(), handleCriarCollectionRapida(), handleSelectCollectionChange(), handleSubmit(), CollectionFormModal(), handleSubmit(), resetar(), CollectionsTable() (+8 more)

### Community 13 - "mcp_server/auth.py"
Cohesion: 0.06
Nodes (44): AccessToken, AutenticacaoMcpB2B, carregar_chaves_parceiros(), ChaveParceiroVerifier, ChavesParceirosInvalidasError, configuracao_auth(), _origem(), preparar_autenticacao() (+36 more)

### Community 14 - "api/auth.py"
Cohesion: 0.15
Nodes (27): get_current_user_endpoint(), list_users_endpoint(), login_endpoint(), obter_perfil_cliente(), AsyncSession, get, post, Endpoints REST para autenticação simples e mockada de usuários (R10, Fase 7). #… (+19 more)

### Community 15 - "typing"
Cohesion: 0.06
Nodes (44): asyncio, _avaliar_cliente(), _carregar_casos(), _julgar_resposta(), main(), Avalia resiliência comportamental a prompt injection (Fase 10, avaliação…, _avaliar_provider(), _carregar_casos() (+36 more)

### Community 16 - "useAuthStore"
Cohesion: 0.13
Nodes (18): AdminUsuariosPage(), CadastroPage(), DEMO_ACCOUNTS, LoginPage(), PlaygroundPanel(), handleSubmit(), AdminGearMenu(), Header() (+10 more)

### Community 17 - "approve_pending"
Cohesion: 0.11
Nodes (29): ApprovedPageResponse, approve_pending(), get_pending(), AsyncSession, get, Path, post, Request (+21 more)

### Community 18 - "db/catalog.py"
Cohesion: 0.13
Nodes (30): adicionar_desconto_volume(), calcular_item_cotacao(), criar_pedido(), criar_produto(), listar_descontos_volume(), listar_produtos(), obter_produtos_por_ids(), preco_vigente() (+22 more)

### Community 19 - "ai_usage_report.py"
Cohesion: 0.10
Nodes (32): AiUsageReport, _dia_local(), get_ai_usage_metrics(), datetime, get, Request, Uso de IA do período, estratificado por origem × ambiente × modelo × operação,…, Converte o filtro do painel em limites UTC. "Hoje"/`start_date`/`end_date` são… (+24 more)

### Community 20 - "metricas/page.tsx"
Cohesion: 0.13
Nodes (29): AdminMetricasPage(), CardMetrica(), CardMetricaProps, AMBIENTES_CONHECIDOS, BLOCO_ZERADO, Props, ROTULOS, SecaoPorAmbiente() (+21 more)

### Community 21 - "Guia Claude Code CLI"
Cohesion: 0.06
Nodes (38): Regras de Workspace Antigravity, Princípio docs/ como Fonte Única da Verdade, Container PostgreSQL 15 (Porta 5433), Container Qdrant Vector DB (Porta 6335), Benchmark de Resiliência a Prompt Injection, Isolamento Sintático por Delimitador, Vulnerabilidade a Injeção Indireta via RAG, Otimização de Chunk Size por Bisseção (+30 more)

### Community 22 - "RuntimeSettingsForm.tsx"
Cohesion: 0.14
Nodes (23): RagSearchConfigSection(), carregar(), handleToggle(), OpenRouterModelCard(), init(), formatVram(), RuntimeSettingsForm(), carregar() (+15 more)

### Community 23 - "upload_document"
Cohesion: 0.16
Nodes (21): delete_document_endpoint(), _document_to_response(), download_document_endpoint(), get_document_content_endpoint(), get_documents(), alias, AsyncSession, delete (+13 more)

### Community 24 - "types/chat.ts"
Cohesion: 0.09
Nodes (31): AppointmentCard(), formatarDataHora(), ChatCard(), DocumentDownloadCard(), formatarTamanhoArquivo(), ProductCard(), QuoteCard(), BACKEND_LABELS (+23 more)

### Community 25 - "ChatModal.tsx"
Cohesion: 0.11
Nodes (32): ChatModal(), handleClearHistory(), handleCloseConversation(), handleDrop(), handleRetry(), handleSolicitarAtendente(), submitAudio(), garantirBolha() (+24 more)

### Community 26 - "OpenRouterModelCard.tsx"
Cohesion: 0.09
Nodes (30): CardComCaracteristicas(), formatarContexto(), formatarDataRelativa(), MODALIDADES_NAO_TEXTO, ModelCharacteristicsPanel(), ModelCharacteristicsPanelProps, NOMES_MODALIDADE, CardComCaracteristicas() (+22 more)

### Community 27 - "sales_catalog.py"
Cohesion: 0.07
Nodes (42): Any, spawn_background_task(), _ficha_do_banco(), formatar_ficha_produto(), _produto_id_pelo_nome(), (id, nome do cadastro, ficha formatada) do produto no banco, ou `None` se não…, Ficha do produto mostrada ao cliente depois do "Identifiquei: …"., normalize() (+34 more)

### Community 28 - "rag_collections.py"
Cohesion: 0.16
Nodes (30): activate_collection_endpoint(), create_collection_endpoint(), delete_collection_endpoint(), list_collections_endpoint(), AsyncSession, delete, get, post (+22 more)

### Community 29 - "post_converter_auto_admin"
Cohesion: 0.14
Nodes (28): _calcular_total_pedido(), ConfirmarConversaoRequest, listar_pedidos_admin(), obter_pedido_admin(), post_analisar_comprovante(), post_confirmar_conversao(), post_converter_auto_admin(), post_converter_manual_simples() (+20 more)

### Community 30 - "OllamaClient"
Cohesion: 0.09
Nodes (12): OllamaClient, Any, AsyncClient, setter, Carrega o modelo na memória/VRAM com o keep_alive configurado (elimina cold-…, Descarrega o modelo da VRAM imediatamente (keep_alive: 0)., Consulta GET /api/ps para verificar se o modelo ativo está carregado na VRAM., Envia uma imagem + prompt ao modelo local (Ollama) e devolve o texto cru —… (+4 more)

### Community 31 - "Conversa"
Cohesion: 0.14
Nodes (30): _escalar_conversa_em_background(), Conversa, Uma conversa do chat (R9, Fase 6) — ver decisão de 2026-09-25 em…, _carregar_clientes_por_email(), claim_conversa(), _com_fuso(), devolver_para_ia(), enviar_mensagem_atendente() (+22 more)

### Community 32 - "ingestao/page.tsx"
Cohesion: 0.13
Nodes (23): AbaConfiguracao(), AbaDocumentosIngeridos(), DOMAIN_OPTIONS, IngestaoDocumentosPage(), ModelosPage(), CrawlerReviewQueue(), handleReject(), DOMAIN_OPTIONS (+15 more)

### Community 33 - "agendamentos.py"
Cohesion: 0.17
Nodes (21): admin_consultar_eventos_google(), admin_criar_agendamento_manual(), admin_listar_agendamentos(), AgendamentoManualCreate, AgendamentoOut, cancelar_agendamento(), listar_meus_agendamentos(), AsyncSession (+13 more)

### Community 34 - "AdminChart"
Cohesion: 0.08
Nodes (37): AdminChartCreate, AdminChartOut, AdminChartUpdate, create_admin_chart(), delete_admin_chart(), list_admin_charts(), AsyncSession, BaseModel (+29 more)

### Community 35 - "api/crawler.ts"
Cohesion: 0.12
Nodes (24): CrawlerPanel(), handleSubmit(), marcarAtividade(), LiveProgress, PROGRESSO_INICIAL, handleApprove(), API_BASE_URL, approvePendingPage() (+16 more)

### Community 36 - "LocalModelsTable.tsx"
Cohesion: 0.12
Nodes (27): formatarDataRelativa(), formatarTamanho(), LocalModelsTable(), handleAtivar(), handleBaixarPreset(), LocalModelsTableProps, POPULAR_LOCAL_PRESETS, PresetLocalModel (+19 more)

### Community 37 - "api/orders.py"
Cohesion: 0.13
Nodes (33): calculate_freight_endpoint(), calculate_quote_endpoint(), create_order_endpoint(), get_order_endpoint(), list_orders_endpoint(), _map_order_to_out(), AsyncSession, get (+25 more)

### Community 38 - "B2BMCPClient"
Cohesion: 0.16
Nodes (7): B2BMCPClient, B2BMCPError, Any, Exception, Erro geral de comunicação com o MCP B2B., `itens`: `[{"produto_id": int, "quantidade": int, "centro_distribuicao": str}]`., Converte uma reserva pendente em venda concluída através de comprovante…

### Community 39 - "adminAtendimento.ts"
Cohesion: 0.17
Nodes (22): AdminAtendimentoPage(), ContextoClientePanel(), ContextoClientePanelProps, FilaEsperaPanel(), FilaEsperaPanelProps, formatEspera(), MeusChatsTabs(), MeusChatsTabsProps (+14 more)

### Community 40 - "OpenRouterClient"
Cohesion: 0.09
Nodes (16): LLMStreamChunk, BaseModel, Exception, Um fragmento do stream de `generate_stream`. Fragmentos intermediários vêm só…, Um cliente de visão (local ou externo) não está configurado, não tem capability…, VisionModelIndisponivelError, OpenRouterClient, Any (+8 more)

### Community 41 - "classifier.py"
Cohesion: 0.23
Nodes (17): ClassificationResult, classify(), _classify_heuristic_fallback(), _classify_with_jev(), _classify_with_llm(), _contexto_com_ultima_resposta(), _heuristic_complexity(), IntentClassifierClient (+9 more)

### Community 42 - "extractor.py"
Cohesion: 0.16
Nodes (19): _blocos_de_texto(), extract_catalog_stream(), extract_page_products_local(), extract_page_products_vision(), _extrair_figuras_pagina(), _parse_page_range(), _parse_products_json(), Any (+11 more)

### Community 44 - "admin_atendimento.py"
Cohesion: 0.15
Nodes (22): ClaimRequest, CloseRequest, get_detalhes_conversa(), get_fila_espera(), get_meus_chats(), MensagemAtendenteRequest, post_claim_conversa(), post_close_conversa() (+14 more)

### Community 45 - "models/rag.py"
Cohesion: 0.13
Nodes (23): playground_search(), AsyncSession, post, BinaryQuantizationRequest, CollectionCreateRequest, DocumentIngestResponse, HnswConfigRequest, PayloadIndexRequest (+15 more)

### Community 46 - "dashboards/page.tsx"
Cohesion: 0.26
Nodes (13): AdminDashboardsPage(), CreateChartModal(), CreateChartModalProps, DataRow, AdminChartData, DynamicChartCard(), DynamicChartCardProps, TIPO_LABELS (+5 more)

### Community 47 - "getApiBaseUrl"
Cohesion: 0.28
Nodes (23): AdminProdutosPage(), CATEGORIAS_PADRAO, ProductFormModal(), addAdminProductCompatibility(), addAdminProductVolumeDiscount(), authHeaders(), confirmCatalogExtraction(), createAdminProduct() (+15 more)

### Community 48 - "cliente_mcp_b2b.py"
Cohesion: 0.13
Nodes (20): _descrever_erro(), main(), Cliente de teste do MCP B2B (R12, Fase 5): faz o que a IA de um revendedor…, Um POST `initialize` cru e devolve só o status HTTP — para conferir o `401` sem…, Sessão MCP completa com a chave: `initialize`, `tools/list` (as 4 ferramentas)…, ResultadoMcp, status_sem_sessao(), _texto() (+12 more)

### Community 49 - "api/model_catalog.py"
Cohesion: 0.10
Nodes (36): get_characteristics(), get_model_catalog_http_client(), get_ollama_client(), AsyncClient, AsyncSession, get, ModelCharacteristics, post (+28 more)

### Community 50 - "app/pedidos/page.tsx"
Cohesion: 0.12
Nodes (24): PedidosPageContent(), ProdutoDetalhePage(), ProdutoPageProps, ProdutosPage(), ImageZoomModal(), ImageZoomModalProps, ProductCard(), ProductCardProps (+16 more)

### Community 51 - "types/rag.ts"
Cohesion: 0.05
Nodes (61): CollectionFormModalProps, CURATED_MODELS, PAYLOAD_INDEXES_PADRAO, SCHEMA_TYPES, TEXT_PARAMS_PADRAO, DocumentsTableProps, DOMAIN_OPTIONS, detectarTipoArquivo() (+53 more)

### Community 52 - "pdf_extract.py"
Cohesion: 0.19
Nodes (13): _detectar_gap_coluna(), extract_text_from_pdf(), _extrair_texto_pagina(), PdfExtractionError, Exception, Path, Extração de texto de PDF para ingestão no RAG (R4). # MVP: extração via…, Levantado quando o PDF não pode ser aberto ou processado. (+5 more)

### Community 53 - "api/local_models.py"
Cohesion: 0.16
Nodes (21): activate_model_endpoint(), _consumir_pull(), get_ollama_client(), get_pull_progress_store(), list_local_models_endpoint(), pull_model_endpoint(), pull_status_endpoint(), get (+13 more)

### Community 54 - "adminPedidos.ts"
Cohesion: 0.20
Nodes (18): AdminPedidosPage(), ModalConversaoPedido(), handleAuditarIA(), handleConfirmarComIA(), handleConverterAuto(), handleConverterSimples(), ModalConversaoPedidoProps, analisarComprovante() (+10 more)

### Community 55 - "ImageUploader.tsx"
Cohesion: 0.47
Nodes (4): ImageUploader(), handleChange(), ImageUploaderProps, fileToBase64()

### Community 56 - "orders.ts"
Cohesion: 0.16
Nodes (12): HistoricoPedidosContent(), CreateOrderItemPayload, CreateOrderPayload, fetchOrderById(), fetchOrders(), FreightQuotePayload, FreightQuoteResult, Order (+4 more)

### Community 57 - "models.py"
Cohesion: 0.08
Nodes (30): do_run_migrations(), run_migrations_online(), Endpoints REST administrativos para gestão de Dashboards e Gráficos Dinâmicos., get_escalonamentos(), AsyncSession, get, AiUsageEvent, Modelos SQLAlchemy do backend (primeiro uso real do Postgres — ver… (+22 more)

### Community 59 - "compilerOptions"
Cohesion: 0.07
Nodes (28): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+20 more)

### Community 60 - "orchestrator.py"
Cohesion: 0.09
Nodes (42): CardAgendamento, CardCotacao, CardDocumentoDownload, CardGrafico, CardProduto, ConversaCloseRequest, ConversaHistoricoOut, ConversaMensagemOut (+34 more)

### Community 61 - "devDependencies"
Cohesion: 0.11
Nodes (19): eslint, eslint-config-next, devDependencies, eslint, eslint-config-next, prettier, @tailwindcss/postcss, @testing-library/jest-dom (+11 more)

### Community 62 - "models/catalog.py"
Cohesion: 0.10
Nodes (26): get_admin_produtos(), description, ge, le, Query, get_public_categorias(), get_public_produto(), get_public_produtos() (+18 more)

### Community 63 - "api/agendamentos.ts"
Cohesion: 0.29
Nodes (13): AdminAgendamentosPage(), formatarDataHora(), AgendamentosPage(), formatarDataHora(), cancelarAgendamento(), criarAgendamentoManual(), fetchAdminAgendamentos(), fetchGoogleCalendarEvents() (+5 more)

### Community 64 - "CalendarClient"
Cohesion: 0.15
Nodes (9): get_calendar_client(), Request, CalendarClient, GoogleCalendarMCPClient, is_system_event(), Any, datetime, Protocol (+1 more)

### Community 65 - "app.py"
Cohesion: 0.16
Nodes (17): calcular_resumo_cotacao(), calcular_total_pedido(), formatar_itens_carrinho(), formatar_itens_pedido(), formatar_moeda(), main(), Aplicação Streamlit do Cliente Independente MCP B2B., Formata valor numérico para o padrão de moeda brasileiro R$ X.XXX,XX. (+9 more)

### Community 66 - "ConversaMensagem"
Cohesion: 0.09
Nodes (37): _carregar_contexto_seguro(), Grava a troca antes do `done`: a próxima mensagem sempre encontra esta no…, Histórico recente e resumo da conversa, lidos do Postgres (R9, Fase 6). Falha…, _registrar_troca_segura(), ConversaMensagem, Uma mensagem de uma conversa: do cliente, a resposta do assistente (IA) ou de…, atualizar_resumo(), precisa_resumir() (+29 more)

### Community 67 - "whisper_client.py"
Cohesion: 0.14
Nodes (11): Exception, Protocol, Wrapper de STT (R5) via faster-whisper, rodando na mesma GPU do modelo local.…, Falha de infraestrutura ao carregar o modelo ou transcrever o áudio. Análogo a…, Cliente STT local via faster-whisper. Suporta qualquer formato de áudio que o…, Transcreve `audio_bytes` (ex.: wav, mp3) para texto em português. # MVP: sem…, SttClient, SttIndisponivelError (+3 more)

### Community 68 - "CatalogImportModal.tsx"
Cohesion: 0.11
Nodes (24): arquivoAceito(), CatalogImportModal(), CatalogImportModalProps, CatalogPriceInput(), CatalogPriceInputProps, chaveArquivo(), formatarMoedaInput(), ModalStep (+16 more)

### Community 69 - "RagDocument Model (PostgreSQL)"
Cohesion: 0.23
Nodes (12): Qdrant Point Deletion by Document ID, RagDocument Model (PostgreSQL), Design — Registro e Exclusão de Documentos Ingeridos no RAG, EmbedderRegistry Cache, RagCollection Profile (Immutable Config), RAG Comparative Search Playground, Design — Perfis de Collection Configuráveis + Playground de Busca, Collection Purpose Isolation (Chat vs MCP B2B) (+4 more)

### Community 70 - "layout.tsx"
Cohesion: 0.29
Nodes (5): frontend_app_globals, geistMono, geistSans, metadata, Footer()

### Community 71 - "Injeção de Dados Estruturados de Catálogo no Prompt"
Cohesion: 0.20
Nodes (11): Injeção de Dados Estruturados de Catálogo no Prompt, Plano de Implementação: Orquestrador MCP B2B em Vendas, Resolução de Produtos em Duas Etapas (SQL + LLM), Pipeline de Extração Multimodal de Catálogo, Plano de Implementação: Gestão de Produtos e Catálogos Multimodais, RAG Visual com Qdrant CLIP, Exposição de Tráfego JSON-RPC para Auditoria, Cliente MCP Streamlit Isolado (+3 more)

### Community 72 - "scripts"
Cohesion: 0.13
Nodes (14): name, private, scripts, build, dev, format, format:check, lint (+6 more)

### Community 73 - "Manual Didático: Repowise no Ambiente de Desenvolvimento Agêntico (WSL2, Antigravity IDE, Claude CLI, Kiro CLI)"
Cohesion: 0.08
Nodes (23): 📌 1. Sumário de Recursos, Portas e Convivência no Ecossistema, 2.1 Repowise vs. Graphify: Como se Complementam?, 2.2 Repowise + Headroom: Economia de Tokens em Camadas, 2.3 Repowise + Provedores Locais (Strata e Ollama), 🔄 2. Convivência e Uso Simultâneo com Outras Ferramentas, 3.1 Inicialização Passo a Passo, 3.2 Validação da Integridade do Setup, 🚀 3. Inicialização e Configuração Segura no Repositório (+15 more)

### Community 74 - "inactivity_closure_worker"
Cohesion: 0.40
Nodes (6): fechar_conversas_inativas(), inactivity_closure_worker(), async_sessionmaker, AsyncSession, Encerra conversas com status='aberta' cuja última atualização foi há mais de…, Worker em background executado periodicamente para fechar conversas inativas.

### Community 75 - "Especificação Arquitetural: Ledger Unificado de Uso de IA"
Cohesion: 0.20
Nodes (10): Painel de Métricas e Ledger Unificado de Uso de IA, Plano do Ledger de Uso de IA: Item A - Fundação, Plano do Ledger de Uso de IA: Item B - Origem Chat, Plano do Ledger de Uso de IA: Item D - Origem Admin, Plano do Ledger de Uso de IA: Item E - Painel, Especificação Arquitetural: Ledger Item B - Origem Chat, Especificação Arquitetural: Ledger Item D - Origem Admin, Semântica de Null (Não Medido) vs Zero (Grátis) (+2 more)

### Community 76 - "criar_escalonamento"
Cohesion: 0.50
Nodes (4): _persistir_escalonamento_em_background(), Roda via `asyncio.create_task` — nunca aguardada pelo stream SSE que a…, criar_escalonamento(), AsyncSession

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

### Community 85 - "db_connector.py"
Cohesion: 0.33
Nodes (6): AsyncConnection, Conector de leitura a um banco de dados relacional para o RAG (R4). # MVP:…, Transforma uma linha (dict coluna -> valor) em texto plano, pronto para…, Lê todas as linhas de `table_name` e devolve uma lista de textos (um por linha,…, read_table_as_text(), row_to_text()

### Community 86 - "api/crawler.py"
Cohesion: 0.13
Nodes (30): is_admin_request(), alias, AsyncSession, Header, Query, Dependência FastAPI compartilhada para restringir endpoints a administradores…, Extrai o token admin de `Authorization`/`X-Auth-Token`/`?token=` (nessa…, require_admin() (+22 more)

### Community 87 - "ChatChartCard.tsx"
Cohesion: 0.24
Nodes (9): ChartConfig, ChartRenderer(), ChartRendererProps, DEFAULT_PALETTE, formatValue(), ChatChartCard(), ChatChartCardProps, TIPO_LABELS (+1 more)

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

### Community 103 - "SearchableSelect.tsx"
Cohesion: 0.40
Nodes (3): SearchableSelect(), SearchableSelectOption, SearchableSelectProps

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

### Community 111 - "LocalVisionResult"
Cohesion: 0.50
Nodes (3): LocalVisionResult, str, Subclasse de str que preserva o texto retornado por…

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

### Community 122 - "Regras de Escopo do MVP"
Cohesion: 0.67
Nodes (3): Regras de Escopo do MVP, Exclusões Formais de Escopo do MVP, Padrão de Comentários de Escopo # MVP

### Community 123 - "Endpoint GET /api/admin/metrics/ai-usage"
Cohesion: 0.67
Nodes (3): Endpoint GET /api/admin/metrics/ai-usage, Reconstrução do Painel /admin/metricas no Frontend, Serviço de Roll-up Puro ai_usage_report

### Community 161 - "RAGConnectionError"
Cohesion: 0.12
Nodes (12): ClipImageStore, AsyncQdrantClient, Embeda e grava uma imagem. Retorna o `image_id` gerado., Exclui um ponto por ID da collection CLIP., Exclui todos os pontos da collection CLIP pertencentes ao produto_id., Exclui pontos da collection CLIP por imagem_url., Operações de ingestão e busca sobre a collection CLIP no Qdrant. Cria a…, Remove `collection_name` do Qdrant. Idempotente: se a collection já não existir… (+4 more)

### Community 162 - "chunk_size_search.py"
Cohesion: 0.19
Nodes (15): _apagar_collection(), _avaliar_chunk_size(), _criar_e_popular_collection(), _FixedCollectionRagClient, main(), Path, Busca por bisseção do `chunk_size` que maximiza a qualidade do RAG (R4, Fase…, Implementa o Protocol `RAGClient` apontando para UMA collection fixa pelo nome,… (+7 more)

### Community 163 - "api/image_search.py"
Cohesion: 0.20
Nodes (17): _get_clip_embedder(), _get_clip_store(), _get_rag_client(), _get_vision_client(), identify_image(), ingest_image(), post, Request (+9 more)

### Community 164 - "classificacao.py"
Cohesion: 0.20
Nodes (17): ClienteCompra, Compra de um cliente (R10) — quantidade e recência definem se ele é Cliente ou…, atualizar_perfil(), carregar_contexto_cliente(), Classificacao, classificar(), _com_fuso(), e_mensagem_so_de_email() (+9 more)

### Community 166 - "useChatStore.ts"
Cohesion: 0.21
Nodes (8): PerfilPage(), FAQ_ITEMS, getUserConversationStorageKey(), getVisitPrompt(), HumanAttendanceStatus, LEGACY_STORAGE_KEY, useChatStore, USER_STORAGE_PREFIX

### Community 167 - "image_processor.py"
Cohesion: 0.22
Nodes (12): extract_text_from_base64(), extract_text_from_bytes(), ImageFormatError, imagem_excede_tamanho_maximo(), OcrIndisponivelError, ValueError, OCR para imagens dirigidas (R6) — extrai texto de PNG/JPG via pytesseract. #…, Formato de imagem não suportado ou dados corrompidos. (+4 more)

### Community 168 - "uploads.py"
Cohesion: 0.35
Nodes (10): _get_base_dir(), obter_imagem_produto(), obter_imagem_temporaria(), get, Path, Request, Endpoints de servimento e persistência de imagens de produtos. GET…, _validar_nome_arquivo() (+2 more)

### Community 169 - "ImageSearchResult"
Cohesion: 0.24
Nodes (7): ImageSearchResult, BaseModel, Busca imagens similares a partir de uma imagem de consulta., Busca imagens similares a partir de uma descrição textual., Reordena resultados de busca por imagem e corta para `top_k`. Reranking básico…, rerank_image_results(), field_validator

### Community 170 - "settings.py"
Cohesion: 0.42
Nodes (9): AppSetting, Parâmetros de configuração e execução persistidos no banco., get_all_app_settings(), get_app_setting(), Any, AsyncSession, Persistência de configurações de execução no PostgreSQL., save_multiple_app_settings() (+1 more)

### Community 171 - "catalog_extractor.py"
Cohesion: 0.27
Nodes (9): CatalogConfirmItem, CatalogConfirmRequest, CatalogConfirmResponse, ExtractedProduct, BaseModel, Item a ser persistido na confirmação., Lote de produtos aprovados pelo administrador na tabela de conferência., Resultado da gravação definitiva no banco e catálogo visual CLIP. (+1 more)

### Community 172 - "apiBaseUrl.ts"
Cohesion: 0.28
Nodes (6): ProductFormModalProps, ProductListTable(), ProductListTableProps, StockDetailBadgeProps, AdminProduct, AdminProductStock

### Community 175 - "identify_product_by_image"
Cohesion: 0.33
Nodes (7): identify_product_by_image(), ImageIdentificationResult, _parse_vision_answer(), BaseModel, Executa o fluxo de identificação de produto por imagem. `vision_client` é duck-…, Resultado do fluxo de identificação de produto por imagem. status: -…, _VisionAnswer

### Community 176 - "listar_estoque"
Cohesion: 0.33
Nodes (5): listar_estoque(), Verifica se dois produtos são compatíveis, nos dois sentidos (par cadastrado…, sao_compativeis(), Traz o estoque total (soma entre centros de distribuição) e o detalhamento por…, ProdutoEstoque

### Community 177 - "ExternalBackendIndisponivelError"
Cohesion: 0.33
Nodes (5): _AgendamentoFalhaValidacao, ExternalBackendIndisponivelError, Exception, Falha de infraestrutura no backend externo (OpenRouter) — sem fallback…, Carrega a resposta já pronta para o visitante quando…

### Community 178 - "processar_conversao_comprovante"
Cohesion: 0.33
Nodes (5): processar_conversao_comprovante(), Any, async_sessionmaker, AsyncSession, Avalia o comprovante de pagamento via ComprovanteEvaluator e converte o status…

### Community 179 - "require_admin"
Cohesion: 0.40
Nodes (5): alias, AsyncSession, Header, Query, require_admin()

### Community 180 - "exportMetrics.ts"
Cohesion: 0.50
Nodes (4): RFC-4180, escaparCampoCsv(), exportMetricsToCsv(), exportMetricsToJson()

### Community 182 - "ChatMessageRequest"
Cohesion: 0.50
Nodes (3): ChatMessageRequest, model_validator, Corpo de `POST /api/chat/messages`.

### Community 183 - ".pull_model_streaming"
Cohesion: 0.50
Nodes (3): PullProgressLine, Baixa `name` (biblioteca do Ollama ou `hf.co/usuario/repo[:tag]` do Hugging…, Uma linha do stream NDJSON de `POST /api/pull` — ver…

### Community 184 - "VisionResult"
Cohesion: 0.50
Nodes (3): str, Subclasse de str que preserva o texto retornado e carrega telemetria de tokens…, VisionResult

### Community 185 - "detect_chart_request"
Cohesion: 0.50
Nodes (3): detect_chart_request(), Gate de intenção para o Agente Analítico de Gráficos Dinâmicos…, Identifica se o prompt do usuário expressa a intenção explícita de gerar ou…

## Knowledge Gaps
- **298 isolated node(s):** `assistente-multimodal-backend`, `cliente-mcp-b2b`, `semi`, `singleQuote`, `trailingComma` (+293 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **34 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ClipEmbedder` connect `ClipEmbedder` to `RAGConnectionError`, `api/image_search.py`, `api/chat.py`, `admin_products.py`, `main.py`, `ImageSearchResult`, `typing`, `identify_product_by_image`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Why does `RAGConnectionError` connect `RAGConnectionError` to `ClipEmbedder`, `api/image_search.py`, `api/chat.py`, `ImageSearchResult`, `QdrantRAGClient`, `typing`, `approve_pending`, `api/crawler.py`, `upload_document`, `rag_collections.py`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Why does `QdrantRAGClient` connect `QdrantRAGClient` to `RAGConnectionError`, `chunk_size_search.py`, `b2b.py`, `main.py`, `ingest.py`, `api/runtime_settings.py`, `models/rag.py`, `typing`, `approve_pending`, `api/crawler.py`, `upload_document`, `rag_collections.py`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Are the 29 inferred relationships involving `QdrantRAGClient` (e.g. with `_FixedCollectionRagClient` and `main()`) actually correct?**
  _`QdrantRAGClient` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `OllamaClient` (e.g. with `main()` and `main()`) actually correct?**
  _`OllamaClient` has 17 INFERRED edges - model-reasoned connections that need verification._
- **What connects `assistente-multimodal-backend`, `cliente-mcp-b2b`, `semi` to the rest of the system?**
  _298 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `comprovante_evaluator.py` be split into smaller, more focused modules?**
  _Cohesion score 0.13043478260869565 - nodes in this community are weakly interconnected._