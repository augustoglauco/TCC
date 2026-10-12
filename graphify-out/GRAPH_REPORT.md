# Graph Report - TCC  (2026-10-12)

## Corpus Check
- 355 files · ~427,626 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 15 file(s) not represented in the graph (top: (none) 7, .example 3, .ini 1)

## Summary
- 2781 nodes · 7188 edges · 156 communities (110 shown, 46 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 576 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Rag Image Search
- Services Comprovante Evaluator
- Router Scheduling
- Router Classifier
- Mcp B2B Module
- Chat Module
- Admin Products Module
- Rag Quality Run Eval
- Rag Qdrant Client
- Router Openrouter Client
- Rag Dependencies Module
- Types Rag
- Versions 0001 Create Rag Documents
- Mcp Server Auth
- Auth Module
- Router Sales Catalog
- Layout Module
- Crawler Module
- Db Catalog
- Services Ai Usage Report
- Metrics Module
- Docs Architecture
- Admin Runtimesettingsform
- Rag Module
- Types Chat
- Chat Chatmodal
- Admin Pullmodelform
- Memory Store
- Rag Collections Registry
- Admin Pedidos Conversao Module
- Router Ollama Client
- Services Atendimento Service
- Ingestao Page
- Agendamentos Module
- Services Safe Sql
- Crawler Module
- Admin Localmodelstable
- Orders Module
- Client Module
- Adminatendimento Module
- Chat Module
- Services Ingestion Metrics
- Admin Charts Module
- Ingestao Page
- Admin Atendimento Module
- Rag Module
- Charts Chartrenderer
- Products Catalogimportmodal
- Scripts Cliente Mcp B2B
- Model Catalog Characteristics
- Products Module
- Admin Documentviewmodal
- Adminproducts Module
- Local Models Module
- Adminpedidos Module
- Utils Exportmetrics
- Orders Module
- Frontend Package
- Products Productlisttable
- Frontend Tsconfig
- Model Catalog Module
- Frontend Package
- Products Module
- Agendamentos Module
- Mcp Client Google Calendar
- App Module
- Hooks Usechatstore
- Stt Whisper Client
- Logging Config Module
- Specs 2026 09 15
- Uploads Module
- Plans 2026 09 24
- Frontend Package
- Versions 0002 Rag Collections
- Services Chat Closure Service
- Specs 2026 10 08
- Tom Escalonamentos Module
- Goup Module
- Manuais Howto Administrador
- Manuais Howto Usuario
- Manuais Prompts E Instrucoes Llm
- Manuais Strata Manual
- Plans 2026 09 17
- Specs 2026 09 16
- Frontend Package
- Rag Db Connector
- Admin Auth Module
- Chat Module
- Mcp Server B2B
- Router Playbooks
- Plans 2026 09 15
- Plans 2026 09 19
- Plans 2026 10 04
- Specs 2026 09 23
- Specs 2026 09 19
- Specs 2026 09 21
- Specs 2026 10 07
- Chat Audiorecorder
- Rag Quality Bateria Perguntas Rag
- Plans 2026 10 07
- Plans 2026 09 21
- Specs 2026 09 24
- Specs 2026 10 03
- Ui Searchableselect
- G Module
- Plans 2026 09 16
- Plans 2026 10 08
- Frontend Package
- Frontend .Prettierrc
- Versions 0012 Conversa Metricas
- Router Ollama Client
- Router Ollama Client
- Router Ollama Client
- Docs Agentic Workflow
- Docs Frontend
- Plans 2026 09 05
- Specs 2026 09 05
- Router Intents Readme
- Versions 0009 Mcp B2B Ferramentas
- Versions 0014 Pedido Email Conversa
- Versions 0018 Conversas Status Custos
- Versions 0024 Ai Usage Events
- Claude Module
- Plans 2026 10 08
- Frontend Playwright.Config
- Docs Architecture
- Docs Architecture
- Plans 2026 10 08
- Plans 2026 10 08
- Frontend Agents
- Frontend Postcss.Config
- Docs Architecture
- Docs Architecture
- Docs Architecture
- Docs Evaluation
- Plans 2026 10 08
- Specs 2026 10 08
- Backend Pyproject
- Cliente B2B Pyproject

## God Nodes (most connected - your core abstractions)
1. `getApiBaseUrl()` - 79 edges
2. `useAuthStore` - 76 edges
3. `react` - 59 edges
4. `QdrantRAGClient` - 58 edges
5. `create_b2b_mcp_server()` - 55 edges
6. `handle_message()` - 49 edges
7. `OllamaClient` - 46 edges
8. `send_message()` - 45 edges
9. `RAGConnectionError` - 45 edges
10. `obter_produto()` - 34 edges

## Surprising Connections (you probably didn't know these)
- `Otimização de Chunk Size por Bisseção` --conceptually_related_to--> `Requisito R4: RAG Multimodal Híbrido`  [INFERRED]
  backend/eval/rag_quality/README.md → docs/ARCHITECTURE.md
- `Políticas de Troca, Devolução e Garantia` --shares_data_with--> `Requisito R4: RAG Multimodal Híbrido`  [INFERRED]
  backend/scripts/sample_docs/atendimento/politicas_troca_garantia.txt → docs/ARCHITECTURE.md
- `Manual Técnico Resumido Gerador GD-30` --shares_data_with--> `Requisito R4: RAG Multimodal Híbrido`  [INFERRED]
  backend/scripts/sample_docs/suporte/manual_gerador_gd30.txt → docs/ARCHITECTURE.md
- `Catálogo de Geradores a Diesel Industrial` --shares_data_with--> `Requisito R4: RAG Multimodal Híbrido`  [INFERRED]
  backend/scripts/sample_docs/vendas/catalogo_geradores.txt → docs/ARCHITECTURE.md
- `Guia Claude Code CLI` --references--> `Guia de Fluxo de Trabalho Agêntico`  [EXTRACTED]
  CLAUDE.md → docs/AGENTIC_WORKFLOW.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Padrão de Arquitetura Dual MCP (Cliente e Servidor)** — docs_architecture_r11_mcp_calendar, docs_architecture_r12_mcp_b2b, goup_calendar_mcp_service, goup_mcp_b2b_service [EXTRACTED 1.00]
- **Baterias de Avaliação Experimental do TCC** — docs_evaluation_eval1_router, docs_evaluation_eval2_rag, docs_evaluation_eval3_latency, docs_evaluation_eval4_prompt_injection [EXTRACTED 1.00]
- **Ecossistema Tripartite de Desenvolvimento Agêntico** — docs_agentic_workflow_antigravity, docs_agentic_workflow_claude_cli, docs_agentic_workflow_kiro_cli [EXTRACTED 1.00]
- **Evolução do Pipeline e Gestão de Documentos RAG** — docs_superpowers_plans_2026_09_14_registro_documentos_rag_registro_postgres_qdrant, docs_superpowers_plans_2026_09_15_rag_collections_config_perfis_collection, docs_superpowers_plans_2026_09_19_crawler_paginas_crawler_bfs, docs_superpowers_plans_2026_10_04_download_documentos_rag_chat_download_direto_chat [INFERRED 0.85]
- **Ciclo de Vendas B2B, Integração MCP e Conversão Financeira** — docs_superpowers_plans_2026_09_24_orquestrador_mcp_b2b_vendas_injecao_catalogo_paralela, docs_superpowers_plans_2026_09_25_admin_produtos_catalogo_extracao_multimodal_catalogo, docs_superpowers_plans_2026_09_29_cliente_mcp_b2b_cliente_independente_streamlit, docs_superpowers_plans_2026_10_05_conversao_reserva_venda_comprovante_evaluator_multimodal [INFERRED 0.85]
- **Ciclo de Vida Conversacional, Escalonamento Humano e Auditoria de Custos** — docs_superpowers_plans_2026_09_23_monitor_de_tom_analise_paralela_sentimento, docs_superpowers_plans_2026_10_03_contabilizador_tokens_custos_ciclo_inatividade_conversa, docs_superpowers_plans_2026_10_05_atendimento_humano_transbordo_transbordo_human_in_the_loop [INFERRED 0.85]
- **MCP B2B Integration & Transactional Ecosystem** — docs_superpowers_specs_2026_09_21_ingestao_mcp_b2b_design_spec, docs_superpowers_specs_2026_09_24_orquestrador_mcp_b2b_vendas_design_spec, docs_superpowers_specs_2026_09_29_cliente_mcp_b2b_design_spec, docs_superpowers_specs_2026_10_05_conversao_reserva_venda_design_spec [EXTRACTED 1.00]
- **RAG Document Lifecycle from Ingestion to User Retrieval** — docs_superpowers_specs_2026_09_14_registro_documentos_rag_design_spec, docs_superpowers_specs_2026_09_15_rag_collections_config_design_spec, docs_superpowers_specs_2026_09_19_crawler_paginas_design_spec, docs_superpowers_specs_2026_10_04_download_documentos_rag_chat_design_spec [EXTRACTED 1.00]
- **Customer Support Escalation and Human Handoff Flow** — docs_superpowers_specs_2026_09_23_monitor_de_tom_design_spec, docs_superpowers_specs_2026_10_03_atendimento_humano_transbordo_design_spec, docs_superpowers_specs_2026_09_29_gestao_agendamentos_design_spec [EXTRACTED 1.00]
- **Pipeline e Arquitetura do Ledger Unificado de Uso de IA** — docs_superpowers_specs_2026_10_08_ledger_uso_ia_origem_ambiente_modelo_design_dimensoes_ledger, docs_superpowers_plans_2026_10_08_ledger_uso_ia_item_a_fundacao_funcao_registrar_uso_ia, docs_superpowers_specs_2026_10_08_ledger_uso_ia_item_e_painel_design_semantica_null_vs_zero, docs_manuais_howto_administrador_metricas_ledger_painel [EXTRACTED 1.00]
- **Pipeline de Defesa e Segurança Contra Prompt Injection** — docs_superpowers_plans_2026_10_07_seguranca_prompt_injection_mcp_modulo_prompt_safety, docs_superpowers_plans_2026_10_07_seguranca_prompt_injection_mcp_sandwich_prompting, docs_manuais_prompts_e_instrucoes_llm_prompt_orchestrator, docs_manuais_prompts_e_instrucoes_llm_prompt_injection_judge [EXTRACTED 1.00]
- **Stack de Inferência Local e Otimização de Memória CUDA / MoE** — docs_manuais_strata_manual_strata_cuda_engine, docs_manuais_strata_manual_strata_memory_lifecycle, docs_manuais_headroom_manual_headroom_context_optimization, docs_manuais_howto_administrador_gestao_modelos_ia [INFERRED 0.85]

## Communities (156 total, 46 thin omitted)

### Community 0 - "Rag Image Search"
Cohesion: 0.05
Nodes (19): delete_admin_produto(), delete_imagem_produto(), _get_clip_embedder(), _get_clip_store(), _get_rag_client(), _get_vision_client(), identify_image(), ingest_image() (+11 more)

### Community 1 - "Services Comprovante Evaluator"
Cohesion: 0.05
Nodes (19): _blocos_de_texto(), extract_catalog_stream(), extract_page_products_local(), extract_page_products_vision(), _extrair_figuras_pagina(), _parse_page_range(), _parse_products_json(), extract_text_from_bytes() (+11 more)

### Community 2 - "Router Scheduling"
Cohesion: 0.06
Nodes (38): CardAgendamento, _AgendamentoFalhaValidacao, _buscar_documentos_rag(), _construir_card_documento_download(), _construir_card_vendas(), e_referencia_anterior(), _emitir_resposta_agendamento(), _extrair_produtos_do_contexto() (+30 more)

### Community 3 - "Router Classifier"
Cohesion: 0.07
Nodes (33): spawn_background_task(), AiUsageEvent, classify_page(), PageClassification, _strip_code_fence(), ClassificationResult, classify(), _classify_heuristic_fallback() (+25 more)

### Community 4 - "Mcp B2B Module"
Cohesion: 0.07
Nodes (37): criar_pedido(), EstoqueInsuficienteError, obter_produtos_por_ids(), ProdutoInexistenteError, sao_compativeis(), create_b2b_mcp_server(), _abrir_sessao_bd(), catalogo_produto_detalhe() (+29 more)

### Community 5 - "Chat Module"
Cohesion: 0.05
Nodes (37): _carregar_contexto_anterior_seguro(), _carregar_conversa_db_segura(), _carregar_dados_cliente_seguro(), deletar_conversa(), fechar_conversa_endpoint(), get_calendar_client(), get_clip_embedder(), get_clip_store() (+29 more)

### Community 6 - "Admin Products Module"
Cohesion: 0.07
Nodes (35): CompatibilidadePayload, delete_compatividade(), delete_desconto_volume(), DescontoVolumePayload, EstoqueUpdatePayload, get_admin_categorias(), get_admin_produto(), get_admin_produtos() (+27 more)

### Community 7 - "Rag Quality Run Eval"
Cohesion: 0.07
Nodes (21): _avaliar_cliente(), _carregar_casos(), _julgar_resposta(), main(), _apagar_collection(), _avaliar_chunk_size(), _carregar_casos(), _fonte_e_correta() (+13 more)

### Community 8 - "Rag Qdrant Client"
Cohesion: 0.06
Nodes (15): _criar_e_popular_collection(), _FixedCollectionRagClient, chunk_text(), _normalizar_preservando_linhas(), TextEmbedder, _ensure_collection_exists(), _extract_text(), ingest_bytes() (+7 more)

### Community 9 - "Router Openrouter Client"
Cohesion: 0.06
Nodes (15): _build_response(), _get_clients(), get_runtime_settings(), preload_local_model(), unload_local_model(), update_runtime_settings(), AppSetting, get_all_app_settings() (+7 more)

### Community 10 - "Rag Dependencies Module"
Cohesion: 0.08
Nodes (13): get_db_session(), get_embedder_registry(), get_qdrant_client(), get_uploads_dir(), _apply_runtime_settings(), create_app(), lifespan(), ActiveCollectionRagClient (+5 more)

### Community 11 - "Types Rag"
Cohesion: 0.07
Nodes (39): CollectionFormModalProps, CURATED_MODELS, PAYLOAD_INDEXES_PADRAO, SCHEMA_TYPES, TEXT_PARAMS_PADRAO, CollectionsTableProps, DocumentsTableProps, CollectionOptionCard() (+31 more)

### Community 12 - "Versions 0001 Create Rag Documents"
Cohesion: 0.06
Nodes (16): upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade() (+8 more)

### Community 13 - "Mcp Server Auth"
Cohesion: 0.06
Nodes (15): AutenticacaoMcpB2B, carregar_chaves_parceiros(), ChaveParceiroVerifier, ChavesParceirosInvalidasError, configuracao_auth(), _origem(), preparar_autenticacao(), seguranca_de_transporte() (+7 more)

### Community 14 - "Auth Module"
Cohesion: 0.09
Nodes (19): get_current_user_endpoint(), list_users_endpoint(), login_endpoint(), obter_perfil_cliente(), register_endpoint(), verificar_admin_por_token(), Cliente, ClienteCompra (+11 more)

### Community 15 - "Router Sales Catalog"
Cohesion: 0.08
Nodes (21): _documento_relevante_para_produto(), _ficha_do_banco(), formatar_ficha_produto(), identify_product_by_image(), ImageIdentificationResult, _parse_vision_answer(), _produto_id_pelo_nome(), _remover_acentos() (+13 more)

### Community 16 - "Layout Module"
Cohesion: 0.09
Nodes (30): AdminUsuariosPage(), CadastroPage(), DEMO_ACCOUNTS, LoginPage(), PerfilPage(), geistMono, geistSans, metadata (+22 more)

### Community 17 - "Crawler Module"
Cohesion: 0.09
Nodes (17): approve_pending(), get_pending(), reject_pending(), run_crawler_stream(), event_stream(), _sse(), _to_pending_response(), CrawlerPendingPage (+9 more)

### Community 18 - "Db Catalog"
Cohesion: 0.10
Nodes (21): adicionar_desconto_volume(), atualizar_estoque(), atualizar_produto(), calcular_item_cotacao(), criar_compatibilidade(), criar_produto(), deletar_produto(), listar_descontos_volume() (+13 more)

### Community 19 - "Services Ai Usage Report"
Cohesion: 0.09
Nodes (19): _dia_local(), get_ai_usage_metrics(), require_admin(), _resolver_janela(), _Acumulador, _agrupar(), AiUsageReport, Atendimento (+11 more)

### Community 20 - "Metrics Module"
Cohesion: 0.15
Nodes (30): AdminMetricasPage(), RefreshIcon(), CardMetrica(), CardMetricaProps, AMBIENTES_CONHECIDOS, BLOCO_ZERADO, Props, ROTULOS (+22 more)

### Community 21 - "Docs Architecture"
Cohesion: 0.06
Nodes (36): Regras de Workspace Antigravity, Container PostgreSQL 15 (Porta 5433), Container Qdrant Vector DB (Porta 6335), Benchmark de Resiliência a Prompt Injection, Isolamento Sintático por Delimitador, Otimização de Chunk Size por Bisseção, Expansão de Palavras-Chave de Domínio, Políticas de Troca, Devolução e Garantia (+28 more)

### Community 22 - "Admin Runtimesettingsform"
Cohesion: 0.11
Nodes (32): RagSearchConfigSection(), carregar(), handleToggle(), CardComCaracteristicas(), FREE_MODELS, OpenRouterModelCard(), init(), OpenRouterModelCardProps (+24 more)

### Community 23 - "Rag Module"
Cohesion: 0.12
Nodes (14): delete_document_endpoint(), _document_to_response(), download_document_endpoint(), get_document_content_endpoint(), get_documents(), reingest_document_endpoint(), upload_document(), RagDocument (+6 more)

### Community 24 - "Types Chat"
Cohesion: 0.11
Nodes (28): AppointmentCard(), formatarDataHora(), ChatCard(), ChatChartCard(), ChatChartCardProps, TIPO_LABELS, DocumentDownloadCard(), formatarTamanhoArquivo() (+20 more)

### Community 25 - "Chat Chatmodal"
Cohesion: 0.12
Nodes (30): ChatModal(), handleClearHistory(), handleCloseConversation(), handleDrop(), handleRetry(), handleSolicitarAtendente(), submitAudio(), garantirBolha() (+22 more)

### Community 26 - "Admin Pullmodelform"
Cohesion: 0.13
Nodes (29): Chip(), formatarContexto(), formatarDataRelativa(), MODALIDADES_NAO_TEXTO, ModelCharacteristicsPanel(), ModelCharacteristicsPanelProps, NOMES_MODALIDADE, lerNomeEmAndamento() (+21 more)

### Community 27 - "Memory Store"
Cohesion: 0.09
Nodes (15): _carregar_contexto_seguro(), _gravar_mensagem_cliente_segura(), _registrar_troca_segura(), atualizar_resumo(), precisa_resumir(), carregar_contexto(), contar_mensagens(), ContextoConversa (+7 more)

### Community 28 - "Rag Collections Registry"
Cohesion: 0.14
Nodes (16): activate_collection_endpoint(), create_collection_endpoint(), delete_collection_endpoint(), list_collections_endpoint(), _quantization_config_dict(), _to_response(), RagCollection, CollectionResponse (+8 more)

### Community 29 - "Admin Pedidos Conversao Module"
Cohesion: 0.15
Nodes (11): _calcular_total_pedido(), ConfirmarConversaoRequest, listar_pedidos_admin(), obter_pedido_admin(), post_analisar_comprovante(), post_confirmar_conversao(), post_converter_auto_admin(), post_converter_manual_simples() (+3 more)

### Community 31 - "Services Atendimento Service"
Cohesion: 0.14
Nodes (14): Conversa, ConversaMensagem, _carregar_clientes_por_email(), claim_conversa(), _com_fuso(), devolver_para_ia(), enviar_mensagem_atendente(), escalar_para_humano() (+6 more)

### Community 32 - "Ingestao Page"
Cohesion: 0.16
Nodes (24): AbaConfiguracao(), AbaCrawler(), AbaDocumentosIngeridos(), DOMAIN_OPTIONS, IngestaoDocumentosPage(), ModelosPage(), DocumentsTable(), confirmarExclusao() (+16 more)

### Community 33 - "Agendamentos Module"
Cohesion: 0.13
Nodes (10): admin_consultar_eventos_google(), admin_criar_agendamento_manual(), admin_listar_agendamentos(), AgendamentoManualCreate, AgendamentoOut, cancelar_agendamento(), get_calendar_client(), listar_meus_agendamentos() (+2 more)

### Community 34 - "Services Safe Sql"
Cohesion: 0.13
Nodes (9): _detect_chart_type(), extract_prompt_inline_data(), _generate_sql_with_llm(), process_dynamic_chart_request(), execute_readonly_sql(), get_catalog_schema_prompt(), SQLSecurityError, _validar_tabelas_permitidas() (+1 more)

### Community 35 - "Crawler Module"
Cohesion: 0.15
Nodes (24): CrawlerPanel(), handleSubmit(), marcarAtividade(), LiveProgress, PROGRESSO_INICIAL, CrawlerReviewQueue(), handleApprove(), handleReject() (+16 more)

### Community 36 - "Admin Localmodelstable"
Cohesion: 0.13
Nodes (24): CardComCaracteristicas(), formatarDataRelativa(), formatarTamanho(), LocalModelsTable(), handleAtivar(), handleBaixarPreset(), LocalModelsTableProps, POPULAR_LOCAL_PRESETS (+16 more)

### Community 37 - "Orders Module"
Cohesion: 0.18
Nodes (17): calculate_freight_endpoint(), calculate_quote_endpoint(), create_order_endpoint(), get_order_endpoint(), list_orders_endpoint(), _map_order_to_out(), listar_pedidos(), FreightQuoteIn (+9 more)

### Community 38 - "Client Module"
Cohesion: 0.16
Nodes (4): main(), B2BAuthError, B2BMCPClient, B2BMCPError

### Community 39 - "Adminatendimento Module"
Cohesion: 0.18
Nodes (22): AdminAtendimentoPage(), ContextoClientePanel(), ContextoClientePanelProps, FilaEsperaPanel(), FilaEsperaPanelProps, formatEspera(), MeusChatsTabs(), MeusChatsTabsProps (+14 more)

### Community 40 - "Chat Module"
Cohesion: 0.10
Nodes (10): obter_conversa(), CardCotacao, CardDocumentoDownload, CardGrafico, CardProduto, ChatDoneEventData, ChatMessageRequest, ConversaHistoricoOut (+2 more)

### Community 41 - "Services Ingestion Metrics"
Cohesion: 0.14
Nodes (12): main(), main(), main(), main(), get_settings(), Settings, create_db_engine(), create_session_factory() (+4 more)

### Community 42 - "Admin Charts Module"
Cohesion: 0.16
Nodes (9): AdminChartCreate, AdminChartOut, AdminChartUpdate, create_admin_chart(), delete_admin_chart(), list_admin_charts(), refresh_admin_chart(), update_admin_chart() (+1 more)

### Community 43 - "Ingestao Page"
Cohesion: 0.15
Nodes (17): AbaEnviarDocumento(), handleCriarCollectionRapida(), handleSelectCollectionChange(), handleSubmit(), CollectionFormModal(), handleSubmit(), resetar(), CollectionsTable() (+9 more)

### Community 44 - "Admin Atendimento Module"
Cohesion: 0.15
Nodes (9): ClaimRequest, CloseRequest, get_detalhes_conversa(), get_fila_espera(), get_meus_chats(), MensagemAtendenteRequest, post_claim_conversa(), post_close_conversa() (+1 more)

### Community 45 - "Rag Module"
Cohesion: 0.14
Nodes (15): playground_search(), BinaryQuantizationRequest, CollectionCreateRequest, DocumentIngestResponse, HnswConfigRequest, PayloadIndexRequest, PlaygroundDocumentResult, PlaygroundResultItem (+7 more)

### Community 46 - "Charts Chartrenderer"
Cohesion: 0.17
Nodes (19): AdminDashboardsPage(), CreateChartModal(), CreateChartModalProps, DataRow, AdminChartData, DynamicChartCard(), DynamicChartCardProps, TIPO_LABELS (+11 more)

### Community 47 - "Products Catalogimportmodal"
Cohesion: 0.12
Nodes (22): arquivoAceito(), CatalogImportModal(), CatalogImportModalProps, CatalogPriceInput(), CatalogPriceInputProps, chaveArquivo(), formatarMoedaInput(), ModalStep (+14 more)

### Community 48 - "Scripts Cliente Mcp B2B"
Cohesion: 0.14
Nodes (7): _descrever_erro(), main(), ResultadoMcp, status_sem_sessao(), _texto(), verificar_mcp_b2b(), _probe_status_http()

### Community 49 - "Model Catalog Characteristics"
Cohesion: 0.15
Nodes (10): ModelCharacteristics, _buscar_linha(), _context_length_do_model_info(), _esta_fresco(), _fetch_huggingface(), _fetch_ollama(), _fetch_openrouter(), _get_openrouter_catalog() (+2 more)

### Community 50 - "Products Module"
Cohesion: 0.18
Nodes (17): ProdutoDetalhePage(), ProdutoPageProps, ProdutosPage(), ImageZoomModal(), ImageZoomModalProps, ProductCard(), ProductCardProps, fetchProductById() (+9 more)

### Community 51 - "Admin Documentviewmodal"
Cohesion: 0.15
Nodes (19): detectarTipoArquivo(), DocumentViewModal(), DocumentViewModalProps, FileType, parseCSV(), parseLinhaCSV(), PlaygroundManualModal(), PlaygroundManualModalProps (+11 more)

### Community 52 - "Adminproducts Module"
Cohesion: 0.32
Nodes (20): ProductFormModal(), addAdminProductCompatibility(), addAdminProductVolumeDiscount(), authHeaders(), confirmCatalogExtraction(), createAdminProduct(), deleteAdminProductCompatibility(), deleteAdminProductImage() (+12 more)

### Community 53 - "Local Models Module"
Cohesion: 0.18
Nodes (12): activate_model_endpoint(), _consumir_pull(), get_ollama_client(), get_pull_progress_store(), list_local_models_endpoint(), pull_model_endpoint(), pull_status_endpoint(), ActivateModelRequest (+4 more)

### Community 54 - "Adminpedidos Module"
Cohesion: 0.22
Nodes (18): AdminPedidosPage(), ModalConversaoPedido(), handleAuditarIA(), handleConfirmarComIA(), handleConverterAuto(), handleConverterSimples(), ModalConversaoPedidoProps, analisarComprovante() (+10 more)

### Community 55 - "Utils Exportmetrics"
Cohesion: 0.16
Nodes (15): RFC-4180, ChatModalProps, PendingError, PendingRetry, WELCOME_MESSAGE, EscalonamentoBanner(), EscalonamentoBannerProps, ImageUploader() (+7 more)

### Community 56 - "Orders Module"
Cohesion: 0.16
Nodes (17): PedidosPage(), PedidosPageContent(), calculateFreight(), calculateQuote(), createOrder(), CreateOrderItemPayload, CreateOrderPayload, fetchOrderById() (+9 more)

### Community 57 - "Frontend Package"
Cohesion: 0.10
Nodes (19): name, private, version, jsdom, prettier, @radix-ui/react-dialog, @radix-ui/react-tabs, tailwindcss (+11 more)

### Community 58 - "Products Productlisttable"
Cohesion: 0.17
Nodes (14): AdminProdutosPage(), CATEGORIAS_PADRAO, CategoryFilter(), CategoryFilterProps, ProductFormModalProps, ProductListTable(), ProductListTableProps, StockDetailBadge() (+6 more)

### Community 59 - "Frontend Tsconfig"
Cohesion: 0.11
Nodes (18): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+10 more)

