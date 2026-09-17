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
- **React Query (ou SWR)** para dados de servidor (produtos, pedidos,
  histórico de conversa) — cache e revalidação sem estado global manual.
- **Zustand (ou Context API)** apenas para estado local do widget de chat
  (aberto/fechado, mensagens em andamento, estado de gravação de áudio) — não
  para dados que já vêm do backend.
- **Server-Sent Events (SSE)** para streaming da resposta do chat — mais
  simples de implementar com FastAPI do que WebSocket bidirecional; suficiente
  porque o cliente só precisa *receber* o streaming, o envio é uma requisição
  HTTP normal.

Esta stack é o ponto de partida; qualquer troca (ex.: SSE → WebSocket, se o
chat evoluir para notificações do servidor sem o cliente perguntar) deve ser
registrada aqui com o motivo.

## 2. Seções/páginas propostas

| Seção | Rota (sugestão) | Propósito | Requer login |
| --- | --- | --- | --- |
| Home / Institucional | `/` | Apresentação da empresa, chamada para o chat, destaques de produtos/serviços | Não |
| Produtos (listagem) | `/produtos` | Catálogo com busca e filtro — mesma base de dados usada pelo RAG e pelo MCP B2B (`docs/ARCHITECTURE.md` §6) | Não |
| Produto (detalhe) | `/produtos/[id]` | Especificações, preço, disponibilidade; ponto de entrada para "perguntar ao chat sobre este produto" | Não |
| Pedidos (carrinho/checkout) | `/pedidos` | Fluxo de compra — pode ser iniciado pelo site ou por uma cotação/reserva feita via chat (Vendas + MCP B2B) | Sim |
| Histórico de pedidos | `/pedidos/historico` | Status e histórico — usa o mesmo ID de cliente que alimenta a classificação Cliente/Lead/Esporádico (R10) | Sim |
| Conta do usuário | `/conta/login`, `/conta/perfil` | Login/cadastro simplificado; liga a identidade do site à conversa do chat (R9, R10) | Parcial |
| Agendamentos | `/agendamentos` | Visualizar/consultar visitas agendadas via chat (R11) — leitura apenas no MVP, sem reagendar/cancelar pela UI (essa ação também não existe no backend do MVP) | Sim |
| Suporte / Central de Ajuda | `/suporte` | FAQ e documentação de produto — é justamente o conteúdo que o crawler (R4) e o RAG de Suporte/Atendimento (R7) devem indexar | Não |
| Contato | `/contato` | Dados institucionais, formas de contato alternativas ao chat | Não |
| **Chat** | widget global (todas as rotas) | Ponto de entrada único para os quatro domínios de atendimento — ver Seção 3 | Não (funciona anônimo; melhora com login) |
| Admin — Ingestão de documentos | `/admin/ingestao` | Página interna (acessível pelo menu de engrenagem ⚙️ no cabeçalho e pelo rodapé) para upload de PDF/texto e ingestão no RAG (R4), complementando `backend/scripts/ingest_sample_docs.py` — decisão registrada em `docs/ARCHITECTURE.md` §5 | Não (`# MVP: sem autenticação, ver docs/ARCHITECTURE.md §5`) |
| Admin — Modelos locais (Ollama) | `/admin/modelos` | Página interna (acessível pelo menu de engrenagem ⚙️ no cabeçalho e pelo rodapé) para listar/ativar em runtime/baixar (Ollama ou Hugging Face GGUF) modelos locais de chat — ferramenta de teste, não substitui a escolha de produção da Fase 10 — decisão registrada em `docs/ARCHITECTURE.md` §5 | Não (`# MVP: sem autenticação, ver docs/ARCHITECTURE.md §5`) |

Todas as páginas compartilham `layout.tsx`, que inclui o widget de chat — ele
deve estar disponível em qualquer rota, inclusive durante o checkout.

## 3. Widget de chat (peça central da interface)

