# Frontend — Interface do Site e do Chat

> Este documento cobre a interface que sustenta o site (institucional,
> produtos, pedidos) e hospeda o chat — a peça central do projeto (ver
> `docs/ARCHITECTURE.md`, Seção 1). O frontend é **cliente da API REST do
> backend**; ele nunca fala diretamente com os MCPs (Google Calendar e MCP
> B2B) — esses protocolos existem para o backend e para IAs de parceiros
> integradores, não para o próprio site (ver `docs/ARCHITECTURE.md`, Seção 6).

## 1. Stack

- **Next.js (App Router) + TypeScript.**
- **Tailwind CSS** para estilo — produtividade alta para um protótipo de TCC
  com uma pessoa só no frontend.
- **Dados de servidor** (produtos, pedidos, histórico) por `fetch` direto nos
  clientes de `lib/api/` e hooks próprios; **nenhuma biblioteca de cache**
  (React Query/SWR) foi adotada — decisão de simplicidade do MVP.
- **Zustand 5** para o estado do widget de chat (aberto/fechado, mensagens em
  andamento, `conversation_id`) e a autenticação — não para dados que já vêm
  do backend.
- **Recharts** para os gráficos (`/avaliacao`, `/admin/dashboards`, cards de
  gráfico no chat) e **Radix UI** (dialog, tabs) para os componentes
  acessíveis.
- **Server-Sent Events (SSE)** para streaming da resposta do chat — mais
  simples de implementar com FastAPI do que WebSocket bidirecional; suficiente
  porque o cliente só precisa *receber* o streaming, o envio é uma requisição
  HTTP normal.

Esta stack é o ponto de partida; qualquer troca (ex.: SSE → WebSocket, se o
chat evoluir para notificações do servidor sem o cliente perguntar) deve ser
registrada aqui com o motivo.

## 2. Seções/páginas

| Seção | Rota (sugestão) | Propósito | Requer login |
| --- | --- | --- | --- |
| Home / Institucional | `/` | Apresentação da empresa, chamada para o chat, destaques de produtos/serviços | Não |
| Produtos (listagem) | `/produtos` | Catálogo com busca e filtro — mesma base de dados usada pelo RAG e pelo MCP B2B (`docs/ARCHITECTURE.md` §6) | Não |
| Produto (detalhe) | `/produtos/[id]` | Especificações, preço, disponibilidade; ponto de entrada para "perguntar ao chat sobre este produto" | Não |
| Login | `/conta/login` | Autenticação simplificada mock (contas simuladas ou e-mail próprio, senha mock `12345`/`admin123`) — decisão em `docs/ARCHITECTURE.md` §5 | Não |
| Cadastro | `/conta/cadastro` | Autoatendimento de novo cadastro (`POST /api/auth/register`); perfil Admin só é aceito com `requester_email` de outro Admin (ou a conta demo `admin@example.com`) — decisão em `docs/ARCHITECTURE.md` §5 (2026-09-29) | Não |
| Perfil | `/conta/perfil` | Detalhes de relacionamento (perfil Cliente/Lead/Esporádico/Admin) e atalho para o histórico de pedidos | Sim |
| Pedidos (carrinho/checkout) | `/pedidos` | Fluxo de compra — pode ser iniciado pelo site ou por uma cotação/reserva feita via chat (Vendas + MCP B2B) | Sim |
| Histórico de pedidos | `/pedidos/historico` | Status e histórico — usa o mesmo ID de cliente que alimenta a classificação Cliente/Lead/Esporádico (R10). Com `?email=` na URL e o usuário logado sendo Admin, mostra o histórico daquele e-mail em vez do próprio ("inspeção administrativa", decisão de 2026-09-29) | Sim |
| Agendamentos | `/agendamentos` | Visualizar visitas agendadas do cliente autenticado, desmarcar visitas confirmadas com confirmação (sincronizado com Google Calendar) e CTA para novo agendamento via chat (R11) | Sim |
| Admin — Agendamentos | `/admin/agendamentos` | Painel administrativo com abas (sistema por usuário com busca e filtros vs consulta à agenda corporativa do Google Calendar em tempo real via MCP) e modal para agendamento manual com validação de conflitos — duração da visita configurável (`duracao_minutos`, decisão de 2026-09-29) | Sim (`admin`) |
| Admin — Usuários | `/admin/usuarios` | Lista/filtra os usuários cadastrados (nome/e-mail/perfil), com contagem de clientes x admins e link "Ver Pedidos" por usuário (`/pedidos/historico?email=...`) — decisão em `docs/ARCHITECTURE.md` §5 (2026-09-29) | Sim (`admin`) |
| Resultados da Avaliação | `/avaliacao` | Gráficos públicos das avaliações da Fase 10 (roteador, RAG, antes × depois da configuração do RAG (Etapa 7), perguntas sem resposta no corpus, grade de chunking da Etapa 3, injeção de prompt e comparativo de modelos), só agregados com IC de Wilson; cada gráfico/tabela tem um badge “i” com balão explicativo ao passar o mouse ou focar; ao lado dele, um badge “+” abre um modal com a explicação, a tabela de dados que originou o gráfico, o motivo, a relevância, os cuidados de leitura e como o projeto chegou àquela conclusão (textos em `app/avaliacao/detalhes.ts`); vazio até as rodadas oficiais gerarem `results.json` (Seção 4) | Não |
| Suporte / Central de Ajuda | `/suporte` | FAQ e documentação de produto — é justamente o conteúdo que o crawler (R4) e o RAG de Suporte/Atendimento (R7) devem indexar | Não |
| Contato | `/contato` | Dados institucionais, formas de contato alternativas ao chat | Não |
| **Chat** | widget global (todas as rotas) | Ponto de entrada único para os quatro domínios de atendimento — ver Seção 3 | Não (funciona anônimo; melhora com login) |
| Admin — Ingestão de documentos | `/admin/ingestao` | Página interna (menu ⚙️) para upload de PDF/texto e ingestão no RAG (R4). Possui painel de collections ativas por finalidade (`Chat`, `MCP B2B`, `Admin`), abas de filtro por finalidade na tabela, botões compactos com ícones SVG, cards flutuantes no hover com contagem de arquivos e métricas técnicas, e playground de busca comparativa restrito ao mesmo purpose | Sim (`admin`) |
| Admin — Catálogo de Produtos | `/admin/produtos` | Página interna (menu ⚙️) para cadastro e gestão de produtos, preços de revendedor e venda agrupados, estoque total consolidado com tooltip detalhado por Centro de Distribuição (CD), fotos vetorizadas no CLIP, e assistente Human-in-the-Loop de importação de catálogos | Sim (`admin`) |
| Admin — Modelos locais (Ollama) | `/admin/modelos` | Página interna (menu ⚙️) para listar/ativar em runtime/baixar modelos locais de chat, visualizar características multimodais dos modelos no hover (`ModelCharacteristicsPanel`), gerenciar a residência na VRAM e latência (seletor `keep_alive`, warmup automático na inicialização, monitor em tempo real da VRAM em GB, botões para carregar e liberar VRAM), e ajustar parâmetros de execução com persistência permanente no PostgreSQL | Sim (`admin`) |
| Admin — Métricas & Custos de IA | `/admin/metricas` | Painel de uso de IA sobre o ledger unificado `ai_usage_events` (item E, 2026-10-08), com cinco seções — Por Origem, Por Ambiente, Por Modelo, Por Operação e Detalhamento Diário — mais o KPI de chats encerrados; distingue custo `null` ("não medido", `—`) de `0.0` ("medido e grátis", `$0.0000`) | Sim (`admin`) |
| Admin — Mensagens de Agentes | `/admin/mensagens` | Caixa de entrada das mensagens que agentes autônomos enviam ao administrador (R13; hoje o Agente de Estoque, que avisa risco de falta nos próximos 10 dias). Lista com severidade, agente, texto e status do e-mail; filtro "só não lidas", marcar uma/todas como lidas. Link no menu ⚙️ | Sim (`admin`) |
| Admin — Central de Atendimento | `/admin/atendimento` | Página interna (menu ⚙️): fila de espera do atendimento humano, assumir chat (claim atômico), abas de chats ativos e envio de mensagens ao cliente (`/api/admin/atendimento/*`) | Sim (Admin) |
| Admin — Pedidos & Conversão | `/admin/pedidos` | Página interna (menu ⚙️): KPIs, filtros de status e modal de conversão de reserva em venda por comprovante (`/api/admin/pedidos/*`) | Sim (Admin) |
| Admin — Ferramentas de Código | `/admin/ferramentas` | Página interna (menu ⚙️) que reúne as três ferramentas de inteligência de código do projeto — Graphify (artefato estático `graphify-out/graph.html`, servido pelo backend), Repowise (UI em `localhost:3012`, pública na `3002` sem senha) e GitNexus (UI em `localhost:4757`, pública na `4747` sem senha; de fora da rede a tela troca `localhost` pelo host da página e a porta interna pela pública, e acrescenta `?server=<origem>` à URL do iframe, porque a SPA do GitNexus chama o backend dela numa URL fixa de build — `http://localhost:4747`, o `localhost` do navegador — e sem isso fica parada em "Start your local server") — com LED de estado em cada cartão (verde piscando suave = no ar, vermelho = fora do ar), botão de atualizar por ferramenta (o do GitNexus só habilita com o servidor no ar; o do Graphify fica sempre ativo, pois é ele que gera o artefato), iframe embutido e o comando para gerar/subir a que estiver indisponível. `# MVP: apoio ao desenvolvimento, fora do escopo do assistente — ver docs/ROADMAP.md, "Extra fora do MVP — Painel de Ferramentas de Código"` | Sim (`admin`) |
| Admin — Dashboards & Gráficos | `/admin/dashboards` | Galeria permanente de gráficos e dashboards analíticos gerados interativamente via chat ou gerenciados pelo administrador, com persistência no PostgreSQL, suporte a Recharts, refresh individual e em lote, fixação e edição | Sim (`admin`) |
| Admin — Preparação da Avaliação | `/admin/datasets` | Painel de apoio à Fase 10 (pedido pelo dono em 2026-10-16): progresso dos cinco conjuntos da Estratégia A em cartões com duas barras (gerado x meta e revisado x gerado — uma só esconderia que "100% revisado" pode ser 18 de 180), fila de revisão item a item com os campos já editáveis e atalhos `A` (aprovar) / `D` (descartar), e disparo das tarefas longas (geração dos rascunhos de roteador, RAG docs, banco e injeção; ingestão do corpus, triagem, rodada completa) com log acompanhado por polling incremental. Editar qualquer campo transforma a decisão em `corrigido` e envia só o que mudou; os conjuntos de imagem e banco aparecem como `automático`, sem fila, porque o gabarito é exato por construção (imagem lê `imagens/dataset.json`, meta 72: 23 positivas + 48 negativas + 1 comprovante). `// MVP: tela de apoio à condução do experimento, fora do escopo do MVP do assistente — ver docs/ROADMAP.md, "Extra fora do MVP — Painel de Preparação da Avaliação"` | Sim (`admin`) |

