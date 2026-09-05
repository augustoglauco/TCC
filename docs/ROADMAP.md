# Roadmap de Implementação

Checklist de tarefas do MVP, organizado por fases com dependências (sem
prazos fixos — a ordem é lógica, não temporal). Cada item referencia o
requisito funcional (`Rn`, ver `docs/ARCHITECTURE.md`, Seção 3). Marque
`- [x]` ao concluir e mantenha os comentários `# MVP: ...` combinados no
código (ver `CLAUDE.md`).

Convenção de status: `- [ ]` pendente · `- [~]` em andamento · `- [x]` feito.

## Fase 0 — Fundamentos e Infraestrutura

- [ ] Provisionar ambiente com GPU (mínimo 16GB de VRAM) e stack de
      inferência local (Ollama ou vLLM)
- [x] Criar estrutura inicial do repositório conforme `docs/CONVENTIONS.md`
      (monorepo `backend/` + `frontend/`, pastas de módulo vazias)
- [x] Configurar `.env.example` e carregamento de configuração
      (pydantic-settings ou equivalente) — `backend/src/app/config.py`
- [x] Configurar logging estruturado com ID de conversa (pré-requisito de R9)
      — `backend/src/app/logging_config.py` (contextvar + formatter JSON)
- [x] Configurar lint/format (ruff/black) e pipeline de testes (pytest) —
      `backend/pyproject.toml` ([tool.ruff], [tool.pytest.ini_options])

## Fase 1 — Modelo Local e Roteador Básico (R1, R3)

- [ ] Subir modelo open-source quantizado 7B–8B (ex.: Llama 3.1 8B, Qwen2.5
      7B) via Ollama/vLLM
- [ ] Implementar avaliação comparativa simples entre 2 modelos candidatos
      (custo/qualidade) — insumo para a Fase 8
- [ ] Implementar classificador de intenção simples (regras + LLM) para
      decidir entre modelo local, modelo externo e RAG
- [ ] Adicionar log básico de decisões do roteador (intenção escolhida,
      custo/latência estimados)

## Fase 2 — Entrada Multimodal e RAG Textual (R2, R4, R5)

- [ ] Implementar entrada de texto e áudio no chat
- [ ] Implementar STT (áudio → texto) com suporte a pelo menos dois formatos
      comuns (ex.: wav e mp3)
- [ ] Implementar ingestão de PDFs/textos e busca vetorial (RAG)
- [ ] Implementar conector de leitura a um banco de dados relacional
      (`# MVP: somente leitura, sem sincronização incremental`)
- [ ] Implementar crawler restrito a um conjunto pré-definido de páginas
      (até ~5), sem agendamento (`# MVP: escopo restrito`)

## Fase 3 — RAG Multimodal, Tratamento de Imagem e Domínios (R4, R6, R7)

- [ ] Implementar entrada de imagem no chat (fluxo básico)
- [ ] Implementar OCR para imagens dirigidas (ex.: comprovante solicitado
      pelo sistema)
- [ ] Implementar busca multimodal via embeddings (ex.: CLIP) sobre um
      catálogo de imagens ampliado (`# MVP: catálogo ampliado, não completo`)
- [ ] Implementar reranking básico dos resultados de busca por imagem
- [ ] Implementar fallback para busca externa de imagem quando não encontrado
      no catálogo interno
- [ ] Separar fluxo/prompts por domínio: Vendas, Suporte Técnico, Atendimento
      ao Usuário, Agendamento de Visita
- [ ] Escrever playbooks iniciais de atendimento para Suporte Técnico e
      Atendimento ao Usuário

## Fase 4 — Agendamento via MCP e Monitor de Tom (R8, R11)

- [ ] Implementar cliente MCP para o Google Calendar
- [ ] Implementar nova intenção de agendamento no roteador (coleta de
      data/hora e dados básicos na conversa)
- [ ] Implementar confirmação automática por e-mail após criar o evento
- [ ] Implementar tratamento de erro claro para falha de conexão/autenticação
      do MCP do Google Calendar (sugerir nova tentativa ou transferir para
      atendente)
- [ ] Implementar classificador leve de sentimento/urgência (heurística +
      LLM leve)
- [ ] Implementar alerta e transferência simulada para atendente humano + log
      dos casos escalonados

## Fase 5 — MCP B2B Provido pela Empresa (R12)

- [ ] Modelar o backend único de dados (catálogo, estoque, preços, manuais)
      reaproveitado tanto pelo RAG quanto pelo servidor MCP
- [ ] Implementar servidor MCP interno expondo os 4 recursos de leitura
      (catálogo, estoque, tabela de preços, manuais)