### Community 60 - "Model Catalog Module"
Cohesion: 0.17
Nodes (7): get_characteristics(), get_model_catalog_http_client(), get_ollama_client(), refresh_characteristics(), _to_response(), CharacteristicsRefreshRequest, ModelCharacteristicsResponse

### Community 61 - "Frontend Package"
Cohesion: 0.11
Nodes (18): devDependencies, eslint, eslint-config-next, eslint-config-prettier, jsdom, @playwright/test, prettier, tailwindcss (+10 more)

### Community 62 - "Products Module"
Cohesion: 0.17
Nodes (8): get_public_categorias(), get_public_produto(), get_public_produtos(), _ordenar_estoque_nome_key(), listar_categorias_distintas(), listar_produtos(), _produto_query(), catalogo_produtos()

### Community 63 - "Agendamentos Module"
Cohesion: 0.29
Nodes (13): AdminAgendamentosPage(), formatarDataHora(), AgendamentosPage(), formatarDataHora(), cancelarAgendamento(), criarAgendamentoManual(), fetchAdminAgendamentos(), fetchGoogleCalendarEvents() (+5 more)

### Community 64 - "Mcp Client Google Calendar"
Cohesion: 0.20
Nodes (3): GoogleCalendarConnectionError, GoogleCalendarMCPClient, is_system_event()

