# 🧪 Guia de Teste Manual — Agendamento de Visitas (R11 / MCP Google Calendar)

Este documento é o **Guia de Teste Manual** para validação ponta a ponta da funcionalidade de **Agendamento de Visitas** (Requisito `R11`, Fase 4A do projeto).

Ele descreve os pré-requisitos de ambiente, os cenários de teste passo a passo e as formas de verificação de resultados no Chat UI, nos logs do Backend FastAPI e no Google Calendar.

---

## 📋 1. Visão Geral do Fluxo

O agendamento é orquestrado via máquina de estados (`backend/src/app/router/scheduling.py`) integrada ao **MCP do Google Calendar via `calendar-mcp-server`** — um servidor MCP de terceiro self-hosted (`http://127.0.0.1:8090/mcp` local), não mais o MCP oficial remoto do Google (trocado em 2026-09-23, ver nota abaixo e `docs/ARCHITECTURE.md` §5).

O assistente coleta **4 campos obrigatórios**:
1. 📅 **Data e Hora desejadas** (validada contra o expediente configurado e disponibilidade na agenda)
2. 👤 **Nome do visitante**
3. 📧 **E-mail do visitante**
4. 📞 **Telefone de contato**

### Regras de Negócio Importantes:
* **Expediente padrão**: Segunda a Sexta-feira, das 09:00 às 18:00 (Fuso `America/Sao_Paulo`).
* **Validação de Conflito**: O sistema consulta a agenda via MCP `list_events` antes de pedir confirmação.
* **Confirmação Explícita**: Nenhum evento é criado no Google Calendar sem antes pedir e receber um "Sim / Pode confirmar" do usuário.
* **Envio de E-mail**: A notificação por e-mail é disparada nativamente pelo Google Calendar (`sendUpdates: "all"`).

---

## ⚙️ 2. Pré-Requisitos e Configuração do Ambiente

> **Atualizado em 2026-09-23:** o MCP consumido deixou de ser o MCP oficial
> do Google (`calendarmcp.googleapis.com`, em Developer Preview e sem
> suporte a contas Gmail pessoais) — agora é o MCP de terceiro self-hosted
> `calendar-mcp-server` (https://github.com/deciduus/calendar-mcp), rodando
> localmente. Ver decisão em `docs/ARCHITECTURE.md` §5.

### 2.1. Variáveis de Ambiente (`.env`)
Certifique-se de que o arquivo `backend/.env` contém as configurações do agendamento (consulte `backend/.env.example` se necessário):

```bash
# URL do calendar-mcp-server local (ver 2.2 para como subir esse processo)
CALENDAR_MCP_URL=http://127.0.0.1:8090/mcp
GOOGLE_CALENDAR_CALENDAR_ID=primary

# Regras de Expediente
AGENDAMENTO_TIMEZONE=America/Sao_Paulo
AGENDAMENTO_EXPEDIENTE_DIAS=seg-sex
AGENDAMENTO_EXPEDIENTE_INICIO=09:00
AGENDAMENTO_EXPEDIENTE_FIM=18:00
```

### 2.2. Autorização OAuth Única e Subida do `calendar-mcp-server`
Se `backend/secrets/calendar_mcp_token.json` ainda não existe:

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/), crie um projeto e ative a **Google Calendar API**.
2. Crie uma credencial de OAuth 2.0, Client ID do tipo **"App para computador"** ("Desktop app" — obrigatório, é o único tipo compatível com o fluxo de autorização local do `calendar-mcp-server`), e baixe o arquivo `json` salvando em `backend/secrets/google_calendar_credentials.json`.
3. Na tela de consentimento OAuth do mesmo projeto, adicione sua conta Google em **"Usuários de teste"** (obrigatório enquanto o app não passa pela verificação do Google).
4. No terminal, autorize (uma vez só):
   ```bash
   cd backend
   export GOOGLE_CLIENT_ID=$(python3 -c "import json; d=json.load(open('secrets/google_calendar_credentials.json')); b=d.get('installed') or d.get('web'); print(b['client_id'])")
   export GOOGLE_CLIENT_SECRET=$(python3 -c "import json; d=json.load(open('secrets/google_calendar_credentials.json')); b=d.get('installed') or d.get('web'); print(b['client_secret'])")
   export TOKEN_FILE_PATH=./secrets/calendar_mcp_token.json
   uvx calendar-mcp-server auth
   ```
   Abra a URL gerada no navegador, selecione a conta Google, conceda a permissão.
5. Suba o servidor MCP local, em um terminal separado (precisa continuar rodando enquanto o backend estiver em uso):
   ```bash
   cd backend
   export GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=...  # mesmos valores do passo 4
   export TOKEN_FILE_PATH=./secrets/calendar_mcp_token.json
   uvx calendar-mcp-server serve --transport http --port 8090
   ```