Todas as páginas compartilham `layout.tsx`, que inclui o widget de chat — ele
deve estar disponível em qualquer rota, inclusive durante o checkout.

## 3. Widget de chat (peça central da interface)

**Comportamento geral:** botão flutuante no canto inferior direito, presente
em todas as páginas; ao clicar, abre um modal central (`ChatModal.tsx`,
sobre `components/ui/Modal.tsx`, Radix Dialog), mesmo comportamento em
mobile e desktop. O ID de conversa (R9/R10) é mantido em `sessionStorage`
para visitantes não autenticados (mantendo o contexto apenas durante a
sessão de navegação na aba) ou persistido no `localStorage` vinculado à conta
do usuário logado (`tcc_chat_user_conversation_id_{email}`). Com a conversa
vazia, o modal mostra uma bolha de boas-vindas do assistente
(`WELCOME_MESSAGE`, definida em `ChatMensagens.tsx` e reexportada por `ChatModal.tsx`): apresenta o que o assistente faz e
convida, de forma opcional, a informar o e-mail ou fazer login para
identificar o cadastro e as compras (R10). A bolha é só de
interface: não entra no store nem no banco e some com a primeira mensagem ou
com o histórico recarregado.

**Entrada multimodal (R2):**
- Campo de texto padrão.
- Botão de upload/drag-and-drop de imagem (uso espontâneo ou dirigido, ver
  `docs/ARCHITECTURE.md` §4) — preview da imagem antes de enviar.
- Botão de gravação de áudio (**toggle** — decisão fechada, ver
  `AudioRecorder` mais abaixo) com indicador visual de gravação — o áudio é
  enviado ao backend para STT (R5); exibir o texto transcrito na bolha do
  usuário assim que disponível.