### Community 65 - "App Module"
Cohesion: 0.13
Nodes (6): calcular_resumo_cotacao(), calcular_total_pedido(), formatar_itens_carrinho(), formatar_itens_pedido(), formatar_moeda(), run_async()

### Community 66 - "Hooks Usechatstore"
Cohesion: 0.14
Nodes (9): FAQ_ITEMS, MessageBubbleProps, ConversationSnapshot, ChatState, getVisitPrompt(), HumanAttendanceStatus, LEGACY_STORAGE_KEY, USER_STORAGE_PREFIX (+1 more)

### Community 68 - "Logging Config Module"
Cohesion: 0.21
Nodes (5): do_run_migrations(), run_migrations_online(), configure_logging(), ConversationIdFilter, JsonFormatter

### Community 69 - "Specs 2026 09 15"
Cohesion: 0.23
Nodes (9): Qdrant Point Deletion by Document ID, RagDocument Model (PostgreSQL), Design — Registro e Exclusão de Documentos Ingeridos no RAG, EmbedderRegistry Cache, RAG Comparative Search Playground, Design — Perfis de Collection Configuráveis + Playground de Busca, Design — Ingestão de Documentação Restrita ao Canal MCP B2B, CardDocumentoDownload Rich Chat Card (+1 more)

### Community 70 - "Uploads Module"
Cohesion: 0.35
Nodes (4): _get_base_dir(), obter_imagem_produto(), obter_imagem_temporaria(), _validar_nome_arquivo()