**Comportamento geral:** botão flutuante no canto inferior direito, presente
em todas as páginas; ao clicar, abre um modal central (`ChatModal.tsx`,
sobre `components/ui/Modal.tsx`, Radix Dialog), mesmo comportamento em
mobile e desktop. O ID de conversa (R9) é gerado no primeiro envio e
persistido em `localStorage` (usuário anônimo) ou associado ao usuário
logado, permitindo retomar a conversa entre sessões/páginas.

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
- **Cards ricos** para respostas estruturadas, em vez de só texto — cobrem os
  casos onde o roteador aciona uma ferramenta ou o RAG retorna algo
  estruturado:
  - Card de produto (imagem, nome, preço, link para `/produtos/[id]`) —
    resultado de RAG de Vendas ou busca de imagem (R6).
  - Card de confirmação de agendamento (data/hora, link para `/agendamentos`)
    — resultado do MCP do Google Calendar (R11).
  - Card de cotação/reserva (itens, valor, prazo) — resultado das ferramentas
    do MCP B2B (R12) quando o roteador atua como integrador desse MCP.
- **Indicador de domínio** (opcional, mas recomendado para a demonstração do
  TCC): um rótulo discreto mostrando qual domínio o roteador identificou
  (Vendas / Suporte Técnico / Atendimento ao Usuário / Agendamento) — ajuda a
  tornar visível o comportamento do Roteador/Orquestrador na apresentação.
- **Indicador de origem do modelo:** bolhas de resposta do assistente cujo
  `backend_used` retornado pela API é `"externo"` são destacadas em azul
  (`bg-blue-50`/`ring-blue-200`, ver `components/chat/MessageBubble.tsx`) —
  torna visível quando o roteador decidiu usar o modelo externo em vez do
  local, útil para a demonstração do TCC (R1).
- **Banner de transferência humana** quando o monitor de tom aciona a
  escalada (R8): mensagem clara ("Conectando você a um atendente...") — no
  MVP essa transferência é simulada no backend, mas a UI deve reagir a esse
  evento como se fosse real.

**Estados do widget:** ocioso · enviando · aguardando streaming · gravando
áudio · processando imagem · transferido para atendente · erro (ex.: falha
do MCP do Google Calendar — mostrar mensagem de erro com opção de tentar
novamente, conforme risco documentado em `docs/ARCHITECTURE.md` §7).

**Anônimo x logado:** o chat funciona sem login (cobre lead e cliente
esporádico, R10); ao estar logado, o backend já recebe o ID do usuário e
pode ligar a conversa ao histórico de pedidos — não é responsabilidade do
frontend decidir a classificação, apenas repassar o contexto de sessão
disponível.

## 4. Integração com o backend (contrato de API — rascunho)

O frontend fala apenas com a API REST do próprio backend (nunca diretamente
com os MCPs). Endpoints sugeridos como ponto de partida — refinar durante a
Fase 10/11 do `docs/ROADMAP.md`:

