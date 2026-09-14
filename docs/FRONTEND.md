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

Todas as páginas compartilham `layout.tsx`, que inclui o widget de chat — ele
deve estar disponível em qualquer rota, inclusive durante o checkout.

## 3. Widget de chat (peça central da interface)

**Comportamento geral:** botão flutuante no canto inferior direito, presente
em todas as páginas; ao clicar, abre um painel (mobile: tela cheia; desktop:
painel lateral). O ID de conversa (R9) é gerado no primeiro envio e
persistido em `localStorage` (usuário anônimo) ou associado ao usuário
logado, permitindo retomar a conversa entre sessões/páginas.

**Entrada multimodal (R2):**
- Campo de texto padrão.
- Botão de upload/drag-and-drop de imagem (uso espontâneo ou dirigido, ver
  `docs/ARCHITECTURE.md` §4) — preview da imagem antes de enviar.
- Botão de gravação de áudio (push-to-talk ou toggle) com indicador visual de
  gravação — o áudio é enviado ao backend para STT (R5); exibir o texto
  transcrito na bolha do usuário assim que disponível.

**Exibição de mensagens:**
- Bolhas de texto padrão para usuário e assistente.
- Indicador de "digitando"/streaming enquanto a resposta chega via SSE.
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
| `POST /api/chat/messages` | Envia mensagem (texto e/ou imagem e/ou áudio) de uma conversa; retorna a resposta (ou inicia o stream) |
| `GET /api/chat/stream/{conversation_id}` (SSE) | Stream da resposta do assistente em geração |
| `GET /api/chat/conversations/{id}` | Recupera histórico/resumo da conversa (R9) |
| `GET /api/products` , `GET /api/products/{id}` | Catálogo de produtos (mesma base do RAG/MCP B2B) |
| `POST /api/orders` , `GET /api/orders/{id}` , `GET /api/orders` | Criação e histórico de pedidos |
| `POST /api/auth/login` , `POST /api/auth/signup` | Autenticação simplificada |
| `GET /api/appointments` | Lista agendamentos criados via chat (leitura) |

`POST /api/chat/messages` — contrato já implementado (Fase 2, texto apenas;
ver `backend/src/app/api/chat.py` e `backend/src/app/models/chat.py`):

```jsonc
// Request
{
  "message": "Quero um orçamento para o produto X",
  "conversation_id": "uuid-opcional, omitir para iniciar conversa nova",
  "audio": null // MVP: campo reservado, aceito mas não processado (STT pendente)
}

// Response (200)
{
  "conversation_id": "uuid-da-conversa",
  "message": "texto da resposta do assistente",
  "domain": "vendas", // vendas | suporte | atendimento | agendamento | fora_escopo
  "backend_used": "local", // local | externo
  "escalation_reason": "nenhum" // nenhum | fora_escopo | rag_vazio | complexidade_alta
}
```

MVP desta primeira versão do endpoint: resposta síncrona (JSON), sem
streaming/SSE (`GET /api/chat/stream/{conversation_id}` continua tarefa da
Fase 8, frontend); o campo `audio` é aceito no schema mas ignorado — o STT
(R5) ainda não existe (ver `backend/src/app/stt/`); o histórico usado para
resolver confirmações curtas (R3) é mantido em memória por processo no
backend (últimas 1-3 mensagens por `conversation_id`), sem persistência em
Postgres nem resumo automático (isso é R9/Fase 6).

**Estado atual do frontend (Fase 7/8, ver `docs/ROADMAP.md`):** o scaffold
Next.js foi criado em `frontend/` (App Router, TypeScript `strict`, Tailwind
CSS, ESLint + Prettier, Vitest + Testing Library) e o widget de chat consome
`POST /api/chat/messages` (`frontend/lib/api/chat.ts`) na versão **texto
apenas / síncrona**: sem upload de imagem, sem gravação de áudio, sem
streaming (SSE) e sem cards ricos — essas partes dependem de R5/R6/R11/R12 no
backend, ainda não implementados, e ficam para quando essas dependências
existirem. Todas as demais páginas listadas na Seção 2 (exceto `/suporte`,
que já tem um FAQ estático real) são *stubs* de navegação ("em construção"),
sem nenhuma chamada de API — a integração real com o catálogo, pedidos,
autenticação e agendamentos é tarefa futura de frontend, condicionada às
respectivas APIs existirem no backend.

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
│   │   ├── ChatPanel.tsx           # painel de conversa
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

Estado atual (Fase 7/8): `AudioRecorder.tsx`, `ImageUploader.tsx` e
`components/chat/cards/` ainda não existem (dependem de R5/R6/R11/R12 no
backend). `lib/hooks/useChatStore.ts` contém o estado do widget via Zustand
(aberto/fechado, mensagens, `conversation_id`) — ainda não há `useConversation`
nem `useProducts` (sem dados de servidor além do chat nesta etapa). Os testes
de componente vivem em `tests/components/` (Vitest + Testing Library).

## 6. Convenções específicas de frontend

- TypeScript em modo `strict`; evitar `any` — tipar as respostas do backend.
- Componentes pequenos e focados; o `ChatPanel` deve orquestrar
  subcomponentes (`MessageBubble`, `cards/*`), não conter toda a lógica.
- Mobile-first: o widget de chat precisa funcionar bem em telas pequenas
  (é o principal ponto de contato do usuário com o produto do TCC).
- Acessibilidade básica: labels em inputs, navegação por teclado no widget de
  chat, `aria-live` na área de mensagens para leitores de tela acompanharem o
  streaming.
- Testes: **Vitest + Testing Library** para componentes (ex.: `MessageBubble`
  renderiza cards corretamente); **Playwright** para os fluxos E2E críticos —
  enviar mensagem de texto, enviar imagem, fluxo de pedido, login. Config em
  `playwright.config.ts` (só Chromium; `webServer` reaproveita `npm run dev`
  se já estiver rodando). `# MVP: os testes E2E do chat mockam
  POST /api/chat/messages via page.route em vez de depender do backend e do
  modelo local (Ollama) reais — cobre o comportamento da UI (envio, exibição
  de resposta, erro/retry); integração real contra o backend fica para os
  testes de integração da Fase 9` — ver `frontend/tests/e2e/chat.spec.ts`.
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