### Community 71 - "Plans 2026 09 24"
Cohesion: 0.20
Nodes (10): Injeção de Dados Estruturados de Catálogo no Prompt, Plano de Implementação: Orquestrador MCP B2B em Vendas, Resolução de Produtos em Duas Etapas (SQL + LLM), Pipeline de Extração Multimodal de Catálogo, Plano de Implementação: Gestão de Produtos e Catálogos Multimodais, RAG Visual com Qdrant CLIP, Cliente MCP Streamlit Isolado, Plano de Implementação: Cliente Independente MCP B2B (+2 more)

### Community 72 - "Frontend Package"
Cohesion: 0.18
Nodes (11): scripts, build, dev, format, format:check, lint, start, test (+3 more)

### Community 73 - "Versions 0002 Rag Collections"
Cohesion: 0.20
Nodes (4): downgrade(), upgrade(), upgrade(), upgrade()

### Community 74 - "Services Chat Closure Service"
Cohesion: 0.27
Nodes (3): fechar_conversa(), fechar_conversas_inativas(), inactivity_closure_worker()

### Community 75 - "Specs 2026 10 08"
Cohesion: 0.20
Nodes (10): Painel de Métricas e Ledger Unificado de Uso de IA, Plano do Ledger de Uso de IA: Item A - Fundação, Plano do Ledger de Uso de IA: Item B - Origem Chat, Plano do Ledger de Uso de IA: Item D - Origem Admin, Plano do Ledger de Uso de IA: Item E - Painel, Especificação Arquitetural: Ledger Item B - Origem Chat, Especificação Arquitetural: Ledger Item D - Origem Admin, Semântica de Null (Não Medido) vs Zero (Grátis) (+2 more)