| Endpoint | Uso |
| --- | --- |
| `POST /api/chat/messages` | Envia mensagem (texto e/ou imagem e/ou áudio) de uma conversa; resposta é o próprio stream Server-Sent Events (SSE) da geração — não há endpoint `GET` separado |
| `GET /api/chat/conversations/{id}` | Recupera histórico/resumo da conversa (R9) |
| `GET /api/products` , `GET /api/products/{id}` | Catálogo de produtos (mesma base do RAG/MCP B2B) |
| `POST /api/orders` , `GET /api/orders/{id}` , `GET /api/orders` | Criação e histórico de pedidos |
| `POST /api/auth/login` , `POST /api/auth/signup` | Autenticação simplificada |
| `GET /api/appointments` | Lista agendamentos criados via chat (leitura) |
| `POST /api/rag/documents` | Upload de um PDF/texto (`multipart/form-data`: `file` + `domain` + `collection_id` opcional, default a collection ativa) para ingestão no RAG — usado pela página `/admin/ingestao` (ver `backend/src/app/api/rag.py`) |
| `GET /api/rag/documents` | Lista o registro de documentos ingeridos (mais recente primeiro), fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `DELETE /api/rag/documents/{document_id}` | Exclui um documento (registro + pontos no Qdrant), fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `POST /api/rag/documents/{document_id}/reingest` | Reingere um documento já enviado em outra collection (a partir do arquivo original salvo em disco), fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `GET /api/rag/documents/{document_id}/content` | Devolve o arquivo original do documento (PDF/TXT/MD/CSV, `FileResponse` com `Content-Disposition: inline`), usado pelo preview em `DocumentViewModal.tsx` (`/admin/ingestao`) — 404 se o documento ou o arquivo em disco não existir, fora do MVP original |
| `GET /api/rag/collections` | Lista os perfis de collection configurados, com contagem de documentos por collection, fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `POST /api/rag/collections` | Cria um novo perfil de collection (nome, modelo de embedding, chunking, HNSW, quantização, payload indexing) e a collection real correspondente no Qdrant, fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `POST /api/rag/collections/{collection_id}/activate` | Marca a collection como ativa (é a que o chat passa a usar na busca), fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `DELETE /api/rag/collections/{collection_id}` | Exclui a collection em cascata (documentos, pontos no Qdrant e arquivos em disco); bloqueado (409) se for a collection ativa, fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `POST /api/rag/playground/search` | Roda a mesma busca contra várias collections em paralelo e devolve resultados/latência por collection, para comparação manual, fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `GET /api/admin/local-models` | Lista os modelos locais já baixados no Ollama, com qual está ativo, fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `POST /api/admin/local-models/activate` | Troca em runtime qual modelo local o chat usa (só em memória, reseta no restart), fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `POST /api/admin/local-models/pull` | Dispara o download de um modelo (biblioteca do Ollama ou GGUF do Hugging Face) em background, sem bloquear o backend, fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |
| `GET /api/admin/local-models/pull-status` | Consulta o progresso de um download em andamento (query param `name`), usado em polling pelo frontend, fora do MVP original — ver `docs/ARCHITECTURE.md` §5 |

`POST /api/chat/messages` — contrato já implementado (Fase 2 para o request;
streaming SSE do response adicionado depois, ver decisão em
`docs/ARCHITECTURE.md` §5 "Streaming SSE do chat"; ver
`backend/src/app/api/chat.py` e `backend/src/app/models/chat.py`):

```jsonc
// Request
{
  "message": "Quero um orçamento para o produto X", // opcional se `audio` vier preenchido
  "conversation_id": "uuid-opcional, omitir para iniciar conversa nova",
  "audio": null // opcional, base64 (wav ou mp3) — processado via STT (R5) quando presente
}
```

A resposta (200) é o próprio stream: `Content-Type: text/event-stream`, uma
sequência de eventos SSE (`event: <tipo>\ndata: <json>\n\n`), nesta ordem:

```
event: conversation
data: {"conversation_id": "uuid-da-conversa"}

event: transcription        // só emitido quando o request trouxe `audio` e a transcrição não veio vazia
data: {"transcribed_message": "texto transcrito do áudio"}

event: status                // opcional, só quando o modelo escolhido ainda não está "quente"
data: {"status": "carregando_modelo"}

event: token                 // um evento por trecho de texto gerado, zero ou mais vezes
data: {"text": "trecho da resposta"}

event: done                  // sempre o último evento em caso de sucesso — telemetria completa
data: {
  "domain": "vendas",              // vendas | suporte | atendimento | agendamento | fora_escopo
  "backend_used": "local",         // local | externo
  "escalation_reason": "nenhum",   // nenhum | fora_escopo | rag_vazio | complexidade_alta

  // Telemetria de inferência (além do MVP original, a pedido explícito —
  // decisão registrada em docs/ARCHITECTURE.md §5). Todos opcionais
  // (`null` quando a métrica não se aplica ao caminho tomado).
  "model_name": "llama3.1:8b",
  "prompt_tokens": 128,
  "completion_tokens": 342,
  "latency_ms": 2500.0,
  "ttft_ms": 150.0,
  "tps": 190.0,
  "confidence": 0.92,
  "complexity": "baixa",
  "estimated_cost_usd": 0.0,
  "rag_retrieval_ms": 38.3,
  "rag_chunks_count": 3,
  "rag_avg_score": 0.71
}
```

