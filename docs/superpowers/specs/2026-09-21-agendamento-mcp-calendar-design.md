# Design — Agendamento via MCP Calendar (R11, Fase 4A)

> Spec resultante de sessão de brainstorm com o desenvolvedor em 2026-09-21.
> Cobre só a metade "Agendamento" da Fase 4 do roadmap (R11). O "Monitor de
> Tom" (R8: classificador de sentimento/urgência, alerta, transferência
> simulada, log) é um subsistema independente, decomposto para um ciclo de
> brainstorm/spec separado (Fase 4B), decisão tomada explicitamente com o
> desenvolvedor por não haver dependência técnica entre os dois.

## 1. Objetivo

Fechar R11 (`docs/ARCHITECTURE.md` linha 75): reconhecer a intenção de
agendamento de visita (o domínio `agendamento` já existe no roteador desde a
Fase 1 — `app.router.classifier.Domain` — mas hoje só tem um playbook que
conversa sem nunca criar o evento de verdade, ver
`app/router/playbooks.py::_AGENDAMENTO_PLAYBOOK`), coletar os dados
necessários ao longo da conversa e, com confirmação do visitante, criar o
evento na agenda da empresa via **MCP do Google Calendar**, com confirmação
automática por e-mail.

## 2. Decisão de arquitetura: qual MCP consumir

R11 pede que o assistente seja **cliente** de um MCP externo (não que a
empresa construa seu próprio servidor — isso é o papel do MCP B2B, R12, que é
o inverso). O Google publica um servidor MCP remoto oficial para Google
Calendar:

- Endpoint: `https://calendarmcp.googleapis.com/mcp/v1`
- Transporte: **Streamable HTTP**
- Auth: OAuth 2.0, cliente tipo "Web application" (client_id/client_secret)
- Tools relevantes expostas: `create_event`, `list_events`, `get_event`,
  `list_calendars`, `suggest_time`, entre outras (descoberta real via
  `tools/list` na implementação, não assumida aqui em detalhe de schema).

**Decisão:** consumir esse servidor remoto oficial, em vez de construir um
servidor MCP próprio que envolveria a API do Calendar. Construir nosso próprio
servidor só para satisfazer o desenho arquitetural do R11 replicaria, do lado
do servidor, exatamente o que o Google já publica de forma padronizada — sem
ganhar a interoperabilidade que é o motivo de existir do MCP. A alternativa
descartada (servidor MCP próprio + service account) foi cogitada por evitar o
fluxo de consentimento OAuth interativo, mas isso se resolve sem abrir mão do
MCP oficial (ver §3).

## 3. Autenticação: consentimento único, não por visitante

O caso de uso é um backend headless agendando numa **única agenda da
empresa** — não há usuário final logado para autenticar a cada visita. Em vez
do fluxo interativo pensado para apps como Claude Desktop/Gemini (um usuário
humano autentica a cada sessão), uso o padrão padrão de automação OAuth do
Google (`access_type=offline`): o **admin da empresa autoriza uma vez**, o
backend guarda o refresh token e o renova sozinho a partir daí.

- `backend/scripts/authorize_google_calendar.py` — script administrativo de
  uso único (fora do fluxo do chat): lê o client secrets JSON
  (`GOOGLE_CALENDAR_CREDENTIALS_PATH`, já existente em `.env.example`),
  inicia o fluxo de autorização, imprime a URL para o admin abrir no
  navegador, recebe o código de volta e troca por um refresh token, que salva
  em `GOOGLE_CALENDAR_TOKEN_PATH` (novo, ex.:
  `./secrets/google_calendar_token.json`).
- Em runtime, `GoogleCalendarMCPClient` lê o refresh token desse arquivo,
  troca por um access token de curta duração via
  `POST https://oauth2.googleapis.com/token` (grant_type=refresh_token) e o
  usa como `Authorization: Bearer <token>` nas chamadas Streamable HTTP ao
  MCP. Cache em memória do access token + expiração, renovando sob demanda
  (sem job de background — próxima chamada após expirar já renova).