### Community 76 - "Tom Escalonamentos Module"
Cohesion: 0.22
Nodes (3): get_escalonamentos(), EscalonamentoResponse, listar_escalonamentos()

### Community 77 - "Goup Module"
Cohesion: 0.28
Nodes (8): Aplicação Cliente Independente MCP B2B, Dependências PIP do Cliente MCP B2B, Requisito R11: Agendamento via Cliente MCP, Requisito R12: Provedor MCP B2B Corporativo, Proxy Reverso Caddy HTTPS (Porta 8443), Serviço calendar-mcp-server (Porta 8090), Serviço mcp-b2b-server (Porta 8100), Arquitetura Dual MCP

### Community 78 - "Manuais Howto Administrador"
Cohesion: 0.22
Nodes (9): Catálogo B2B e Ferramentas MCP, Dashboards e Gráficos Dinâmicos via Chat, Gestão da Base de Conhecimento e Ingestão RAG, Gestão de Usuários e Permissões, Manual do Administrador do Sistema, Parametrização do Web Crawler, Prompt Text-to-SQL de Gráficos Analíticos (analytics_agent.py), Prompts de Extração de Catálogo Textual e Visual (extractor.py) (+1 more)

### Community 79 - "Manuais Howto Usuario"
Cohesion: 0.22
Nodes (9): Monitor de Tom e Gestão de Sessões, Widget do Assistente Virtual Multimodal, Cards Ricos e Interativos no Chat, Manual do Usuário e Cliente, Interação Multimodal por Texto, Áudio e Foto, Transbordo para Suporte Especializado, Montagem Dinâmica e Sanitização de Prompt (orchestrator.py), Prompt do Monitor de Tom Emocional (tone_monitor.py) (+1 more)