- [ ] Implementar as 4 ferramentas do MCP B2B: validação de compatibilidade,
      consulta de frete e prazos, cotação automática, reserva/pedido
- [ ] Integrar o Roteador/Orquestrador como "mais um integrador" do MCP B2B
      para intenções de Vendas (cotação, compatibilidade, estoque)
- [ ] Garantir e documentar que autenticação por parceiro e exposição
      pública **não** fazem parte do MVP
      (`# MVP: uso interno, sem autenticação por parceiro`)

## Fase 6 — Memória e Classificação do Usuário (R9, R10)

- [ ] Implementar persistência da conversa por ID único
- [ ] Implementar resumo automático periódico da conversa (não só ao final)
- [ ] Implementar heurística inicial de classificação Cliente/Lead/Esporádico
      com base em histórico de compras/perguntas

## Fase 7 — Frontend: Site Institucional, Produtos e Pedidos (ver `docs/FRONTEND.md`)

- [ ] Criar o projeto Next.js (TypeScript) em `frontend/` conforme
      `docs/FRONTEND.md` §5
- [ ] Implementar Home institucional e Contato
- [ ] Implementar listagem e detalhe de produtos (`/produtos`), consumindo a
      API do backend
- [ ] Implementar autenticação simplificada (login/cadastro) e página de
      perfil
- [ ] Implementar fluxo de pedidos (carrinho/checkout) e histórico de pedidos
- [ ] Implementar página de Suporte/Central de Ajuda (esse conteúdo também é
      alvo do crawler do RAG, R4)
- [ ] Implementar página de Agendamentos (leitura dos agendamentos criados
      via chat, R11)

## Fase 8 — Frontend: Widget de Chat (ver `docs/FRONTEND.md` §3)

- [ ] Implementar botão flutuante + painel de chat (`ChatWidget`,
      `ChatPanel`), presente em todas as rotas
- [ ] Implementar envio de texto e exibição do streaming de resposta (SSE)
- [ ] Implementar upload de imagem (`ImageUploader`) e gravação de áudio
      (`AudioRecorder`)
- [ ] Implementar persistência do ID de conversa (retomar conversa entre
      sessões/páginas, R9)
- [ ] Implementar cards ricos: produto, confirmação de agendamento,
      cotação/reserva
- [ ] Implementar indicador de domínio identificado pelo roteador
      (opcional, útil para a demonstração ao orientador)
- [ ] Implementar banner de transferência para atendente humano (monitor de
      tom, R8)
- [ ] Implementar estados de erro (ex.: falha do MCP do Google Calendar) com
      opção de tentar novamente

## Fase 9 — Integração Ponta a Ponta e Robustez

- [ ] Testes de integração cobrindo os quatro domínios de atendimento
      (backend)
- [ ] Testes E2E do frontend cobrindo os fluxos críticos: chat (texto,
      imagem, áudio), pedido, login (ver `docs/FRONTEND.md` §6)
- [ ] Ajustes de robustez nas frentes mais custosas: RAG multimodal e monitor
      de tom
- [ ] Revisão de tratamento de erro para dependências externas

## Fase 10 — Avaliação Experimental (ver `docs/EVALUATION.md`)

- [ ] Montar conjunto de teste rotulado para acurácia do roteador + matriz de
      confusão entre os quatro domínios
- [ ] Montar conjunto de perguntas de referência para qualidade do RAG
      (avaliação manual em escala 1–5 + LLM-as-judge)
- [ ] Medir latência (média e p95) do modelo local x modelo externo para o
      mesmo conjunto de prompts
- [ ] Consolidar os resultados das três avaliações em um relatório curto para
      apresentação ao orientador

## Fase 11 — Preparação da Entrega

- [ ] Revisar todos os 12 requisitos funcionais contra o que foi de fato
      implementado (checklist final)
- [ ] Atualizar `docs/ARCHITECTURE.md`, `docs/FRONTEND.md` e este roadmap com
      o estado final do protótipo
- [ ] Preparar demonstração cobrindo os quatro domínios + agendamento + MCP
      B2B, usando a interface completa (site + widget de chat)

## Explicitamente fora do MVP (não implementar sem decisão registrada em `docs/ARCHITECTURE.md`)

- Integração com CRM.
- Fine-tuning de modelo e otimização de latência em produção.
- Exposição pública do MCP B2B a parceiros externos reais (autenticação,
  OAuth, rate limiting, auditoria completa).
- Integração real com fila de atendimento humano e sistema de ticketing.
- Reagendamento/cancelamento de visita e checagem de disponibilidade em
  múltiplas agendas.