### 2.3. Inicialização dos Serviços
Inicie o `calendar-mcp-server` (passo 2.2.5, terminal próprio), depois o Backend e o Frontend:

```bash
# Terminal 1: calendar-mcp-server (ver 2.2.5)

# Terminal 2: Backend FastAPI
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 3: Frontend Next.js
cd frontend
npm run dev
```

Acesse o site em `http://localhost:3000` e abra o widget do assistente de chat no canto inferior direito.

---

## 🧪 3. Matriz de Casos de Teste (Cenários Manuais)

---

### 🟢 CT-01: Fluxo Feliz (Agendamento Completo em Mensagem Única)

* **Objetivo**: Garantir que o assistente extrai todos os dados de uma só vez, pede confirmação e cria o evento.
* **Pré-condição**: Escolher um dia útil futuro (ex.: próxima terça-feira às 14:00).

| Passo | Ação do Usuário | Resposta Esperada do Assistente |
| :--- | :--- | :--- |
| **1** | *"Gostaria de agendar uma visita comercial para terça-feira que vem às 14h. Meu nome é Carlos Silva, e-mail carlos.silva@email.com e telefone (11) 98888-7777."* | Resumo dos dados coletados + pedido de confirmação: *"Só confirmando antes de agendar: visita em DD/MM/YYYY às 14:00, em nome de Carlos Silva, e-mail carlos.silva@email.com, telefone (11) 98888-7777. Posso confirmar?"* |
| **2** | *"Sim, pode confirmar!"* | Mensagem de sucesso: *"Prontinho! Sua visita foi agendada para DD/MM/YYYY às 14:00. Você vai receber a confirmação por e-mail em carlos.silva@email.com."* |

#### Verificação de Resultados:
- [ ] Checar no **Google Calendar** da conta autenticada se o evento foi criado no dia/horário com duração de 30 minutos.
- [ ] Checar se a caixa de e-mail `carlos.silva@email.com` (ou e-mail real de teste) recebeu o convite do Google Calendar.

---

### 🟡 CT-02: Coleta Gradual de Dados (Preenchimento em Múltiplos Turnos)

* **Objetivo**: Verificar se a máquina de estados acumula os slots entre as mensagens sem perder informações já ditas.

| Passo | Ação do Usuário | Resposta Esperada do Assistente |
| :--- | :--- | :--- |
| **1** | *"Quero agendar uma visita à empresa."* | Pergunta pelos campos que faltam: *"Para agendar sua visita, ainda preciso de: a data e o horário desejados para a visita, seu nome, seu e-mail e seu telefone."* |
| **2** | *"Meu nome é Maria Oliveira e meu e-mail é maria@empresa.com"* | Reconhece o nome e e-mail e pede o restante: *"Para agendar sua visita, ainda preciso de: a data e o horário desejados para a visita e seu telefone."* |
| **3** | *"Pode ser quinta-feira às 10h? Meu telefone é 11977776666"* | Detecta que todos os dados foram informados e pede confirmação resumindo tudo. |
| **4** | *"Isso mesmo, pode marcar."* | Confirma o agendamento no Google Calendar e finaliza o atendimento. |

---

### 🔴 CT-03: Validação de Expediente (Data no Passado ou Fora do Horário)

* **Objetivo**: Garantir que horários inválidos são rejeitados **antes** da etapa de confirmação, mantendo o nome/e-mail/telefone salvos.

#### Cenário 3A: Horário no Passado
1. **Usuário**: *"Quero agendar uma visita em nome de João, joao@email.com, 11999990000 para ontem às 14h."*
2. **Resposta Esperada**: *"Esse horário já passou. Pode sugerir uma data e hora futuras?"*

#### Cenário 3B: Final de Semana (Sábado/Domingo)
1. **Usuário**: *"Pode ser neste domingo às 10h?"*
2. **Resposta Esperada**: *"Nosso expediente inclui apenas seg-sex. Pode escolher outro dia?"*

#### Cenário 3C: Fora do Horário de Atendimento (ex: 20:00)
1. **Usuário**: *"Quero marcar para próxima quarta-feira às 20:00."*
2. **Resposta Esperada**: *"Nosso expediente para visitas é das 09:00 às 18:00. Pode escolher outro horário nessa faixa?"*

#### Recuperação no CT-03:
3. **Usuário**: *"Entendi, então marca para quarta-feira às 15:00."*
4. **Resposta Esperada**: O assistente deve recuperar o nome (`João`), e-mail (`joao@email.com`) e telefone (`11999990000`) já coletados e pedir confirmação para a nova data (quarta às 15h) **sem pedir que o usuário digite seus dados novamente**.