### Community 80 - "Manuais Prompts E Instrucoes Llm"
Cohesion: 0.22
Nodes (9): Mapeamento de Prompts e Instruções LLM, Critérios e Prompt do Classificador de Intenção (classifier.py), Prompts de Auditoria de Comprovantes Financeiros (comprovante_evaluator.py), Prompt de Visão para Identificação de Produtos (image_identification.py), Prompt LLM-as-Judge de Qualidade RAG (eval/rag_quality/run_eval.py), Prompt de Consolidação de Resumo (resumo.py), Prompt de Extração de Intenções de Vendas (sales_catalog.py), Prompt de Extração de Agendamento (scheduling.py) (+1 more)

### Community 81 - "Manuais Strata Manual"
Cohesion: 0.29
Nodes (8): Otimização de Janela de Contexto Headroom, Modos de Operação do Proxy Headroom, Manual do Headroom, Gerenciamento e Parametrização da IA em Runtime, Manual do Strata, Motor de Inferência CUDA Strata MoE, Gerenciamento de Ciclo de Vida de Memória (Lazy / Idle Unload), Modelo Swift 1.5 MoE Quantizado

### Community 82 - "Plans 2026 09 17"
Cohesion: 0.25
Nodes (7): Plano de Implementação: Streaming SSE da Resposta do Chat, Protocolo Unificado de Streaming SSE no Chat, Monitor de Tom e Sentimento em Paralelo, Escalonamento Imediato via SSE e Banco, Plano de Implementação: Monitor de Tom, Download Seguro de Arquivos RAG via Chat, Plano de Implementação: Download Direto de Documentos RAG