- `GOOGLE_CALENDAR_CALENDAR_ID=primary` (já existente) continua valendo: é a
  agenda primária da conta que o admin autorizou.

`# MVP: consentimento único feito manualmente pelo admin via script de linha
de comando, sem UI de reautorização nem alerta automático de expiração do
refresh token — se o Google revogar o token, o erro aparece como falha de
autenticação do MCP (ver §6) e o admin reroda o script`.

## 4. Coleta de dados: máquina de estado em memória por conversa

Dados obrigatórios antes de criar o evento, confirmados com o desenvolvedor:
**data/hora desejada, nome do visitante, e-mail e telefone**.

Novo módulo `backend/src/app/router/scheduling.py`:

```python
class BookingSlots(BaseModel):
    data_hora: datetime | None = None
    nome: str | None = None
    email: str | None = None
    telefone: str | None = None
    awaiting_confirmation: bool = False

    def is_complete(self) -> bool:
        return all([self.data_hora, self.nome, self.email, self.telefone])
```

Guardado em memória por `conversation_id`, no mesmo padrão MVP já usado por
`_conversation_history` em `app/api/chat.py` (dict de processo, sem
persistência em banco — a persistência de conversa é Fase 6, ainda não
implementada). `# MVP: estado de agendamento perdido em restart do processo,
igual ao histórico de conversa — aceitável no protótipo`.