**Exibição de mensagens:**
- Bolhas de texto padrão para usuário e assistente.
- Indicador de "digitando"/streaming enquanto a resposta chega via SSE: se o
  backend emitir o evento `status` ("carregando_modelo", ver Seção 4), a
  bolha do assistente é criada de imediato com um texto temporário ("🤖
  Aguarde, consultando documentos internos..."), substituído pelo texto real
  assim que o primeiro evento `token` chega; a partir daí a bolha é
  preenchida incrementalmente (token a token) conforme os eventos chegam,
  produzindo o efeito de "digitando" — ver `ChatModal.tsx`.
- **Cards ricos** para respostas estruturadas, em vez de só texto (Fase 8,
  implementado em 2026-09-29 — decisão em `docs/ARCHITECTURE.md` §5) —
  vêm no campo opcional `card` do evento `done` (ver §4), renderizados por
  `components/chat/cards/ChatCard.tsx` (dispatcher por `card.tipo`) logo
  abaixo do texto da resposta em `MessageBubble.tsx`:
  - `ProductCard` (`card.tipo === "produto"`): imagem, nome, preço, badge de
    estoque, link para `/produtos/[id]` — produto único resolvido em Vendas
    sem quantidade informada.
  - `AppointmentCard` (`card.tipo === "agendamento"`): data/hora formatada e
    link para `/agendamentos` — só aparece quando a visita é confirmada de
    verdade (R11). `# MVP`: o card não expõe o link do evento no Google
    Calendar ao cliente (pedido explícito, 2026-09-29) — `google_event_link`
    continua no contrato de dados (`card.google_event_link`), usado só pelo
    painel `/admin/agendamentos`.
  - `QuoteCard` (`card.tipo === "cotacao"`): produto, quantidade, preço
    unitário, percentual de desconto e subtotal — mesmo produto do
    `ProductCard`, mas com quantidade informada pelo cliente (R12).
  - `ChatChartCard` (`card.tipo === "grafico"`): gráfico analítico dinâmico
    gerado pelo assistente via Recharts (barras, linhas, pizza, área, donut),
    com persistência permanente na tabela `admin_charts` e link direto para
    o painel `/admin/dashboards`.
  - `DocumentDownloadCard` (`card.tipo === "documento_download"`, 2026-10-05):
    nome do arquivo, badge de relevância (score arredondado em %) e tamanho
    formatado (KB/MB), com link `<a download>` apontando para
    `GET /api/rag/documents/{id}/download` (resolvido via `getApiBaseUrl()`
    + `card.download_url`). Emitido pelo orquestrador quando a busca
    vetorial do RAG retorna score >= 0.65 — **sempre** para documentos de
    coleção `purpose="chat"`, então o link nunca exige token (endpoint
    público só para essa finalidade; `purpose="admin"` exige token, mas o
    backend nunca emite esse card para esses documentos).
  - **Fechar o modal ao navegar** (2026-10-14): o `ChatWidget` fica no layout
    raiz, então o `isOpen` do `useChatStore` sobrevive à navegação do
    `next/link` e o modal continuaria cobrindo a página de destino. Todo card
    com link interno (`ProductCard`, `QuoteCard`, `AppointmentCard` e
    `ChatChartCard`) chama `useChatStore.getState().close()` no `onClick` do
    `Link` — é por isso que esses cards são `"use client"`. O
    `DocumentDownloadCard` é a exceção proposital: baixa um arquivo
    (`<a download>`) sem navegar, então o chat fica aberto.
  `# MVP`: consulta genérica por categoria ou catálogo completo (que lista
  vários produtos, não um item único) ainda não tem card próprio — continua
  só em texto.
- **Foco da caixa de mensagem** (2026-10-14, pedido do usuário): o critério
  é *devolver* foco (o usuário estava compondo e uma ação o tirou dele) x
  *tomar* foco (o usuário não pediu para digitar). Devolver vale em qualquer
  dispositivo; tomar só em ponteiro preciso, porque em touch abrir o teclado
  virtual come metade da viewport e esconde a última mensagem — é a prática
  dos chats de mercado (WhatsApp Web, Telegram, Slack, Intercom). A checagem é
  por capability query (`temPonteiroPreciso()` → `matchMedia("(pointer: fine)")`),
  nunca por user-agent, e sem suporte a `matchMedia` assume desktop. Todos os
  `focus()` usam `{ preventScroll: true }` para não desfazer o scroll da
  conversa. Três caminhos:
  - **envio, fim da gravação de áudio e erro de envio** — o `<input>` fica
    `disabled` enquanto `controlsDisabled` (`isSending || isRecording`) está
    ligado, então o foco só pode voltar quando ele reabre: efeito com deps
    `[open, controlsDisabled]`. Incondicional (o teclado já está aberto);
  - **ações dentro da composição** (remover a imagem pendente, selecionar
    imagem) — `focarCaixaMensagem()`, incondicional, pelo mesmo motivo;
  - **ações secundárias** (exportar CSV/JSON, fechar o banner de
    escalonamento, "Tentar novamente", falar com atendente, encerrar
    atendimento, limpar histórico) e **a abertura do chat** —
    `focarCaixaMensagemSePonteiroPreciso()`, que não faz nada em touch.
  Os dois helpers focam dentro de um `requestAnimationFrame`, para esperar o
  re-render que a ação disparou. Testes: o `jsdom` não implementa
  `matchMedia`, então os testes de desktop não precisam de stub e só os de
  touch usam o helper `mockPonteiro("coarse")`.
- **Scroll para a última mensagem ao abrir o chat** (2026-10-14, pedido do
  usuário): o efeito de scroll suave (`behavior: "smooth"`, disparado por
  `messages`/`error`) não resolve a abertura — ele roda no mesmo commit em que
  o modal monta, quando a lista ainda não tem altura, e a animação é
  descartada, deixando a conversa no topo. Um efeito próprio com dep `[open]`
  faz o salto instantâneo (`behavior: "auto"`, `block: "end"`) dentro de um
  `requestAnimationFrame` duplo, já com a lista medida. O salto vale em
  qualquer dispositivo; só o foco que o acompanha é condicionado ao ponteiro.
  Atenção ao mexer nisso: o teste "não força scroll a cada poll de 4s"
  (`tests/components/ChatModal.test.tsx`) mede a linha de base **depois** de
  deixar esse salto único acontecer; o que ele protege é o scroll repetido do
  polling de atendimento humano, não o da abertura.
- **Indicador de domínio** (opcional, mas recomendado para a demonstração do
  TCC): um rótulo discreto mostrando qual domínio o roteador identificou
  (Vendas / Suporte Técnico / Atendimento ao Usuário / Agendamento) — ajuda a
  tornar visível o comportamento do Roteador/Orquestrador na apresentação.
- **Indicador de origem do modelo:** bolhas de resposta do assistente cujo
  `backend_used` retornado pela API é `"externo"` são destacadas em vermelho clarinho
  (`bg-red-50`/`border-red-200/80`, ver `components/chat/MessageBubble.tsx`) —
  torna visível quando o roteador decidiu usar o modelo externo em vez do
  local, útil para a demonstração do TCC (R1).
- **Banner de transferência humana** quando o monitor de tom aciona a
  escalada (R8): implementado em `components/chat/EscalonamentoBanner.tsx`
  e integrado ao topo da listagem de mensagens em `ChatModal.tsx`, como
  elemento flutuante (`sticky top-0 z-20`, 2026-10-13): fica visível sobre
  as mensagens mesmo em conversas longas com scroll. Consome o
  evento SSE `escalonamento` (`lib/api/chat.ts`, callback `onEscalonamento`)
  com mensagem contextualizada de acordo com o motivo detectado (`urgencia`:
  "Identificamos urgência na sua solicitação. Um atendente humano foi notificado...";
  `insatisfacao`: "Percebemos sua insatisfação e lamentamos o transtorno..."),
  badge explicativo "Alerta de Tom" e botão de fechar (`aria-label="Fechar aviso de atendimento humano"`).
  O backend registra o caso em `tom_escalonamentos` e coloca a conversa na fila de
  atendimento humano (Central de Atendimento, `/admin/atendimento`); a UI reage ao
  evento informando o usuário com transparência.

**Estados do widget:** ocioso · enviando · aguardando streaming · gravando
áudio · processando imagem · transferido para atendente · erro (ex.: falha
do MCP do Google Calendar — mostrar mensagem de erro com opção de tentar
novamente, conforme risco documentado em `docs/ARCHITECTURE.md` §7).

**Anônimo x logado:** o chat funciona sem login (cobre lead e cliente
esporádico, R10); ao estar logado, o backend já recebe o ID do usuário e
pode ligar a conversa ao histórico de pedidos — não é responsabilidade do
frontend decidir a classificação, apenas repassar o contexto de sessão
disponível.

## 4. Integração com o backend (contrato de API)

O frontend fala apenas com a API REST do próprio backend (nunca diretamente
com os MCPs). A tabela abaixo descreve os endpoints **já implementados** em
`backend/src/app/api/*.py` (os schemas Pydantic estão em
`backend/src/app/models/`); ao mudar uma rota ou um campo, atualize esta
seção na mesma tarefa:

**Resolução da URL base do backend (`frontend/lib/api/apiBaseUrl.ts`,
2026-09-24):** cada módulo de `frontend/lib/api/*.ts` obtém a URL base via
`getApiBaseUrl()` em vez de hardcodear `http://localhost:8000` — se
`NEXT_PUBLIC_API_BASE_URL` estiver definida (sem barra final, que duplicaria
no path), usa esse valor; senão deriva `"<protocolo><hostname>:8000"` a
partir da própria página (`window.location`) em runtime no navegador. Isso
permite acessar o frontend por `localhost`, IP da LAN ou o domínio DuckDNS
(mesmas origens de `allowedDevOrigins` em `frontend/next.config.ts`) sem
reconfigurar nada — `localhost` hardcoded apontaria para o próprio
dispositivo do usuário, não para a máquina de dev, quando acessado de fora
dela (bug de acesso mobile, commit `7d8426b`).

| Endpoint | Uso |
| --- | --- |
| `POST /api/chat/messages` | Envia mensagem (texto e/ou imagem e/ou áudio) de uma conversa; resposta é o próprio stream Server-Sent Events (SSE) da geração — não há endpoint `GET` separado |
| `GET /api/chat/conversations/{id}` | Recupera histórico/resumo/status da conversa (R9, Fase 6): `{conversation_id, status, resumo, mensagens: [{papel: "cliente"\|"assistente"\|"atendente", texto, dominio, criada_em, atendente_nome, metricas}]}` — `metricas` é o evento `done` da resposta (só nas do assistente; `null` nas gravadas antes da migração `0012`), convertido por `metricsFromDone` (`lib/utils/chatMetrics.ts`, o mesmo usado ao receber o `done`) para o painel ⚙️ reaparecer igual; `atendente_nome` só preenchido em `papel="atendente"`; mais antiga primeiro (até 50); `404` se a conversa não existe, `503` se o banco está fora do ar. Dois consumidores em `lib/api/chat.ts`: `fetchConversationHistory` (usado pelo `ChatWidget` ao montar — carrega as mensagens só se a tela estiver vazia; qualquer falha deixa o chat vazio, sem erro) e `fetchConversationSnapshot` (histórico + `status` juntos — achado de 2026-10-06, Fase 4: sem WebSocket/SSE do servidor para empurrar uma mensagem do atendente humano ao cliente, o `ChatModal` (via o hook `useConversaHumanaPolling`) usa esta função para repollar a cada 4s e substituir as mensagens em tela enquanto `status` for `aguardando_humano`/`em_atendimento_humano`; para sozinho quando o atendente encerra/devolve a conversa) |
| `POST /api/chat/conversations/{id}/close` | Encerra a conversa (R9/métricas). Corpo opcional `{motivo}` (default `manual_usuario`; também `manual_admin`, `inatividade`). Resposta `{conversation_id, status, encerrada_em, motivo_encerramento}`; `404` se a conversa não existe, `503` se o banco está fora do ar. Cliente: `closeConversation` em `lib/api/chat.ts` |
| `DELETE /api/chat/conversations/{id}` | Botão "limpar conversa" do `ChatModal` (`deleteConversation` em `lib/api/chat.ts`): apaga as mensagens e zera resumo e perfil da conversa (o e-mail é mantido); `204`, `404` se a conversa não existe, `503` se o banco está fora do ar |
| `GET /api/products` | Catálogo público de produtos (mesma base do RAG/MCP B2B), usado por `/produtos` (`lib/api/products.ts`). Query: `termo` (nome, descrição ou especificações), `categoria`, `limit` (1–100, default 12), `offset`. Resposta `{items: ProdutoOut[], total, limit, offset}`, com os produtos com estoque primeiro e depois por nome |
| `GET /api/products/categorias` | Lista as categorias distintas do catálogo (filtro da página `/produtos`) |
| `GET /api/products/{id}` | Um produto (`ProdutoOut`, com imagens); `404` se não existe. Consumido pela página de detalhe `/produtos/[id]` (`lib/api/products.ts`, `fetchProductById`) |
| `GET /api/admin/produtos` | Lista para a tela `/admin/produtos` (query `termo`, `categoria`, `limit` 1–200, default 100, `offset`), mesma resposta paginada de `GET /api/products`, sem a ordenação por estoque — fora do MVP original, ver `docs/ARCHITECTURE.md` §5 (Gestão de Produtos) |
| `POST /api/admin/produtos`, `PUT /api/admin/produtos/{id}` — campo `dias_alerta_estoque` | Inteiro opcional (1–365): dias de cobertura abaixo dos quais o agente de estoque (R13) avisa o administrador; reflete o prazo de reposição/entrega do produto. `null` usa o padrão global (`ESTOQUE_HORIZONTE_DIAS`, 10). Vem também em `ProdutoOut`. Campo "Alertar estoque com (dias)" no formulário do produto (2026-10-15) | Sim (`admin`) |
| `GET /api/admin/produtos/categorias` | Categorias distintas (formulário e filtro do admin) |
| `GET /api/admin/produtos/{id}` , `POST /api/admin/produtos` , `PUT /api/admin/produtos/{id}` , `DELETE /api/admin/produtos/{id}` | CRUD de produto (`PUT` parcial). O `DELETE` também remove as fotos e os vetores do CLIP no Qdrant |
| `POST /api/admin/produtos/{id}/estoque` | Grava a quantidade de um centro de distribuição (`{centro_distribuicao, quantidade}`), aba "Estoque por CD" do `ProductFormModal`; devolve o `ProdutoOut` atualizado |
| `POST /api/admin/produtos/{id}/descontos-volume` , `DELETE /api/admin/produtos/{id}/descontos-volume/{desconto_id}` | Faixas de desconto por volume (`{quantidade_minima, percentual_desconto}`); `desconto_id` é UUID (`400` se inválido); devolvem o `ProdutoOut` atualizado |
| `GET /api/admin/produtos/{id}/compatibilidades` , `POST /api/admin/produtos/{id}/compatibilidades` , `DELETE /api/admin/produtos/{id}/compatibilidades/{compativel_com_id}` | Lista (`GET`), cria (`POST`) e remove (`DELETE`) o vínculo de compatibilidade entre dois produtos (`{compativel_com_id}`); `POST`/`DELETE` devolvem a lista atualizada; o produto é escolhido pelo `SearchableSelect` com busca; `404` se algum dos produtos não existe |
| `POST /api/admin/produtos/{id}/imagens` , `DELETE /api/admin/produtos/{id}/imagens/{img_id}` | Foto avulsa do produto (`multipart`: `file`, `is_principal`), indexada na hora no CLIP; o `DELETE` remove o arquivo e o vetor |
| `POST /api/admin/produtos/catalogo/extrair/stream` | Extração de produtos de catálogos PDF/imagens/texto (`.txt`, `.md`, `.csv`; o `CatalogImportModal` aceita arrastar, colar com Ctrl+V e seleção) em SSE (`multipart`: `files`, `provider` `local`\|`external`, `fallback_external`, `page_range` opcional: `1-5`, `2, 5, 8`, `3-`, `-4`), usada pelo `CatalogImportModal` |
| `POST /api/admin/produtos/upload-temp` , `POST /api/admin/produtos/catalogo/confirmar` | Foto de rascunho da conferência (`temp/`) e gravação em lote dos produtos conferidos (com as fotos movidas para a pasta definitiva e indexadas no CLIP) |
| `GET /api/uploads/produtos/{arquivo}` , `GET /api/uploads/produtos/temp/{arquivo}` | Serve as fotos de produto (definitivas e de rascunho), com proteção contra path traversal |
| `POST /api/auth/login` , `GET /api/auth/me` | Autenticação simplificada mock (senha `12345`/`admin123`) e dados do usuário autenticado (perfil calculado a partir do histórico de compras, ou `Admin` fixo por e-mail) |
| `POST /api/auth/register` | Autocadastro (`{nome, email, password?, perfil?, requester_email?}`); cadastrar perfil `Admin` exige `requester_email` de um Admin já existente (senão `403`) — decisão em `docs/ARCHITECTURE.md` §5 (2026-09-29) |
| `GET /api/auth/users` | Lista todos os usuários cadastrados com o perfil já calculado, para a página `/admin/usuarios` — decisão em `docs/ARCHITECTURE.md` §5 (2026-09-29) |
| `POST /api/orders` , `GET /api/orders/{id}` , `GET /api/orders` , `POST /api/orders/quote` , `POST /api/orders/freight` | Criação, consulta, cotação por volume e simulação de frete de pedidos (Fase 7) |
| `GET /api/agendamentos/meus` , `POST /api/agendamentos/{id}/cancelar` , `GET /api/agendamentos/admin` , `POST /api/agendamentos/admin/manual` , `GET /api/agendamentos/admin/google-events` | Gestão completa de agendamentos, cancelamento sincronizado com o Google Calendar e consulta em tempo real da agenda corporativa via MCP (Fase 7, R11) |
| `POST /api/rag/documents` | Upload de um PDF/texto (`multipart/form-data`: `file` + `domain` + `collection_id` opcional, default a collection ativa) para ingestão no RAG — usado pela página `/admin/ingestao` (ver `backend/src/app/api/rag.py`) |
| `GET /api/rag/documents` | Lista o registro de documentos ingeridos (mais recente primeiro), fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `DELETE /api/rag/documents/{document_id}` | Exclui um documento (registro + pontos no Qdrant), fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `POST /api/rag/documents/{document_id}/reingest` | Reingere um documento já enviado em outra collection (a partir do arquivo original salvo em disco), fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `GET /api/rag/documents/{document_id}/download` | Baixa o arquivo original (`Content-Disposition: attachment`), usado pelo `DocumentDownloadCard` do chat. **Público** só quando a collection de origem tem `purpose="chat"`; para qualquer outro `purpose` (`admin`, `mcp_b2b`) exige token admin (`Authorization`, `X-Auth-Token` ou `?token=`). `404` se o documento não existe |
| `GET /api/rag/documents/{document_id}/content` | Devolve o arquivo original do documento (PDF/TXT/MD/CSV, `FileResponse` com `Content-Disposition: inline`), usado pelo preview em `DocumentViewModal.tsx` (`/admin/ingestao`) — 404 se o documento ou o arquivo em disco não existir, fora do MVP original |
| `GET /api/rag/collections` | Lista os perfis de collection configurados, com contagem de documentos e finalidade (`purpose`: `chat`/`mcp_b2b`/`admin`) por collection, fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `POST /api/rag/collections` | Cria um novo perfil de collection (nome, modelo de embedding, chunking, HNSW, quantização, payload indexing, `purpose` — default `chat`) e a collection real correspondente no Qdrant, fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `POST /api/rag/collections/{collection_id}/activate` | Marca a collection como ativa (é a que o chat passa a usar na busca); retorna **409** se a collection for `purpose="mcp_b2b"` (restrita ao canal MCP B2B, não pode ser ativada para o chat), fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `DELETE /api/rag/collections/{collection_id}` | Exclui a collection em cascata (documentos, pontos no Qdrant e arquivos em disco); bloqueado (409) se for a collection ativa, fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `POST /api/rag/playground/search` | Roda a mesma busca contra várias collections em paralelo e devolve resultados/latência por collection, para comparação manual, fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `POST /api/rag/images` , `POST /api/rag/images/search` , `POST /api/rag/images/identify` | Catálogo visual CLIP (R6), `multipart`. `POST /api/rag/images`: `file` (PNG/JPG/WEBP, senão `400`) + `domain`, ingere e devolve `201 {image_id, filename, domain}`. `/search`: `file` (imagem) **ou** `query` (texto), `domain` opcional; devolve `[{image_id, filename, domain, score, produto_id, imagem_url}]` (`422` se nenhum dos dois). `/identify`: `file`; roda o fluxo CLIP interno → visão externa → RAG texto e devolve o mesmo resultado do evento SSE `identification` (`status`, `produto`, `produto_id`, `imagem_url`, `fonte`, `detalhes`, `confianca_interna`/`confianca_externa`, `mensagem`, mais telemetria `prompt_tokens`/`completion_tokens`/`total_tokens`/`cost_*_usd`/`estimated_cost_usd`/`model_name`). `503` se o RAG está fora do ar. O widget de chat não os chama (envia a imagem em `POST /api/chat/messages`) |
| `GET /api/rag/crawler/run/stream` | Dispara um crawl a partir de uma URL semente (`url`, `depth`, `max_pages` opcional — default `crawler_max_pages_default`) e emite progresso em tempo real via SSE (eventos `visitando`/`ingerida`/`enfileirada`/`erro`/`done`); classifica cada página por LLM e ingere direto (`>=` limiar de confiança) ou enfileira para revisão (abaixo do limiar), consumido via `EventSource` pela aba "Crawler" de `/admin/ingestao` — ver `backend/src/app/api/crawler.py` |
| `GET /api/rag/crawler/pending` | Lista as páginas crawleadas cuja classificação de domínio ficou abaixo do limiar de confiança, aguardando revisão manual (aba "Crawler" de `/admin/ingestao`) |
| `POST /api/rag/crawler/pending/{page_id}/approve` | Aprova uma página pendente com o domínio escolhido pelo revisor e a ingere no RAG (`origin="crawler"`) |
| `POST /api/rag/crawler/pending/{page_id}/reject` | Descarta uma página pendente sem ingerir |
| `GET /api/admin/local-models` | Lista os modelos locais já baixados no Ollama, com qual está ativo, fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `POST /api/admin/local-models/activate` | Troca em runtime qual modelo local o chat usa (só em memória, reseta no restart), fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `POST /api/admin/local-models/pull` | Dispara o download de um modelo (biblioteca do Ollama ou GGUF do Hugging Face) em background, sem bloquear o backend, fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `GET /api/admin/local-models/pull-status` | Consulta o progresso de um download em andamento (query param `name`), usado em polling pelo frontend, fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `DELETE /api/admin/local-models/delete` | Desinstala um modelo do Ollama (body `{name}`); 404 se não baixado, 409 se for o modelo ativo, 502 se o Ollama falhar. O frontend pede confirmação em modal, fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `GET /api/admin/runtime-settings` | Lê os parâmetros de execução ajustáveis em runtime (temperatura do modelo local, timeouts local/externo, fallback de domínio do RAG, `crawler_max_pages_default`, `crawler_confidence_threshold`, `intent_router_provider`: `heuristica` \| `heuristica_llm` \| `jev_openrouter`, `tone_monitor_enabled`, `tone_monitor_provider`: `heuristica_llm` \| `jev_openrouter`, `external_model_name`: modelo de texto do OpenRouter, trocado pelo card "Modelo externo" de `/admin/modelos`, `external_vision_model_name`, `image_internal_confidence`, `image_external_confidence`, `estoque_agent_mode`: `desativado` \| `deterministico` \| `ia` e `estoque_agent_llm`: `local` \| `externo` — agente de previsão de estoque, R13; `local_llm_keep_alive`: string do Ollama, `-1` = permanente (default), `5m`, `0` = descarrega; `local_llm_warmup_on_startup`: bool, default `true` — pré-carrega o modelo na subida do backend; a resposta traz também `local_model_loaded` e `local_model_vram_bytes`, somente leitura), persistidos em `app_settings`, fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `POST /api/admin/runtime-settings/preload` , `POST /api/admin/runtime-settings/unload` | Carrega o modelo local na VRAM na hora (warmup manual) ou o descarrega (libera VRAM); sem corpo, devolvem os runtime-settings atualizados. Botões da seção de VRAM de `/admin/modelos` |
| `PUT /api/admin/runtime-settings` | Atualiza (parcialmente — só os campos enviados mudam) os parâmetros acima; `local_llm_temperature: null` explícito reseta para o default do próprio modelo, fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `GET /api/admin/model-catalog/characteristics` | Características de um modelo (query `source`: `openrouter` \| `ollama` \| `huggingface`, e `tag`): `{source, tag, is_multimodal, input_modalities, output_modalities, context_length, parameter_size, quantization, pricing_prompt_per_1k, pricing_completion_per_1k, knowledge_cutoff, fetched_at}`; cacheado no banco. `404` se não achar. Alimenta o `ModelCharacteristicsPanel` de `/admin/modelos` | Sim (`admin`) |
| `POST /api/admin/model-catalog/characteristics/refresh` | Mesmo retorno, mas força nova consulta à fonte (corpo `{source, tag}`); `404` se não achar | Sim (`admin`) |
| `GET /api/admin/tom/escalonamentos` | Lista os casos escalonados pelo Monitor de Tom (R8) persistidos em `tom_escalonamentos`, mais recente primeiro, `LIMIT 100` fixo, sem paginação — sem UI dedicada nesta entrega, só para inspeção manual/demonstração, ver `docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md` §6.2 |
| `GET /api/admin/agentes/mensagens` | Caixa de entrada dos agentes (R13, 2026-10-15). Query: `apenas_nao_lidas`, `agente`, `limit` (1–500, padrão 100). Devolve `{mensagens: [{id, agente, tipo, severidade, titulo, corpo, dados, lida, email_status, criado_em}], nao_lidas}`, mais recentes primeiro. `email_status`: `enviado`, `nao_configurado`, `falhou`, `nao_enviado` | Sim (`admin`) |
| `POST /api/admin/agentes/mensagens/{id}/lida` | Marca uma mensagem como lida; `404` se não existe | Sim (`admin`) |
| `POST /api/admin/agentes/mensagens/lidas` | Marca todas como lidas; devolve a lista atualizada | Sim (`admin`) |
| `GET /api/admin/ferramentas` | Estado das três ferramentas de inteligência de código (`/admin/ferramentas`, 2026-10-13). Devolve `{ferramentas: [{id, nome, descricao, tipo, url, online, detalhe, comando}]}`, na ordem Graphify → Repowise → GitNexus. `tipo` é `artefato` (arquivo gerado no repo) ou `servidor` (processo local sondado com timeout de 1,5s); `url` é `null` quando não há o que abrir, e `comando` é o que o desenvolvedor roda para gerar/subir. Servidor fora do ar **não** é erro: devolve `200` com `online: false` | Sim (`admin`) |
| `GET /api/admin/ferramentas/graphify/grafo` | Serve `graphify-out/graph.html` para o iframe da tela. Aceita o token admin por `?token=` (iframe não manda cabeçalho `Authorization` — mesmo caminho de `GET /api/rag/documents/{id}/download`). `404` com instrução de rodar `graphify update .` quando o artefato não existe | Sim (`admin`) |
| `POST /api/admin/ferramentas/{id}/atualizar` | Reindexa a ferramenta na raiz do repositório — `id` é `graphify` (`graphify update .`) ou `gitnexus` (`node .gitnexus/run.cjs analyze --index-only`, com fallback para a CLI `gitnexus`); botão na aba de cada uma em `/admin/ferramentas` (2026-10-15). Devolve `{sucesso, saida}`; falha do comando é `200` com `sucesso: false`. `404` para outro `id`, `409` se já há execução em andamento, `503` se a CLI não está no PATH do backend. Timeout de 300s | Sim (`admin`) |
| `GET /api/admin/datasets` · `GET /api/admin/datasets/{conjunto}/itens` (`apenas_pendentes`, `offset`, `limite`) · `PATCH /api/admin/datasets/{conjunto}/itens/{indice}` (`{status, campos?}`) · `POST /api/admin/datasets/tarefas` (`{tipo}`) · `GET /api/admin/datasets/tarefas` · `GET /api/admin/datasets/tarefas/{id}?desde=N` · `POST /api/admin/datasets/tarefas/{id}/cancelar` | Painel de Preparação da Avaliação (`/admin/datasets`, 2026-10-17). `campos` vai cru nos dois sentidos: cada conjunto tem o seu formato e a tela monta o layout pelas chaves. O `PATCH` faz `update`, então aprovar um item intacto não manda `campos`. `409` ao revisar conjunto de gabarito automático (imagem, banco) e ao iniciar tarefa cujo tipo já está rodando. O detalhe da tarefa devolve só as linhas a partir de `desde` e o `proximo_offset` para a volta seguinte — o buffer é de 2.000 linhas. Cliente em `frontend/lib/api/datasets.ts` | Sim (`admin`) |
| `GET /api/admin/atendimento/fila`, `GET /api/admin/atendimento/meus-chats`, `GET /api/admin/atendimento/{conversation_id}` | Central de Atendimento (Admin): fila de espera por prioridade e tempo (`tempo_espera_segundos`, `motivo_escalonamento`), chats do atendente autenticado e detalhe da conversa com mensagens e dados do cliente. |
| `POST /api/admin/atendimento/{conversation_id}/claim`, `.../mensagem`, `.../close` | Assumir a conversa (claim atômico; 409 se outro atendente já assumiu), enviar mensagem do atendente ao cliente (papel `atendente`) e encerrar ou devolver a conversa à IA. |
| `POST /api/chat/conversations/{id}/transbordo` | Botão "Falar com atendente humano" do widget: coloca a conversa na fila (motivo `solicitacao_direta`). |
| `GET /api/admin/charts` , `POST /api/admin/charts` , `PUT /api/admin/charts/{id}` , `DELETE /api/admin/charts/{id}` , `POST /api/admin/charts/{id}/refresh` | Gráficos persistidos de `/admin/dashboards` (`lib/api/charts.ts`). `AdminChartOut`: `{id, titulo, descricao, tipo_grafico (bar\|line\|pie\|area\|donut), config_json, dados_json, sql_query, fixado, ordem, criado_por, criado_em, atualizado_em}`; lista ordenada por fixado, ordem e criação, sem cache. `POST` (`201`): `titulo` obrigatório, `fixado` default `true`. `PUT` parcial (só os campos enviados). `refresh` re-executa a agregação (`sql_query`) e atualiza `dados_json`. `id` é UUID (`400` se inválido), `404` se não existe; `DELETE` devolve `{"ok": true}` | Sim (`admin`) |
| `GET /api/admin/pedidos` · `GET /api/admin/pedidos/{id}` · `POST /api/admin/pedidos/{id}/converter-manual-simples` · `.../analisar-comprovante` · `.../confirmar-conversao` · `.../converter-auto-admin` | Conversão de reserva em venda (`/admin/pedidos`, `lib/api/adminPedidos.ts`). Listagem: query `status` (`reservado`, `venda_concluida`, `pagamento_divergente`), `limit` (1–200, default 50), `offset`; cada pedido: `{id, status, user_email, conversation_id, comprovante_url, tipo_conversao, convertido_em, convertido_por, llm_parecer, criado_em, valor_total, itens[]}`. Três modalidades, todas só para pedido em `reservado` (senão `400`): (1) `converter-manual-simples` (`multipart`: `convertido_por`, `comprovante` opcional) → `tipo_conversao=manual_simples`; (2) `analisar-comprovante` (`multipart`: `comprovante`) devolve `{pedido_id, valor_devido, comprovante_url, parecer: {valido, valor_pago, divergencia, justificativa, codigo_transacao}}` e depois `confirmar-conversao` (JSON `{comprovante_url?, parecer_json?, convertido_por?}`) → `manual_padrao`; (3) `converter-auto-admin` (`multipart`: `comprovante`) converte sozinho se o parecer for válido e sem divergência, senão marca `pagamento_divergente`. `404` se o pedido não existe | Sim (`admin`) |
| `GET /api/admin/metrics/ai-usage` | Painel de uso de IA (`/admin/metricas`, item E do ledger, 2026-10-08): agrega `ai_usage_events` por origem × ambiente × modelo × operação, mais o recorte diário e o volume de chats encerrados. Query: `period` (`today`\|`7d`\|`30d`\|`all`) ou `start_date`+`end_date` (`YYYY-MM-DD`, `400` se mal formada); o recorte é no calendário **local** do administrador. Substituiu `GET /api/admin/metrics/tokens-and-costs` (removido em 2026-10-08) — ver contrato completo abaixo |

`POST /api/chat/messages` — contrato já implementado (Fase 2 para o request;
streaming SSE do response adicionado depois, ver decisão em
`docs/ARCHITECTURE.md` §5 "Streaming SSE do chat"; ver
`backend/src/app/api/chat.py` e `backend/src/app/models/chat.py`):

```jsonc
// Request
{
  "message": "Quero um orçamento para o produto X", // opcional se `audio` ou `image` vier preenchido
  "conversation_id": "uuid-opcional, omitir para iniciar conversa nova",
  "audio": null, // opcional, base64 (wav ou mp3) — processado via STT (R5) quando presente
  "image": null, // opcional, base64 (PNG/JPG/WEBP) — ver `image_intent` (R6)
  "image_intent": null, // opcional: "documento" = OCR (só quando o sistema pede comprovante); ausente/"produto" = identificação de produto (PADRÃO, ver docs/ARCHITECTURE.md §4)
  "user_email": null, // opcional: e-mail do usuário autenticado no frontend. Histórico detalhado de compras e pedidos no prompt SOMENTE é carregado quando o usuário está autenticado; quando não logado, usa apenas para classificação de tipo de cliente (R10)
  "auth_token": null // opcional: token de POST /api/auth/login quando o usuário está logado nesta sessão. Verificado no servidor (verificar_admin_por_token) para liberar o modo admin de busca no RAG (Admin vê chat ativo + mcp_b2b + admin); NUNCA usar user_email sozinho para isso — ver docs/ARCHITECTURE.md §6, decisão de 2026-09-30
}
```

> **Fluxo de imagem (docs/ARCHITECTURE.md §4):** o padrão para qualquer
> imagem é **identificação de produto** (CLIP interno → visão externa → RAG
> texto). O OCR só roda quando o widget marca `image_intent="documento"` — o
> que o frontend faz apenas quando o assistente solicitou um
> comprovante/extrato. No fluxo de identificação a resposta sai como
> `token` + um evento `identification` (ver abaixo); o OCR segue o fluxo
> normal do orchestrator (classificação + geração).

A resposta (200) é o próprio stream: `Content-Type: text/event-stream`, uma
sequência de eventos SSE (`event: <tipo>\ndata: <json>\n\n`), nesta ordem:

```
event: conversation
data: {"conversation_id": "uuid-da-conversa"}

event: transcription        // só emitido quando o request trouxe `audio` e a transcrição não veio vazia
data: {"transcribed_message": "texto transcrito do áudio"}

event: status                // opcional, zero ou mais vezes, só quando o modelo local ainda não está "quente"
data: {"status": "carregando_modelo"}
// Emitido antes de `generate_stream` (geração da resposta) e, quando
// `ROUTER_COMPLEXITY_STRATEGY=llm`, também antes da classificação (que
// chama o modelo local para resolver mensagens ambíguas) — correção de
// 2026-09-18: antes, um cold-start disparado só pela classificação
// acontecia em silêncio (o único check ficava depois dela), então a
// mensagem de espera às vezes não aparecia (ver `orchestrator.py`).
// Com a conversa em atendimento humano (status `aguardando_humano` ou
// `em_atendimento_humano`), a IA fica pausada e o stream é só: `conversation`,
// `status` com {"status", "atendente_id", "atendente_nome"}, um `token` com o
// aviso de recebimento e um `done` com domain="atendimento_humano" e
// backend_used="humano" (tokens e custo zerados). O botão "Falar com atendente
// humano" do widget e frases como "quero falar com um atendente humano"
// colocam a conversa na fila.

event: token                 // um evento por trecho de texto gerado, zero ou mais vezes
data: {"text": "trecho da resposta"}

event: identification        // SÓ no fluxo de identificação de produto por imagem (image sem image_intent="documento")
data: {
  "status": "encontrado_interno",   // encontrado_interno | encontrado_externo | nao_identificado
  "produto": "Câmera IP 4MP",        // ausente quando nao_identificado; nome do cadastro quando achado no banco
  "produto_id": 7,                    // opcional: presente quando o produto está no cadastro
  "fonte": "catalogo_imagens",        // catalogo_imagens | visao_externa+catalogo | visao_externa+rag_texto
  "detalhes": "...ficha do produto...", // opcional: ficha do banco (descrição, especificações técnicas, dimensões, peso) ou, sem produto no banco, texto do RAG
  "confianca_interna": 0.45,          // presente no caso interno
  "confianca_externa": 0.88,          // presente no caso externo
  "mensagem": "Não consegui identificar..." // presente só no nao_identificado
}
// No fluxo de identificação, o `done` traz backend_used="identificacao_imagem"
// e domain="vendas" (o restante da telemetria de inferência não se aplica).

event: escalonamento         // opcional, no máximo uma vez por conversation_id — Monitor de Tom (R8)
data: {"motivo": "urgencia", "confianca": 0.87}
// motivo: "urgencia" | "insatisfacao". Emitido quando o Monitor de Tom
// (heurística + fallback heuristica_llm/jev_openrouter, ver
// docs/ARCHITECTURE.md §5) detecta urgência/insatisfação forte na mensagem
// atual — não substitui a resposta normal do domínio, que continua sendo
// gerada e streamada. Só dispara uma vez por conversa (estado em memória
// por processo, perdido em restart). O caso também é persistido em
// `tom_escalonamentos` (Postgres) e exposto para consulta manual em
// GET /api/admin/tom/escalonamentos. No frontend, é recebido via
// callback `onEscalonamento` em `lib/api/chat.ts` e renderiza o
// componente `components/chat/EscalonamentoBanner.tsx` em `ChatModal.tsx`.

event: done                  // sempre o último evento em caso de sucesso — telemetria completa
data: {
  "domain": "vendas",              // vendas | suporte | atendimento | agendamento | fora_escopo
  "backend_used": "local",         // local | externo | resposta_fixa (mensagem só com
                                   // e-mail, sem LLM, R10) | identificacao_imagem |
                                   // humano (conversa em atendimento humano)
  "escalation_reason": "nenhum",   // nenhum | fora_escopo | rag_vazio | complexidade_alta

  // Telemetria de inferência (além do MVP original, a pedido explícito —
  // decisão registrada em docs/ARCHITECTURE.md §5). Todos opcionais
  // (`null` quando a métrica não se aplica ao caminho tomado).
  "model_name": "llama3.1:8b",
  "prompt_tokens": 128,
  "completion_tokens": 342,
  "total_tokens": 470,
  "latency_ms": 2500.0,
  "ttft_ms": 150.0,
  "tps": 190.0,
  "confidence": 0.92,
  "complexity": "baixa",
  "cost_prompt_usd": 0.0,          // custo dos tokens de entrada
  "cost_completion_usd": 0.0,      // custo dos tokens de saída
  "estimated_cost_usd": 0.0,
  "vision_used": false,            // true quando a resposta envolveu visão computacional
  "rag_retrieval_ms": 38.3,        // tempo do bloco de recuperação — busca RAG e, em Vendas com
                                    // integração do catálogo (R12), a consulta de vendas
                                    // concorrente (as duas rodam em paralelo, ver docs/ARCHITECTURE.md §5)
  "rag_chunks_count": 3,
  "rag_avg_score": 0.71,
  "rag_chunks": [ { "source": "manual.pdf", "score": 0.78 } ],  // fonte e score de cada chunk

  // Provedor que REALMENTE classificou a intenção nesta requisição —
  // "heuristica_llm" ou "jev_openrouter" (ver docs/ARCHITECTURE.md, decisão
  // do TypeSafe Jev como provedor alternativo). Alternado via runtime
  // settings, não por request. Reflete o provedor efetivo, não
  // necessariamente o selecionado: se o Jev falhar (timeout, erro HTTP,
  // resposta malformada), o classificador degrada para a heurística local e
  // este campo mostra "heuristica_llm" mesmo com "jev_openrouter"
  // selecionado no admin (correção de revisão final — antes vazava o valor
  // selecionado, não o usado de fato). `null` no fluxo de identificação de
  // imagem, que não passa por classificação de intenção.
  "router_provider": "heuristica_llm",

  // Classificação do visitante (R10, Fase 6): "cliente" | "esporadico" |
  // "lead" | "nao_classificado", com o motivo. `null` quando a memória da
  // conversa está indisponível ou no fluxo de identificação de imagem.
  "perfil_usuario": "lead",
  "perfil_motivo": "intenção de compra",

  // Card rico opcional (Fase 8, decisão em docs/ARCHITECTURE.md §5,
  // 2026-09-29) — união discriminada por "tipo"; `null`/ausente na maioria
  // dos turnos. Ver §3, "Cards ricos".
  "card": {
    "tipo": "produto",           // | "cotacao" | "agendamento" | "grafico" | "documento_download"
    "produto_id": 1,
    "nome": "Gerador Diesel GD-15",
    "preco": "24900.00",         // Decimal serializado como string
    "imagem_url": "/api/uploads/produtos/gd15.jpg",
    "estoque_total": 8
  }
}
```

O texto completo da resposta do assistente **não** vem em um campo único —
o cliente reconstrói concatenando o `text` de cada evento `token`, na ordem
em que chegam (é assim que a UI faz o efeito de "digitando"). O evento
`transcription` (campo `transcribed_message`) continua sendo como o widget de chat exibe o texto
transcrito na bolha do usuário (ver §3), já que a transcrição só existe no
backend.

Se uma dependência (Ollama, OpenRouter, Qdrant) falhar **depois** que o
stream já abriu, a resposta HTTP já começou (200) — não há mais como trocar
o status code nesse ponto, então o backend emite um evento `error` como
último evento:

```
event: error
data: {"detail": "Serviço temporariamente indisponível, tente novamente."}
```

Erros de **validação de entrada**, que acontecem antes do stream abrir,
continuam HTTP normal (sem SSE): `audio` não é base64 válido → 400; nem
`message` nem `audio` preenchidos, ou transcrição vazia sem `message` de
fallback → 422; STT indisponível → 503. `message` é **opcional** — é
obrigatório enviar `message` e/ou `audio`. Quando `audio` vem preenchido, o
texto transcrito substitui `payload.message` como mensagem efetiva enviada
ao roteador — o áudio é tratado como alternativa ao campo de texto
(push-to-talk), não como complemento dele. Se a transcrição vier vazia
(áudio sem fala reconhecível), o backend usa `payload.message` como
fallback quando presente. Limitações que restam: sem robustez a áudio
ruidoso/silencioso, sem VAD, idioma fixo em português (ver
`docs/ARCHITECTURE.md` §5/§7). O histórico usado para resolver confirmações
curtas (R3) vem da memória da conversa no Postgres (R9, Fase 6: as 3
mensagens mais recentes do cliente naquele `conversation_id`). A troca só é
gravada quando o evento `done` chega com sucesso, não em caso de `error`.

**Estado atual do frontend (Fase 7/8, ver `docs/ROADMAP.md`):** o scaffold
Next.js foi criado em `frontend/` (App Router, TypeScript `strict`, Tailwind
CSS, ESLint + Prettier, Vitest + Testing Library) e o widget de chat consome
`POST /api/chat/messages` (`frontend/lib/api/chat.ts`) com **texto e áudio**.
`sendChatMessage` foi reescrito para consumir o contrato SSE descrito acima:
em vez de `response.json()`, faz o parsing manual de blocos `event:`/`data:`
do `ReadableStream` da resposta (não usa `EventSource`, que só suporta GET) e
entrega a resposta incrementalmente via callbacks — `onConversationId`,
`onTranscription`, `onStatus`, `onToken`, `onEscalonamento`, `onDone`, `onError` — retornando
`Promise<void>` em vez de um objeto de resposta único; nunca lança, erros de
rede/HTTP/stream viram chamada a `onError` (ver
`frontend/tests/lib/api/chat.test.ts`). `ChatModal.tsx` já consome essa
assinatura (Fase 8): acumula o texto dos eventos `token` numa bolha do
assistente criada sob demanda, exibe um texto de status temporário enquanto
o modelo local carrega (ver "Estados do widget" abaixo) e nunca deixa a
bolha vazia ou travada no placeholder — se `onDone` chegar sem nenhum token
(resposta vazia do modelo), o texto final vira um aviso de "sem resposta do
modelo, tente novamente" em vez de ficar em branco. Além de texto e áudio, o
widget envia imagem (`ImageUploader`), mostra os cards ricos (produto, cotação,
agendamento, download de documento e gráfico), a identificação de produto por
foto e o aviso de escalonamento. As demais páginas da Seção 2 estão
implementadas e integradas às respectivas APIs (catálogo, pedidos,
autenticação, agendamentos e telas administrativas).

**Gravação de áudio (`AudioRecorder`, R5):** botão de microfone
(`components/chat/AudioRecorder.tsx`) ao lado do botão "Enviar" no
`ChatModal`. Comportamento **toggle** (não push-to-talk, ao contrário do que
a Seção 3 lista como alternativa): um clique inicia a gravação
(`navigator.mediaDevices.getUserMedia` + `MediaRecorder` do browser), outro
clique para e dispara o envio automaticamente — sem edição/preview do áudio
antes de enviar. Indicador visual de gravação: o próprio botão muda de ícone
(🎤 → ⏹) e cor (vermelho, `animate-pulse`) enquanto grava, e outros controles
do modal (campo de texto, botão "Enviar") ficam desabilitados durante a
gravação. O `Blob` gravado (formato depende do browser, tipicamente
`audio/webm`) é convertido para base64 no cliente antes de enviar — o
backend detecta o formato pelo conteúdo via faster-whisper/ffmpeg, não pela
extensão (ver `backend/src/app/stt/whisper_client.py`), então não há
conversão para wav/mp3 no frontend. A bolha do usuário só é adicionada
**depois** da resposta do backend, usando `transcribed_message` (o cliente
não sabe o que foi dito antes da transcrição); erro de rede/503/422 usa a
mesma bolha de erro com "Tentar novamente" do fluxo de texto, reenviando o
mesmo áudio em base64. Permissão de microfone negada ou navegador sem suporte
a `getUserMedia`/`MediaRecorder` são tratados localmente no próprio
`AudioRecorder` (mensagem de erro ou botão desabilitado), sem afetar o resto
do widget.

**Telemetria e export de dataset** (além do MVP original, a pedido
explícito — decisão registrada em `docs/ARCHITECTURE.md` §5): cada bolha de
resposta do assistente (`MessageBubble.tsx`) tem um painel com os campos de
telemetria da resposta (`model_name`, `prompt_tokens`/`completion_tokens`,
`latency_ms`, `ttft_ms`, `tps`, `estimated_cost_usd`,
`rag_retrieval_ms`/`rag_chunks_count`/`rag_avg_score`, e o perfil do
visitante `perfil_usuario`/`perfil_motivo`, R10) e, quando a resposta
usou RAG, a lista `rag_chunks` (fonte/arquivo e score de cada chunk
recuperado, na seção "Fontes" do bloco RAG do painel) — escondido por padrão,
revelado por uma engrenagem pequena (⚙️, mesmo tamanho de fonte do rótulo de
domínio) ao lado do rótulo de domínio no topo da bolha (`aria-label`
"Mostrar/Ocultar métricas da resposta"). A largura do painel (barra
compacta + telemetria estendida) acompanha a largura real da bolha de
resposta acima dele — medida via `ResizeObserver` sobre a bolha, não um
`max-width` fixo — com um piso de `16rem` para não quebrar o grid em
respostas muito curtas. O `ChatModal` mostra dois botões de
exportação — CSV e JSON — que baixam as métricas de todas as mensagens da
conversa atual (`frontend/lib/utils/exportMetrics.ts`), independente do
painel por mensagem estar aberto ou fechado, pensados para alimentar a
avaliação experimental da Fase 10 (`docs/EVALUATION.md`), não como uma
feature de produto para o usuário final.

`GET /api/avaliacao/resultados` — **público** (sem token), alimenta a página
`/avaliacao` (Recharts): `{roteador, rag (com `sem_resposta`), etapa7, chunk_size, injecao, modelos}` (`etapa7` vem de `rag_quality/etapa7.json`, gerado por `consolidar_etapa7.py`),
cada seção `null`/vazia se o `results.json` não existe. `chunk_size` lê a
grade da Etapa 3 (`eval/rag_ingestion/resultados_etapa3.json`) e traz, por
tamanho de chunk em tokens, o melhor overlap com `ndcg_10` e `recall_5`
(`{chunk_size, overlap_pct, ndcg_10, recall_5}`). Só agregados, com
intervalo de Wilson (`{acertos, total, taxa, ic_inf, ic_sup}`); tipos em
`frontend/lib/api/avaliacao.ts`. Link "Resultados da Avaliação" no menu ⚙️.

`GET /api/admin/metrics/ai-usage` — contrato do painel de uso de IA
(`/admin/metricas`, item E do ledger, 2026-10-08, ver
`docs/superpowers/specs/2026-10-08-ledger-uso-ia-item-e-painel-design.md`
§2):

```jsonc
// Resposta (AiUsageReport, frontend/lib/api/metrics.ts)
{
  "period": "7d",
  "atendimento": { "chats_encerrados": 42 },
  "totais":       { /* BlocoMetricas */ },
  "por_origem":   [ { "origem": "chat", ...bloco }, { "origem": "b2b", ... }, { "origem": "admin", ... } ],
  "por_ambiente": [ { "ambiente": "interno", ...bloco }, { "ambiente": "externo", ...bloco } ],
  "por_modelo":   [ { "modelo": "clip", "ambiente": "interno", ...bloco }, ... ],
  "por_operacao": [ { "operacao": "geracao_resposta", "origem": "chat", "ambiente": "interno", ...bloco }, ... ],
  "diario": [
    { "data": "2026-10-08", "chats_encerrados": 7, "totais": { /* bloco */ }, "por_origem": [ { "origem": "chat", ...bloco }, ... ] }
  ]
}
// BlocoMetricas: { chamadas: number, tokens_entrada: number|null,
//                  tokens_saida: number|null, custo_usd: number|null,
//                  chamadas_sem_custo_medido: number }
```

`tokens_entrada`/`tokens_saida`/`custo_usd` são `number | null`: `null` é
"não medido" (a chamada aconteceu, mas o custo/tokens não foram
capturados), `0` é "medido e grátis" (CLIP, modelo local na GPU). O
frontend nunca normaliza `null` para `0` — a renderização passa pelos
helpers de `frontend/lib/format/metricas.ts` (`formatarCusto`,
`formatarTokens`, `formatarDataPtBr`, mais as constantes `NAO_MEDIDO`
(`"—"`) e `TITULO_NAO_MEDIDO`, usado como `title`/tooltip do traço):
`null` → `—`; `0` → `$0.0000`/`0`. Em `por_origem`/`por_ambiente` só vêm
as dimensões com evento no período; na tabela diária, uma origem sem linha
num dia é renderizada como `$0.0000` (zero chamadas conhecido), não como
`—` — distinção implementada em `TabelaDiaria.tsx`, não em
`formatarCusto`.

Consumido por `fetchAiUsageMetrics` (`frontend/lib/api/metrics.ts`) e
renderizado por `frontend/app/admin/metricas/page.tsx` (cabeçalho, filtro
de período e KPI de chats encerrados preservados da versão anterior),
delegando cada seção a um componente em
`frontend/components/admin/metricas/`: `CardMetrica.tsx` (card genérico de
um bloco de métricas, reusado por origem/ambiente), `SecaoPorOrigem.tsx`,
`SecaoPorAmbiente.tsx`, `TabelaPorModelo.tsx`, `TabelaPorOperacao.tsx` e
`TabelaDiaria.tsx`.

Os tipos de request/response devem espelhar os schemas Pydantic do backend
(`src/app/models/`, ver `docs/CONVENTIONS.md`) — ao gerar os tipos
TypeScript, prefira derivá-los de um contrato compartilhado (ex.: OpenAPI
gerado pelo FastAPI + gerador de tipos) em vez de reescrevê-los manualmente,
para evitar divergência entre frontend e backend.

## 5. Estrutura de pastas do frontend

```
frontend/
├── app/
│   ├── layout.tsx              # layout raiz — inclui o ChatWidget global
│   ├── page.tsx                 # Home institucional
│   ├── produtos/
│   │   ├── page.tsx              # listagem
│   │   └── [id]/page.tsx         # detalhe do produto
│   ├── pedidos/
│   │   ├── page.tsx               # carrinho/checkout
│   │   └── historico/page.tsx     # histórico de pedidos
│   ├── conta/
│   │   ├── login/page.tsx
│   │   ├── cadastro/page.tsx
│   │   └── perfil/page.tsx
│   ├── agendamentos/page.tsx      # status de visitas agendadas
│   ├── avaliacao/page.tsx         # resultados públicos da avaliação (Fase 10)
│   ├── admin/                     # agendamentos, atendimento, dashboards, datasets, ferramentas,
│   │                              # ingestao, mensagens, metricas, modelos, pedidos, produtos, usuarios
│   ├── suporte/page.tsx           # FAQ / central de ajuda
│   └── contato/page.tsx
├── components/
│   ├── chat/
│   │   ├── ChatWidget.tsx          # botão flutuante + estado aberto/fechado
│   │   ├── ChatModal.tsx           # modal de conversa (sobre ui/Modal.tsx)
│   │   ├── MessageBubble.tsx
│   │   ├── Chat*.tsx               # partes do modal: mensagens, input, ações, métricas, banner de escalonamento
│   │   ├── AudioRecorder.tsx
│   │   ├── ImageUploader.tsx
│   │   └── cards/                  # ChatCard (dispatcher), ProductCard, AppointmentCard, QuoteCard, DocumentDownloadCard, ChatChartCard
│   ├── layout/                     # Header, Footer, AdminGearMenu
│   └── ui/                         # Modal, Tabs, Toast, Tooltip, SearchableSelect
├── lib/
│   ├── api/                        # cliente HTTP para o backend
│   ├── hooks/                      # useChatStore, useChatEnvio, useAuthStore, useCartStore, useAdmin*...
│   └── types/                      # tipos compartilhados com o backend
├── public/
├── tests/
├── .env.example
└── package.json
```

Estado atual: `lib/hooks/useChatStore.ts` contém o estado do widget via Zustand
(aberto/fechado, mensagens, `conversation_id`); o envio fica em `useChatEnvio.ts`.
Não existem `useConversation` nem `useProducts` (os dados de servidor vêm de
`lib/api/` direto nas páginas). Os testes vivem em `tests/` (`components/`,
`lib/`, `unit/`, `smoke/` com Vitest + Testing Library, e `e2e/` com Playwright).

## 6. Convenções específicas de frontend

- TypeScript em modo `strict`; evitar `any` — tipar as respostas do backend.
- Componentes pequenos e focados; o `ChatModal` deve orquestrar
  subcomponentes (`MessageBubble`, `cards/*`), não conter toda a lógica.
- Mobile-first: o widget de chat precisa funcionar bem em telas pequenas
  (é o principal ponto de contato do usuário com o produto do TCC).
- Acessibilidade básica: labels em inputs, navegação por teclado no widget de
  chat, `aria-live` na área de mensagens para leitores de tela acompanharem o
  streaming.
- Testes: **Vitest + Testing Library** para componentes (ex.: `MessageBubble`
  renderiza cards corretamente); **Playwright** para os fluxos E2E críticos —
  enviar mensagem de texto, gravar/enviar áudio, enviar imagem, fluxo de
  pedido, login, e as interações do widget em
  `tests/e2e/chat-interacao.spec.ts` (2026-10-14: card rico fecha o modal ao
  navegar, foco de volta na caixa após enviar, abertura já na última
  mensagem, foco na abertura em ponteiro preciso).
  **Por que essas quatro precisam de Playwright e não bastam em Vitest:** o
  jsdom não tem layout — `scrollIntoView` é mock e não existe "estar visível
  na área rolável" —, então `toBeInViewport()`, `toBeFocused()` depois de um
  `requestAnimationFrame` e a navegação real do `next/link` só valem num
  navegador. Verificado que os quatro falham com os componentes revertidos ao
  commit anterior. O caso touch (`pointer: coarse`) segue coberto só em
  Vitest, com stub de `matchMedia`: exigiria um projeto novo com
  `devices["Pixel 5"]` no `playwright.config.ts`.
  Nota de autoria de teste: com o modal aberto, o botão flutuante do
  `ChatWidget` ("Fechar chat") fica fora da árvore de acessibilidade e
  `getByRole` não o acha — para fechar, use o "Fechar" do
  `components/ui/Modal.tsx`. Config em `playwright.config.ts` (só Chromium; `webServer`
  reaproveita `npm run dev` se já estiver rodando). `# MVP: os testes E2E do
  chat mockam POST /api/chat/messages via page.route em vez de depender do
  backend e do modelo local (Ollama)/STT reais — cobre o comportamento da UI
  (envio, exibição de resposta, erro/retry); integração real contra o backend
  fica para os testes de integração da Fase 9` — ver
  `frontend/tests/e2e/chat.spec.ts`. O teste de gravação de áudio usa o
  dispositivo de mídia fake do próprio Chromium (flags
  `--use-fake-device-for-media-stream` e `--use-fake-ui-for-media-stream` em
  `use.launchOptions.args`, `playwright.config.ts`) em vez de um microfone
  real — grava um tom de teste sintético gerado pelo browser. Testes de
  componente do `AudioRecorder` (Vitest) mockam `navigator.mediaDevices.
  getUserMedia` e a classe `MediaRecorder`, que o jsdom não implementa — ver
  `frontend/tests/components/AudioRecorder.test.tsx`.
  Os outros três fluxos críticos estão em specs próprios, mesmo padrão de
  mock via `page.route`: `frontend/tests/e2e/imagem.spec.ts` (upload de
  imagem no chat, identificação de produto e caso não identificado — `# MVP:
  mocka o SSE, não decodifica a imagem nem chama CLIP/visão externa`),
  `frontend/tests/e2e/pedido.spec.ts` (login → carrinho pré-preenchido via
  `?produto=` → checkout → confirmação de pedido; e o gate de login exigido
  para acessar `/pedidos`) e `frontend/tests/e2e/login.spec.ts` (login
  manual, login rápido por conta de demonstração, erro de senha incorreta).
  Existe também um **smoke test manual** (`frontend/tests/smoke/chat.smoke.spec.ts`,
  `npm run test:e2e:smoke`, config separada `playwright.smoke.config.ts`) que
  bate no backend e no Ollama reais, sem mock — exige os dois rodando
  localmente; não faz parte da suíte padrão (`npm run test:e2e`) por causa da
  dependência externa e da latência de LLM real.
- Lint/format: ESLint + Prettier, mesma disciplina de PRs pequenos descrita
  em `docs/CONVENTIONS.md`.
- **Hidratação ("estamos no cliente?"): use `useEstaNoCliente()`**
  (`frontend/lib/hooks/useEstaNoCliente.ts`), não o par
  `useState(false)` + `useEffect(() => setMounted(true), [])`. O hook usa
  `useSyncExternalStore` (snapshot do servidor `false`, do cliente `true`), o
  que evita o segundo render e o `setState` síncrono dentro de efeito que a
  regra `react-hooks/set-state-in-effect` (eslint-plugin-react-hooks 7)
  proíbe. `components/ui/Tooltip.tsx` ainda tem uma cópia local equivalente
  (`useEstaNoCliente` interno) — consolidar quando algo mais mexer no
  Tooltip, que é componente de risco alto no grafo.
- **Carregar dados em efeito: nenhum `setState` antes do primeiro `await`.**
  O padrão nas páginas é: o estado de carregamento já nasce `true`
  (`useState(true)`) porque o efeito sempre carrega no mount; o loader só
  toca estado depois do `await`; e os caminhos interativos (botão
  "Atualizar", listeners de `focus`/`visibilitychange`, submit de filtro)
  ligam o spinner no próprio handler, onde `setState` é permitido. Estado que
  só espelha outro estado é **derivado** em vez de escrito por efeito — ex.:
  `detalhes = activeChatId ? detalhesCarregados : null`
  (`app/admin/atendimento`) e `carregando = loading && (!hasHydrated ||
  (isAdmin && !!token))` (`app/admin/dashboards`, que substituiu o
  `else { setLoading(false) }` responsável pelo bug do visitante não-admin
  preso no esqueleto de carregamento). Para sincronizar estado local com uma
  prop, ajuste durante o render (padrão "adjusting state when a prop
  changes"), como em `CatalogPriceInput`
  (`components/admin/products/CatalogImportModal.tsx`), nunca por efeito.
- `# MVP:` alguns efeitos que disparam um loader `async` ficam com
  `// eslint-disable-next-line react-hooks/set-state-in-effect` e uma
  justificativa logo acima. São **falsos positivos**: o `setState` só ocorre
  depois de `await` sobre uma função `async` importada, e a regra não resolve
  a assincronia dessas chamadas, assumindo o pior caso (uma `async function`
  local idêntica passa sem reclamar). O comentário `eslint-disable-next-line`
  precisa ser a última linha antes do código — explicação vem acima dele, ou
  a diretiva não se aplica.
- **Tipos dos gráficos dinâmicos: `lib/types/charts.ts`.** `ChartCellValue`,
  `ChartRow`, `ChartFormat` e `ChartConfig` são a fonte única usada por
  `AdminChartData` (`components/admin/DynamicChartCard.tsx`), por
  `ChartRenderer`, por `lib/api/charts.ts` e pelo card `ChatCardGrafico`
  (`lib/types/chat.ts`, que antes duplicava a mesma forma inline). Nada aqui
  usa `any`: o payload de tooltip do Recharts vem de `TooltipContentProps`
  (exportado por `recharts` 3) e `formatValue` recebe `unknown`.
- **`<img>` em vez de `next/image` (regra `@next/next/no-img-element`).** Toda
  imagem de produto vem do host do backend, resolvido **em runtime** por
  `getApiBaseUrl()` (IP da LAN, domínio DuckDNS, `localhost`…), e o preview de
  upload é um `blob:` de `URL.createObjectURL`. `next/image` precisa de
  `images.remotePatterns` conhecido em **build-time** e rejeita `blob:`, então
  os 8 pontos de imagem usam `<img>` com
  `// eslint-disable-next-line @next/next/no-img-element` e a justificativa
  acima da diretiva — ver a regressão já coberta em
  `tests/components/PedidosPage.test.tsx`. Em JSX, quando o `<img>` é filho
  direto, o comentário tem de vir entre chaves (`{/* … */}`), senão vira text
  node (`react/jsx-no-comment-textnodes`).
- **`react-hooks/exhaustive-deps`: loader estável, não dependência omitida.**
  Em `app/admin/agendamentos`, os loaders são `useCallback(…, [])` e leem os
  filtros de um `useRef` atualizado por efeito, porque os filtros são
  aplicados por botão (não a cada tecla) — assim o loader entra na lista de
  dependências do efeito de carga sem que digitar no filtro dispare uma nova
  requisição. Em `ProductFormModal`, o efeito depende do objeto
  `produtoParaEditar` inteiro (e não de `produtoParaEditar?.id`): a prop vem
  do state do pai (`editingProduct`), logo a referência é estável entre
  renders.

## 7. Rastreabilidade com os requisitos funcionais

| Requisito | Onde aparece no frontend |
| --- | --- |
| R1 (modelo local) | Transparente ao frontend — nenhuma UI específica |
| R2 (entrada multimodal) | Widget de chat: texto, upload de imagem, gravação de áudio |
| R3 (roteador) | Indicador de domínio no widget (opcional/demonstração) |
| R4 (RAG) | Card de produto no chat; conteúdo de `/produtos` e `/suporte` alimenta o RAG |
| R5 (STT) | `AudioRecorder` + exibição do texto transcrito |
| R6 (tratamento de imagem) | `ImageUploader`. `# MVP`: o card de produto (Fase 8) só é gerado pela resolução por texto em Vendas (`_consultar_vendas`); a identificação por imagem responde com ficha do produto em texto, sem card, ainda |
| R7 (domínios) | Indicador de domínio; páginas `/suporte`, `/produtos`, `/agendamentos` refletem os quatro domínios |
| R8 (monitor de tom) | Banner de transferência para atendente humano |
| R9 (memória da conversa) | ID de conversa persistido; retomada ao reabrir o widget |
| R10 (classificação do usuário) | Estado de login/anônimo repassado ao backend; páginas `/conta/login`, `/conta/cadastro`, `/conta/perfil`; perfil Admin com menu ⚙️ restrito e página `/admin/usuarios` (gestão de usuários e consulta de pedidos por usuário) |
| R11 (agendamento) | Card de confirmação no chat; página `/agendamentos` (listagem, cancelamento e CTA chat); painel `/admin/agendamentos` (gestão por usuário, Google Calendar via MCP e agendamento manual) |
| R12 (MCP B2B) | Card de cotação/reserva no chat quando o roteador aciona o MCP B2B para Vendas |

## 8. Fora de escopo do frontend no MVP

- Gateway de pagamento real — checkout do MVP pode simular o pagamento (ver
  também "fora de escopo" geral em `docs/ARCHITECTURE.md`/`docs/ROADMAP.md`).
- Reagendamento automático de visita com escolha interativa de novos horários pela UI (cancelamento e novo agendamento via chat suportados).
- Notificações push, aplicativo mobile nativo, múltiplos idiomas.
- ~~Painel administrativo para gestão de catálogo/estoque/preços~~ —
  **revogado** pela decisão de 2026-09-25 (pedido explícito do
  desenvolvedor, `docs/ARCHITECTURE.md` §5, Gestão de Produtos): a tela
  `/admin/produtos` cadastra produtos, preços e fotos e, desde 2026-09-27
  (commit `a6c530d`), também estoque por CD, desconto por volume e
  compatibilidade.

**Decisão revista (Fase 2):** a exclusão acima era, na prática, uma regra
geral contra qualquer UI administrativa no MVP. Ela fica mantida para
catálogo/estoque/preços (não há necessidade concreta de UI ali — popular via
banco é suficiente), mas deixa de ser uma proibição geral: uma página
administrativa simples é aceitável no MVP quando (a) ela expõe uma
capacidade de backend que já existe e só era acionável por script/CLI, e (b)
sem ela a tarefa correspondente fica mais difícil de demonstrar/operar do
que deveria. Primeiro caso: `/admin/ingestao` (upload de documentos para o
RAG, ver linha na tabela da Seção 2 e `docs/ARCHITECTURE.md` §5) — antes só
dava para ingerir documentos rodando `backend/scripts/ingest_sample_docs.py`
manualmente. Novas páginas administrativas continuam exigindo essa mesma
análise caso a caso (registrada aqui ou em `docs/ARCHITECTURE.md`), não uma
liberação geral.

`/admin/ingestao` foi ampliada (fora do MVP original, a pedido explícito,
2026-09-14) com um registro/exclusão de documentos e abas de configuração de
collections e playground de busca comparativo — ver
`docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md` e
`docs/superpowers/specs/2026-09-15-rag-collections-config-design.md`. A aba
"Crawler" (R4, Fase 2) foi adicionada depois: formulário de disparo (URL
semente, profundidade, teto de páginas opcional) e fila de revisão das
páginas cuja classificação de domínio ficou abaixo do limiar de confiança,
com aprovação (escolhendo o domínio) ou rejeição — ver
`docs/superpowers/specs/2026-09-19-crawler-paginas-design.md`.