### Community 83 - "Specs 2026 09 16"
Cohesion: 0.29
Nodes (6): Background Model Pull with Polling, Design — Gerenciador de Modelos Locais (Ollama), Ollama Model Cold-Start Detection, Streaming (SSE) da Resposta do Chat — Design, ModelCharacteristics Persistent Cache, Design — Características de Modelo (Multimodalidade) no Hover

### Community 84 - "Frontend Package"
Cohesion: 0.25
Nodes (8): dependencies, next, @radix-ui/react-dialog, @radix-ui/react-tabs, react, react-dom, recharts, zustand

### Community 87 - "Chat Module"
Cohesion: 0.29
Nodes (6): _escalar_conversa_em_background(), _persistir_escalonamento_em_background(), event_stream(), event_stream_humano(), _sse(), criar_escalonamento()

### Community 88 - "Mcp Server B2B"
Cohesion: 0.33
Nodes (3): parceiro_atual(), _registrar_chamada(), envolvida()

### Community 90 - "Plans 2026 09 15"
Cohesion: 0.29
Nodes (6): Plano de Implementação: Registro e Exclusão de Documentos RAG, Amarração Dual Postgres e Qdrant por Document ID, Adapter de Coleção Ativa em Runtime, Perfis Imutáveis de Coleções Vetoriais, Plano de Implementação: Perfis de Collection Configuráveis e Playground, Playground Comparativo de Busca RAG

### Community 91 - "Plans 2026 09 19"
Cohesion: 0.33
Nodes (7): Crawler BFS de Páginas Web, Fila de Revisão Humana de Páginas por Confiança, Plano de Implementação: Crawler de Páginas para RAG, Ciclo de Vida de Sessões e Encerramento por Inatividade, Plano de Implementação: Contabilizador de Tokens e Custos, Plano de Implementação: Atendimento Humano e Transbordo Dinâmico, Transbordo Human-in-the-Loop com Lock Atômico

### Community 92 - "Plans 2026 10 04"
Cohesion: 0.29
Nodes (7): Contabilização Segregada de Tokens e Custos de LLM, Contabilização Financeira de Visão Computacional, Plano de Implementação: Custos de Visão Externa, Dashboards Dinâmicos Persistentes com Recharts, Plano de Implementação: Dashboards Dinâmicos Admin, Agente Analítico com Text-to-SQL Seguro, Plano de Implementação: Agente Analítico de Gráficos Dinâmicos com LLM

### Community 93 - "Specs 2026 09 23"
Cohesion: 0.33
Nodes (5): Design — Monitor de Tom (R8), Tom Escalonamentos Model & Persistence, CLIP Visual Catalog in Qdrant, Hybrid PDF/Image Catalog Extraction with SSE, Design — Gestão de Produtos no Admin, Ingestão de Catálogos e RAG Visual CLIP

### Community 94 - "Specs 2026 09 19"
Cohesion: 0.29
Nodes (5): Same-Host BFS Web Crawler, Crawler Human Review Queue for Uncertain Confidence, Crawler de Páginas para o RAG — Design, AI Generation Pausing on Human Takeover, Especificação: Transbordo para Atendimento Humano e Fila de Suporte

### Community 95 - "Specs 2026 09 21"
Cohesion: 0.48
Nodes (5): Booking Slots State Machine & Extraction, Google Calendar MCP Client, Design — Agendamento via MCP Calendar (R11), Agendamento Model & PostgreSQL Synchronization, Design — Gestão de Agendamentos (Fase 7)

### Community 96 - "Specs 2026 10 07"
Cohesion: 0.33
Nodes (5): Multimodal Receipt Evaluation Pipeline, Especificação: Conversão de Reserva em Venda com Comprovação Multimodal, High-Confidence Injection Attempt Logging, Sandwich System Prompt Defense, Especificação: Resiliência a Prompt Injection e Abuso MCP

### Community 97 - "Chat Audiorecorder"
Cohesion: 0.43
Nodes (6): AudioRecorder(), handleClick(), startRecording(), stopRecording(), AudioRecorderProps, blobToBase64()

### Community 98 - "Rag Quality Bateria Perguntas Rag"
Cohesion: 0.33
Nodes (6): Bateria de Perguntas de Ground Truth RAG, Parâmetros Ópticos da Tabela DORI, Tecnologia de Busca por IA InSearch, Benchmark de Qualidade do RAG, Avaliação via LLM-as-Judge, Avaliação 2: Qualidade do RAG

### Community 99 - "Plans 2026 10 07"
Cohesion: 0.33
Nodes (6): Prompt LLM-as-Judge de Resiliência a Injeção (eval/prompt_injection/run_eval.py), Prompts de Sistema e Playbooks por Domínio (playbooks.py), Avaliação Experimental de Resiliência a Injeções, Plano de Implementação de Segurança Contra Prompt Injection e Abuso MCP, Técnica de Sandwich Prompting Anti-Injeção, Validação Robusta de Schemas de Entrada MCP B2B