O texto completo da resposta do assistente **não** vem em um campo único —
o cliente reconstrói concatenando o `text` de cada evento `token`, na ordem
em que chegam (é assim que a UI faz o efeito de "digitando"). O evento
`transcribed_message` continua sendo como o widget de chat exibe o texto
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
curtas (R3) é mantido em memória por processo no backend (últimas 1-3
mensagens por `conversation_id`), sem persistência em Postgres nem resumo
automático (isso é R9/Fase 6) — só é atualizado quando o evento `done`
chega com sucesso, não em caso de `error`.

**Estado atual do frontend (Fase 7/8, ver `docs/ROADMAP.md`):** o scaffold
Next.js foi criado em `frontend/` (App Router, TypeScript `strict`, Tailwind
CSS, ESLint + Prettier, Vitest + Testing Library) e o widget de chat consome
`POST /api/chat/messages` (`frontend/lib/api/chat.ts`) com **texto e áudio**.
`sendChatMessage` foi reescrito para consumir o contrato SSE descrito acima:
em vez de `response.json()`, faz o parsing manual de blocos `event:`/`data:`
do `ReadableStream` da resposta (não usa `EventSource`, que só suporta GET) e
entrega a resposta incrementalmente via callbacks — `onConversationId`,
`onTranscription`, `onStatus`, `onToken`, `onDone`, `onError` — retornando
`Promise<void>` em vez de um objeto de resposta único; nunca lança, erros de
rede/HTTP/stream viram chamada a `onError` (ver
`frontend/tests/lib/api/chat.test.ts`). `ChatModal.tsx` já consome essa
assinatura (Fase 8): acumula o texto dos eventos `token` numa bolha do
assistente criada sob demanda, exibe um texto de status temporário enquanto
o modelo local carrega (ver "Estados do widget" abaixo) e nunca deixa a
bolha vazia ou travada no placeholder — se `onDone` chegar sem nenhum token
(resposta vazia do modelo), o texto final vira um aviso de "sem resposta do
modelo, tente novamente" em vez de ficar em branco. Também sem upload de
imagem e sem cards ricos — essas partes dependem de
R6/R11/R12 no backend (ainda não implementados) e/ou de trabalho de UI ainda
não iniciado, e ficam para quando essas dependências existirem. Todas as
demais páginas listadas na Seção 2 (exceto `/suporte`, que já tem um FAQ
estático real) são *stubs* de navegação ("em construção"), sem nenhuma
chamada de API — a integração real com o catálogo, pedidos, autenticação e
agendamentos é tarefa futura de frontend, condicionada às respectivas APIs
existirem no backend.

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
explícito — decisão registrada em `docs/ARCHITECTURE.md` §5): quando há
pelo menos uma resposta do assistente na conversa, o `ChatModal` mostra um
painel com os campos de telemetria da resposta (`model_name`,
`prompt_tokens`/`completion_tokens`, `latency_ms`, `ttft_ms`, `tps`,
`estimated_cost_usd`, `rag_retrieval_ms`/`rag_chunks_count`/`rag_avg_score`)
e dois botões de exportação — CSV e JSON — que baixam as métricas de todas
as mensagens da conversa atual (`frontend/lib/utils/exportMetrics.ts`),
pensados para alimentar a avaliação experimental da Fase 10
(`docs/EVALUATION.md`), não como uma feature de produto para o usuário
final.

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
│   │   └── perfil/page.tsx
│   ├── agendamentos/page.tsx      # status de visitas agendadas
│   ├── suporte/page.tsx           # FAQ / central de ajuda
│   └── contato/page.tsx
├── components/
│   ├── chat/
│   │   ├── ChatWidget.tsx          # botão flutuante + estado aberto/fechado
│   │   ├── ChatModal.tsx           # modal de conversa (sobre ui/Modal.tsx)
│   │   ├── MessageBubble.tsx
│   │   ├── AudioRecorder.tsx
│   │   ├── ImageUploader.tsx
│   │   └── cards/                  # ProductCard, AppointmentCard, QuoteCard
│   ├── layout/                     # Header, Footer, Nav
│   └── ui/                         # botões, inputs, componentes genéricos
├── lib/
│   ├── api/                        # cliente HTTP para o backend
│   ├── hooks/                      # useChat, useConversation, useProducts...
│   └── types/                      # tipos compartilhados com o backend
├── public/
├── tests/
├── .env.example
└── package.json
```

Estado atual (Fase 7/8): `AudioRecorder.tsx` já existe (ver acima); `ImageUploader.tsx` e
`components/chat/cards/` ainda não existem (dependem de R6/R11/R12 no
backend). `lib/hooks/useChatStore.ts` contém o estado do widget via Zustand
(aberto/fechado, mensagens, `conversation_id`) — ainda não há `useConversation`
nem `useProducts` (sem dados de servidor além do chat nesta etapa). Os testes
de componente vivem em `tests/components/` (Vitest + Testing Library).

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
  pedido, login. Config em `playwright.config.ts` (só Chromium; `webServer`
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
  Existe também um **smoke test manual** (`frontend/tests/smoke/chat.smoke.spec.ts`,
  `npm run test:e2e:smoke`, config separada `playwright.smoke.config.ts`) que
  bate no backend e no Ollama reais, sem mock — exige os dois rodando
  localmente; não faz parte da suíte padrão (`npm run test:e2e`) por causa da
  dependência externa e da latência de LLM real.
- Lint/format: ESLint + Prettier, mesma disciplina de PRs pequenos descrita
  em `docs/CONVENTIONS.md`.

## 7. Rastreabilidade com os requisitos funcionais

| Requisito | Onde aparece no frontend |
| --- | --- |
| R1 (modelo local) | Transparente ao frontend — nenhuma UI específica |
| R2 (entrada multimodal) | Widget de chat: texto, upload de imagem, gravação de áudio |
| R3 (roteador) | Indicador de domínio no widget (opcional/demonstração) |
| R4 (RAG) | Card de produto no chat; conteúdo de `/produtos` e `/suporte` alimenta o RAG |
| R5 (STT) | `AudioRecorder` + exibição do texto transcrito |
| R6 (tratamento de imagem) | `ImageUploader`; card de produto como resultado de busca por imagem |
| R7 (domínios) | Indicador de domínio; páginas `/suporte`, `/produtos`, `/agendamentos` refletem os quatro domínios |
| R8 (monitor de tom) | Banner de transferência para atendente humano |
| R9 (memória da conversa) | ID de conversa persistido; retomada ao reabrir o widget |
| R10 (classificação do usuário) | Estado de login/anônimo repassado ao backend; sem UI própria |
| R11 (agendamento) | Card de confirmação no chat; página `/agendamentos` (leitura) |
| R12 (MCP B2B) | Card de cotação/reserva no chat quando o roteador aciona o MCP B2B para Vendas |

## 8. Fora de escopo do frontend no MVP

- Gateway de pagamento real — checkout do MVP pode simular o pagamento (ver
  também "fora de escopo" geral em `docs/ARCHITECTURE.md`/`docs/ROADMAP.md`).
- Reagendamento/cancelamento de visita pela UI (o backend também não suporta
  isso no MVP — ver `docs/ARCHITECTURE.md` §5).
- Notificações push, aplicativo mobile nativo, múltiplos idiomas.
- Painel administrativo para gestão de catálogo/estoque/preços — no MVP essa
  base é populada diretamente no banco (ver `docs/CONVENTIONS.md`), sem UI.

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
2026-09-14) com um registro/exclusão de documentos e uma aba de
configuração reservada para entregas futuras — ver
`docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md`.