**Extração dos campos:** uma chamada LLM dedicada, no mesmo padrão de
`app.router.classifier._classify_with_llm` (prompt → JSON → parse com
`ValidationError`/`JSONDecodeError` tratado, mesmo strip de code fence via
`_strip_code_fence`). Recebe a mensagem atual, `recent_messages` e os slots já
conhecidos; devolve só os campos que conseguiu extrair desta mensagem (nunca
`null` sobrescrevendo um valor já coletado — o merge é "só substitui campos
não-nulos na resposta").

### 4.1. Fluxo dentro de `orchestrator.handle_message`

Novo ramo substituindo o `if classification.domain == "agendamento":
backend_escolhido = "local"` atual (`app/router/orchestrator.py:151`):

1. Recupera `BookingSlots` da conversa (ou cria vazio).
2. Roda a extração LLM, faz merge dos campos não-nulos nos slots.
3. **Slots incompletos** → playbook de agendamento (ajustado para saber o que
   já tem e o que falta) pede só os campos que faltam. Sem chamar o MCP.

   `Nota (implementação, revisão final): o "playbook de agendamento" acima
   não existe mais como prompt de sistema estático/LLM-gerado —
   `_AGENDAMENTO_PLAYBOOK` foi removido (commit `a529f2b`, "remove playbook
   morto") e substituído por templates de mensagem determinísticos em
   `scheduling.py` (`mensagem_campos_faltando`, `mensagem_pedir_confirmacao`,
   `mensagem_sucesso`, `MSG_ERRO_MCP`), montados sem chamada ao LLM. Mesmo
   motivo do §5: durante a coleta/confirmação de uma ação irreversível
   (criar um evento real na agenda), o risco de o LLM inventar/alucinar um
   detalhe (nome, data, e-mail) na resposta ao visitante não compensa a
   flexibilidade de um prompt gerado — ver decisão registrada em
   `docs/ARCHITECTURE.md` (Fase 4A).`
4. **Slots completos, ainda não validados** → antes de pedir confirmação,
   valida o horário (ver §4.3): fora do expediente/no passado, ou em
   conflito com outro evento já na agenda → explica o motivo, **limpa só
   `data_hora`** e volta ao passo 3 pedindo um novo horário (nome/e-mail/
   telefone já coletados continuam guardados). Passa na validação →
   segue para o passo 5.
5. **Slots completos e válidos, ainda não confirmados**
   (`awaiting_confirmation=False`) → assistente resume os dados coletados e
   pergunta explicitamente "posso confirmar?"; marca
   `awaiting_confirmation=True`. Sem chamar `create_event` ainda — decisão do
   desenvolvedor de sempre pedir uma confirmação explícita antes de criar o
   evento de verdade, para não agendar em cima de um dado mal interpretado
   (ex.: data extraída errado de áudio transcrito via STT).
6. **`awaiting_confirmation=True`** e a mensagem atual é interpretada como
   confirmação afirmativa (mesma chamada de extração do passo 2 também
   classifica isso, ver §4.2) → chama `GoogleCalendarMCPClient.create_event`
   (ver §5). Sucesso: confirma o agendamento, avisa que o convite chega por
   e-mail, **limpa os slots da conversa** (agendamento concluído). Falha: ver
   §6.
7. **`awaiting_confirmation=True`** mas a mensagem não é uma confirmação clara
   (quer mudar um dado, por exemplo) → volta a tratar como passo 2/3: extrai
   de novo, atualiza os slots que mudaram, `awaiting_confirmation` volta a
   `False` até nova confirmação (e, se `data_hora` mudou, revalida pelo
   passo 4 de novo).

### 4.2. Detecção de confirmação

O mesmo prompt de extração (§4) devolve também um campo
`confirmacao: bool | null` — `true` quando a mensagem é uma afirmação clara
("sim", "pode confirmar", "isso mesmo") no contexto de
`awaiting_confirmation=True` (informado no prompt), `null`/`false` caso
contrário. Evita uma segunda chamada LLM só para essa checagem.

### 4.3. Validação de horário (antes da confirmação)

Decisão do desenvolvedor: não confiar cegamente no horário que o visitante
pedir — validar expediente **e** conflito de agenda antes de sequer pedir
confirmação (revisando a ideia inicial deste spec, que deixava isso como
não-objetivo).

1. **Expediente** — checagem local, sem chamar o MCP: `data_hora` não pode
   estar no passado, precisa cair num dia útil e dentro do horário
   configurados (`AGENDAMENTO_EXPEDIENTE_DIAS`,
   `AGENDAMENTO_EXPEDIENTE_INICIO`, `AGENDAMENTO_EXPEDIENTE_FIM`, ver §8),
   interpretados no fuso `AGENDAMENTO_TIMEZONE`. Fora disso → mensagem
   explicando o expediente válido, pede outro horário.
2. **Conflito de agenda** — só roda se a checagem de expediente passou:
   `GoogleCalendarMCPClient.is_time_available(start, end)` (ver §5), que usa
   a tool `list_events` do MCP filtrada pela janela `[data_hora, data_hora +
   30min)`. Se houver qualquer evento nessa janela → horário indisponível,
   mesma mensagem/loop do passo 4. Se a chamada ao MCP falhar (conexão/auth)
   → mesmo tratamento de erro do §6 (não dá pra confirmar automaticamente
   agora), mesmo sem ainda estar em `awaiting_confirmation`.

`# MVP: checagem de conflito busca só na mesma agenda (GOOGLE_CALENDAR_CALENDAR_ID),
sem checar múltiplas agendas (explicitamente fora do MVP, ver CLAUDE.md); não
sugere automaticamente um horário alternativo livre (a tool suggest_time não
é usada) — o visitante propõe o próximo horário, o sistema só valida; existe
uma janela de corrida pequena entre esta checagem e a criação do evento no
passo 6 (dois visitantes confirmando quase ao mesmo tempo para o mesmo
horário) — aceitável no protótipo, sem lock/reserva temporária`.

## 5. `GoogleCalendarMCPClient`

Novo módulo `backend/src/app/mcp_client/google_calendar.py` (pasta já
existe, vazia, desde a Fase 0):

```python
class GoogleCalendarAuthError(Exception): ...
class GoogleCalendarConnectionError(Exception): ...

class GoogleCalendarMCPClient:
    async def is_time_available(self, start: datetime, end: datetime) -> bool:
        ...  # True se não houver nenhum evento na janela [start, end)

    async def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        attendee_email: str,
        attendee_name: str,
        description: str = "",
    ) -> str:  # retorna o link do evento (htmlLink) para incluir na resposta
        ...
```

`is_time_available` chama a tool `list_events` (filtrando por
`GOOGLE_CALENDAR_CALENDAR_ID` e a janela `[start, end)`) e devolve `True`
quando a lista vier vazia — usada na validação de horário (§4.3), antes da
etapa de confirmação.

- Usa o SDK oficial `mcp` (já em `backend/pyproject.toml`, `mcp>=1.0`) com
  transporte Streamable HTTP (`mcp.client.streamable_http`) apontando para
  `https://calendarmcp.googleapis.com/mcp/v1`, header `Authorization` com o
  access token renovado (§3).
- Chama a tool `create_event` via `ClientSession.call_tool(...)`, passando um
  convidado com o e-mail/nome do visitante e notificação ativada — é o
  Google Calendar que dispara o e-mail de confirmação/convite, **sem
  infraestrutura de e-mail própria** (SMTP, templates) — decisão do
  desenvolvedor: reaproveitar o mecanismo nativo do Calendar em vez de
  construir e manter um subsistema de e-mail só para isso. Os nomes exatos
  dos parâmetros da tool (`attendees`, formato de convidado, campo de
  notificação) são confirmados via `tools/list` na implementação (§2 já
  registra que o schema não é assumido aqui) e mapeados no corpo do
  `call_tool`.
- `scheduling.py` (não o client) calcula `end = data_hora + 30min` quando
  chama `create_event` — o playbook não pergunta duração da visita, mantendo
  a coleta enxuta (§4). `create_event` recebe `start`/`end` já prontos, sem
  default interno.
- Erros de rede/timeout na chamada Streamable HTTP → `GoogleCalendarConnectionError`.
  Erros de token (refresh revogado, 401/403 da troca de token ou da chamada)
  → `GoogleCalendarAuthError`. Orchestrator trata as duas do mesmo jeito (§6),
  a distinção existe só para o log estruturado.

## 6. Tratamento de erro (parte de R11: "sugerir nova tentativa ou
transferir para atendente")

Ao chamar `create_event` (passo 5 do fluxo), qualquer
`GoogleCalendarAuthError`/`GoogleCalendarConnectionError`:

- Log estruturado, mesmo padrão de `rag_indisponivel`/`backend_indisponivel`
  em `orchestrator.py`: evento `google_calendar_indisponivel`, com o tipo de
  erro (`auth` vs `conexao`).
- Resposta ao visitante: mensagem clara de que não foi possível confirmar
  automaticamente agora, e que um atendente vai entrar em contato para
  confirmar manualmente (`# MVP: sem fila de atendimento real — é só a
  mensagem + o log estruturado, que o admin pode acompanhar; integração real
  com fila humana é fora do MVP, ver docs/ARCHITECTURE.md §5`).
- `awaiting_confirmation` volta a `False`, mas os **slots continuam
  guardados** — o visitante não precisa redigitar data/nome/e-mail/telefone
  para tentar de novo, só confirmar de novo numa mensagem seguinte (retoma no
  passo 4 do fluxo). Mesmo espírito do botão "Tentar novamente" já existente
  no chat para erro de rede do `POST /api/chat/messages` (Fase 8), mas aqui é
  o próprio fluxo de conversa que permite a nova tentativa, sem botão
  dedicado no frontend.

## 7. Testes

Backend (pytest, mesmo padrão de mock usado para `OllamaClient`/
`OpenRouterClient` — sem rede real, sem credenciais reais em CI):

- `scheduling.py`: extração de slots parcial (só alguns campos vêm na
  mensagem) e merge preservando campos já coletados; detecção de confirmação
  afirmativa vs. mensagem ambígua; resposta LLM não-JSON cai em fallback sem
  quebrar o turno (mesmo espírito de `_classify_heuristic_fallback`, mas aqui
  o fallback é "trata como não extraído, pergunta de novo" — não há
  heurística de agendamento por regex).
- `orchestrator.py`: os ramos do fluxo (§4.1/§4.3) — slots incompletos,
  horário fora do expediente/no passado (limpa `data_hora`, mantém o resto),
  horário em conflito de agenda (mesma limpeza), horário válido pede
  confirmação, confirmação afirmativa cria evento, resposta ambígua durante
  `awaiting_confirmation` volta a extrair, sucesso limpa slots, falha do MCP
  (na checagem de disponibilidade ou na criação) mantém slots e reseta
  `awaiting_confirmation`.
- `google_calendar.py`: `GoogleCalendarMCPClient` com `ClientSession`/
  transporte mockados — `is_time_available` com janela livre/ocupada,
  `create_event` bem-sucedido (parâmetros corretos, incluindo convidado),
  refresh de token expirado, erro de conexão vira
  `GoogleCalendarConnectionError`, erro de auth vira `GoogleCalendarAuthError`
  (para os dois métodos).

`eval/` (Fase 10) não é tocado por esta entrega — mede qualidade/latência,
não corretude funcional (`docs/CONVENTIONS.md`).

## 8. Mudanças em `.env.example`

```
# --- MCP cliente: Google Calendar (R11) ---
GOOGLE_CALENDAR_CREDENTIALS_PATH=./secrets/google_calendar_credentials.json
GOOGLE_CALENDAR_TOKEN_PATH=./secrets/google_calendar_token.json   # novo
GOOGLE_CALENDAR_CALENDAR_ID=primary

# --- Validação de horário do agendamento (R11) --- # novo
AGENDAMENTO_TIMEZONE=America/Sao_Paulo
AGENDAMENTO_EXPEDIENTE_DIAS=seg-sex
AGENDAMENTO_EXPEDIENTE_INICIO=09:00
AGENDAMENTO_EXPEDIENTE_FIM=18:00
```

`GOOGLE_CALENDAR_CREDENTIALS_PATH` já existia (placeholder de uma sessão
anterior); `GOOGLE_CALENDAR_TOKEN_PATH` é novo, para o refresh token gerado
pelo script de autorização (§3). As quatro variáveis de expediente (novas)
alimentam a validação do §4.3. Nenhum segredo real entra em `.env.example`
nem em commit — só os caminhos de arquivo e configuração de expediente,
seguindo o padrão já usado pelo resto do projeto (`docs/CONVENTIONS.md`).

## 9. Não-objetivos explícitos (fora desta entrega)

- Monitor de tom (R8) — subsistema independente, spec própria (Fase 4B).
- Reagendamento/cancelamento de visita — explicitamente fora do MVP
  (`CLAUDE.md`, `docs/ROADMAP.md`).
- Sugestão automática de horário alternativo livre (`suggest_time`) — quando
  o horário pedido é inválido/indisponível, o sistema só explica o motivo e
  pede que o visitante proponha outro; não busca proativamente um horário
  livre. Simplificação consciente de escopo, não esquecimento.
- Checagem de disponibilidade em múltiplas agendas — só a agenda configurada
  em `GOOGLE_CALENDAR_CALENDAR_ID`, explicitamente fora do MVP
  (`CLAUDE.md`).
- Reserva/lock temporário do horário durante a janela entre a checagem de
  disponibilidade e a criação do evento — risco de corrida pequeno, aceito
  no protótipo (ver nota de MVP em §4.3).
- Confirmação por SMS — só e-mail, via o próprio Google Calendar (§5).
- Servidor MCP próprio para Calendar — decisão de consumir o oficial do
  Google (§2).
- Reautenticação automática/alerta de expiração do refresh token — script
  manual do admin (§3).