### Community 100 - "Plans 2026 09 21"
Cohesion: 0.40
Nodes (5): Máquina de Estados de Agendamento por Slots, Cliente MCP Google Calendar Streamable HTTP, Plano de Implementação: Agendamento via MCP Calendar, Plano de Implementação: Gestão Completa de Agendamentos, Sincronização Híbrida de Agendamentos Postgres e Google Calendar

### Community 101 - "Specs 2026 09 24"
Cohesion: 0.47
Nodes (5): SalesCatalogClient (Direct Database Access), Design — Orquestrador como Integrador do MCP B2B em Vendas, B2BMCPClient Python SDK, Streamlit Partner Portal Application, Design — Cliente Independente MCP B2B com Interface Web

### Community 102 - "Specs 2026 10 03"
Cohesion: 0.40
Nodes (5): Segregated Prompt & Completion Cost Calculation, Design — Contabilizador de Tokens, Custos Segregados e Chats Encerrados, AdminChart PostgreSQL Model, Natural Language Chat Chart Synthesis, Design — Dashboards e Gráficos Dinâmicos Gerados via Chat

### Community 103 - "Ui Searchableselect"
Cohesion: 0.33
Nodes (4): SearchableSelect(), SearchableSelectOption, SearchableSelectProps, react-dom

### Community 104 - "G Module"
Cohesion: 0.60
Nodes (5): checar_servico(), falha(), main(), passo(), g.sh script

### Community 105 - "Plans 2026 09 16"
Cohesion: 0.40
Nodes (4): Gerenciador Assíncrono de Modelos Ollama, Plano de Implementação: Gerenciador de Modelos Locais, Cache de Características e Multimodalidade de Modelos, Plano de Implementação: Características de Modelo no Hover

### Community 106 - "Plans 2026 10 08"
Cohesion: 0.40
Nodes (5): Serviço registrar_uso_ia e Gerenciamento de Sessão Global, Conexão dos 10 Pontos de IA da Origem Chat, Instrumentação de Gráficos e Extração no Ledger, Mapeamento das Famílias de IA do Chat, Padrão de Sessão Assíncrona e Fallback Global

### Community 107 - "Frontend Package"
Cohesion: 0.40
Nodes (4): eslintConfig, eslint, eslint-config-next, eslint-config-prettier

### Community 108 - "Frontend .Prettierrc"
Cohesion: 0.40
Nodes (4): printWidth, semi, singleQuote, trailingComma

### Community 113 - "Docs Agentic Workflow"
Cohesion: 0.50
Nodes (4): Ambiente Antigravity IDE, Mecanismo de Artifacts de Revisão, Claude Code CLI, Kiro CLI

### Community 114 - "Docs Frontend"
Cohesion: 0.50
Nodes (4): Requisito R2: Entrada Multimodal de Chat, Widget de Chat Multimodal, Componentes de Cards Ricos no Chat, Streaming Server-Sent Events (SSE)

### Community 115 - "Plans 2026 09 05"
Cohesion: 0.67
Nodes (3): Classificador de Intenção e Complexidade, Orquestrador Híbrido de LLM, Plano de Implementação: Roteador Básico

### Community 116 - "Specs 2026 09 05"
Cohesion: 0.83
Nodes (3): Intent Classifier (Domain & Complexity), LLMClient Protocol, Design — Fase 1: Modelo Local e Roteador Básico

### Community 117 - "Router Intents Readme"
Cohesion: 0.67
Nodes (3): Benchmark de Acurácia do Roteador de Intenções, Matriz de Confusão 4x4 do Roteador, Avaliação 1: Acurácia do Roteador

### Community 123 - "Plans 2026 10 08"
Cohesion: 0.67
Nodes (3): Endpoint GET /api/admin/metrics/ai-usage, Reconstrução do Painel /admin/metricas no Frontend, Serviço de Roll-up Puro ai_usage_report

## Knowledge Gaps
- **103 isolated node(s):** `assistente-multimodal-backend`, `cliente-mcp-b2b`, `RFC-4180`, `@tailwindcss/postcss`, `@testing-library/jest-dom` (+98 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 965 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **46 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `QdrantRAGClient` connect `Rag Qdrant Client` to `Rag Image Search`, `Mcp B2B Module`, `Rag Quality Run Eval`, `Services Ingestion Metrics`, `Rag Dependencies Module`, `Router Openrouter Client`, `Rag Module`, `Crawler Module`, `Rag Module`, `Rag Collections Registry`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Are the 30 inferred relationships involving `QdrantRAGClient` (e.g. with `_FixedCollectionRagClient` and `main()`) actually correct?**
  _`QdrantRAGClient` has 30 INFERRED edges - model-reasoned connections that need verification._
- **What connects `assistente-multimodal-backend`, `cliente-mcp-b2b`, `RFC-4180` to the rest of the system?**
  _103 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Rag Image Search` be split into smaller, more focused modules?**
  _Cohesion score 0.05369369369369369 - nodes in this community are weakly interconnected._
- **Why does `OllamaClient` connect `Router Ollama Client` to `Rag Quality Run Eval`, `Services Ingestion Metrics`, `Router Openrouter Client`, `Rag Dependencies Module`, `Router Ollama Client`, `Router Ollama Client`, `Local Models Module`, `Model Catalog Module`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Should `Services Comprovante Evaluator` be split into smaller, more focused modules?**
  _Cohesion score 0.05136986301369863 - nodes in this community are weakly interconnected._
- **Why does `TextEmbedder` connect `Rag Qdrant Client` to `Crawler Module`, `Rag Dependencies Module`, `Services Comprovante Evaluator`, `Services Ingestion Metrics`?**
  _High betweenness centrality (0.015) - this node is a cross-community bridge._