---

### 🟠 CT-04: Validação de Conflito de Agenda (Double-Booking)

* **Objetivo**: Testar se a verificação via MCP `list_events` impede o agendamento em horário ocupado.

#### Procedimento de Teste:
1. Abra o seu **Google Calendar** manualmente e crie um evento genérico na **próxima sexta-feira das 11:00 às 11:30**.
2. No chat do assistente, tente agendar uma visita exatamente para esse horário:
   - **Usuário**: *"Quero agendar uma visita para próxima sexta-feira às 11:00. Nome Lucas, lucas@email.com, tel 11911112222."*
3. **Resposta Esperada**: O assistente detecta a ocupação e responde informando que o horário está indisponível, solicitando outra sugestão de horário.

---

### 🔵 CT-05: Alteração de Dados Durante a Etapa de Confirmação

* **Objetivo**: Verificar a flexibilidade da máquina de estado quando o usuário corrige algum dado antes de finalizar.

| Passo | Ação do Usuário | Resposta Esperada do Assistente |
| :--- | :--- | :--- |
| **1** | *"Agendar visita para sexta às 15h. Nome Pedro, pedro@email.com, 11922223333."* | *"Só confirmando antes de agendar: visita em DD/MM/YYYY às 15:00, em nome de Pedro, e-mail pedro@email.com, telefone 11922223333. Posso confirmar?"* |
| **2** | *"Não, altera o e-mail para pedro.novo@email.com"* | O assistente atualiza o slot de e-mail e gera uma nova pergunta de confirmação com o e-mail atualizado. |
| **3** | *"Agora sim, pode agendar!"* | Evento criado com o e-mail corrigido `pedro.novo@email.com`. |

---

### 🟣 CT-06: Tratamento de Falhas e Indisponibilidade do MCP

* **Objetivo**: Confirmar que falhas de conexão ou credenciais do Google Calendar são tratadas graciosamente.

#### Procedimento de Teste (Simulação de Erro):
1. Renomeie temporariamente o arquivo de token `backend/secrets/google_calendar_token.json` para `google_calendar_token.json.bak`.
2. No chat, execute um fluxo completo de agendamento e confirme.
3. **Resposta Esperada**:
   - O assistente responde com a mensagem de fallback amigável:
     > *"No momento não consegui confirmar o agendamento automaticamente. Um atendente da nossa equipe vai entrar em contato para confirmar os detalhes. Pedimos desculpas pelo transtorno."*
   - O backend registra o log estruturado contendo `google_calendar_indisponivel` (tipo `auth`).
4. **Restauração**: Restaure o arquivo `google_calendar_token.json`. Ao enviar "Tentar novamente" ou confirmar na mensagem seguinte, o fluxo deve ser concluído com sucesso.

---

## 📊 4. Checklist de Verificação e Evidências

Ao concluir os testes manuais, valide as seguintes evidências:

- [ ] **Chat UI**: Nenhuma resposta gerada contém alucinação de dados (os dados confirmados batem 100% com o que o usuário forneceu).
- [ ] **Google Calendar UI**: O evento aparece com o título "Visita Comercial - [Nome do Visitante]", início no horário agendado, término 30 minutos depois, e descrição contendo o telefone de contato.
- [ ] **E-mail de Convite**: O e-mail informado no chat recebe o convite oficial do Google Calendar.
- [ ] **Logs do Backend**: No terminal do FastAPI, observar logs indicando a transição de slots e a execução da tool MCP `create_event`.

---

## 🛠️ 5. Resolução de Problemas Comuns (Troubleshooting)

* **Erro `GoogleCalendarConnectionError` ("MCP do Google Calendar indisponível")**:
  * Confirme que o `calendar-mcp-server` está rodando (`curl http://127.0.0.1:8090/mcp` deve responder — `400` é normal para um `GET` simples, só confirma que o processo está no ar; timeout/conexão recusada indica que ele não está rodando, ver `goup.md`).
  * Se o processo está no ar mas mesmo assim falha: o token pode ter sido revogado/expirado. Execute novamente `calendar-mcp-server auth` (mesmos `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`/`TOKEN_FILE_PATH` do passo 2.2).
* **Fuso Horário Incorreto**:
  * Caso a hora no Google Calendar apareça deslocada (ex.: 3 horas a mais ou a menos), confirme se `AGENDAMENTO_TIMEZONE=America/Sao_Paulo` está definido no `.env`.
* **Perda do Estado de Agendamento**:
  * Lembre-se que o estado dos slots é armazenado **em memória no processo do Backend** (MVP). Se você reiniciar o servidor Uvicorn durante um teste no meio da conversa, os dados coletados naquela sessão serão limpos.
