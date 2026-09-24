# goup — subir a aplicação completa

Comandos para derrubar processos antigos presos nas portas do projeto e subir
tudo de novo, limpo. Rode a partir da raiz do repositório
(`/home/augusto/Projetos/TCC`).

> **Dica de paste:** se seu terminal embaralha comandos colados em várias
> linhas (as quebras de linha somem), cole **um bloco de cada vez** (cada
> bloco abaixo já é uma linha única encadeada com `&&`/`;`), ou copie o bloco
> inteiro da seção "Tudo de uma vez" para um arquivo e rode com `bash`.

## Portas usadas

| Serviço | Porta | Gerenciado por |
| --- | --- | --- |
| Backend (FastAPI/uvicorn) | 8000 | processo solto (`.venv`) |
| Frontend (Next.js) | **3001** | processo solto (`npm run dev`) |
| **calendar-mcp-server (MCP do agendamento)** | **8090** | processo solto (`uvx calendar-mcp-server`) |
| **mcp-b2b-server (MCP B2B provido — catálogo/estoque/preços/manuais)** | **8100** | processo solto (`.venv`, `scripts/run_mcp_b2b_server.py`) |
| Postgres | 5433 | Docker (`backend/docker-compose.yml`) |
| Qdrant | 6335 / 6336 | Docker (`backend/docker-compose.yml`) |
| Ollama | 11434 | serviço do sistema (`ollama serve`) |

> **Novo desde 2026-09-23:** o agendamento de visita (R11) não fala mais
> direto com o MCP do Google — fala com um MCP de terceiro self-hosted
> (`calendar-mcp-server`) rodando localmente na porta 8090. Sem ele no ar,
> o backend sobe normal (conexão é lazy), mas qualquer mensagem de
> agendamento falha com "MCP do Google Calendar indisponível". Ver
> `docs/ARCHITECTURE.md` §5 e `docs/GUIA_TESTE_AGENDAMENTO.md` §2.2 para
> detalhes de autenticação (só precisa rodar `calendar-mcp-server auth`
> uma vez; depois disso só `calendar-mcp-server serve` a cada sessão).

> **Novo desde 2026-09-24:** o MCP B2B provido pela empresa (R12, Fase 5 —
> catálogo, estoque, preços e manuais, recursos de leitura) sobe como
> processo próprio na porta 8100 (`scripts/run_mcp_b2b_server.py`), mesmo
> padrão do `calendar-mcp-server` acima, mas código deste projeto (não um
> pacote de terceiro). Sem ele no ar, backend/frontend sobem normal — o MCP
> B2B só é consultado por integradores/IAs de parceiros externas ao chat
> (uso interno, sem autenticação por parceiro — ver `docs/ARCHITECTURE.md`
> §5/§6).

> ⚠️ **Não usamos a porta 3000** — nesta máquina ela já é ocupada pelo
> **Open WebUI**, um serviço separado que não é deste projeto. O frontend
> deste projeto sobe na **3001**, e o backend já está configurado para
> aceitar CORS de `http://localhost:3001` (default de `CORS_ALLOWED_ORIGIN`
> tanto em `.env.example` quanto em `config.py`; pode ser sobrescrito no
> `backend/.env` local, não commitado). **Nunca derrube nada na porta 3000.**

Só backend e frontend costumam precisar ser "derrubados" manualmente — Docker
e Ollama normalmente já ficam de pé entre sessões.

## 1. Derrubar processos antigos do projeto (portas 8000, 3001, 8090 e 8100)

```bash
fuser -k 8000/tcp 2>/dev/null; fuser -k 3001/tcp 2>/dev/null; fuser -k 8090/tcp 2>/dev/null; fuser -k 8100/tcp 2>/dev/null; sleep 1; echo "portas 8000/3001/8090/8100 liberadas"
```

Se `fuser` não existir na sua máquina, alternativa com `lsof`:

```bash
lsof -ti:8000 | xargs -r kill; lsof -ti:3001 | xargs -r kill; lsof -ti:8090 | xargs -r kill; lsof -ti:8100 | xargs -r kill; sleep 1; echo "portas 8000/3001/8090/8100 liberadas"
```

Conferir se ficou algo preso:

```bash
ss -ltnp 2>/dev/null | grep -E ':(8000|3001|8090|8100)\s' || echo "nada escutando em 8000/3001/8090/8100"
```

## 2. Garantir a infraestrutura (Docker + Ollama) no ar

```bash
cd backend && docker compose up -d postgres qdrant && cd ..
```

```bash
curl -s -o /dev/null -w "ollama: %{http_code}\n" --max-time 3 http://localhost:11434/api/tags || echo "ollama não respondeu — rode 'ollama serve' em outro terminal"
```

## 3. Aplicar migrações pendentes do banco

```bash
cd backend && .venv/bin/alembic upgrade head && cd ..
```

## 4. Subir o calendar-mcp-server (porta 8090, em background)

Precisa do `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` (mesmas credenciais
"Desktop app" já usadas) e de já ter rodado `calendar-mcp-server auth` uma
vez (gera `backend/secrets/calendar_mcp_token.json` — ver
`docs/GUIA_TESTE_AGENDAMENTO.md` §2.2 se ainda não fez isso):

```bash
cd backend
export GOOGLE_CLIENT_ID=$(python3 -c "import json; d=json.load(open('secrets/google_calendar_credentials.json')); b=d.get('installed') or d.get('web'); print(b['client_id'])")
export GOOGLE_CLIENT_SECRET=$(python3 -c "import json; d=json.load(open('secrets/google_calendar_credentials.json')); b=d.get('installed') or d.get('web'); print(b['client_secret'])")
export TOKEN_FILE_PATH=./secrets/calendar_mcp_token.json
nohup uvx calendar-mcp-server serve --transport http --port 8090 > /tmp/tcc-calendar-mcp.log 2>&1 & disown
cd ..
```

Sem ele no ar, backend/frontend sobem normal — só mensagens de agendamento
no chat falham (`GoogleCalendarConnectionError`).

## 4b. Subir o mcp-b2b-server (porta 8100, em background)

```bash
cd backend && nohup .venv/bin/python scripts/run_mcp_b2b_server.py > /tmp/tcc-mcp-b2b.log 2>&1 & disown; cd ..
```

Sem ele no ar, backend/frontend sobem normal — é um serviço à parte, só
consultado por integradores/IAs de parceiros externas ao chat.

## 5. Subir o backend (porta 8000, em background)

```bash
cd backend && nohup .venv/bin/uvicorn src.app.main:app --host 0.0.0.0 --port 8000 > /tmp/tcc-backend.log 2>&1 & disown; cd ..
```

## 6. Subir o frontend (porta 3001, em background)

```bash
cd frontend && PORT=3001 nohup npm run dev > /tmp/tcc-frontend.log 2>&1 & disown; cd ..
```

## 7. Checar se tudo respondeu

```bash
sleep 3
curl -s -o /dev/null -w "backend (8000): %{http_code}\n" --max-time 5 http://localhost:8000/docs
curl -s -o /dev/null -w "frontend (3001): %{http_code}\n" --max-time 5 http://localhost:3001
curl -s -o /dev/null -w "calendar-mcp (8090): %{http_code}\n" --max-time 5 http://localhost:8090/mcp
curl -s -o /dev/null -w "mcp-b2b (8100): %{http_code}\n" --max-time 5 http://localhost:8100/mcp
```

`200` no backend/frontend e `400` no calendar-mcp/mcp-b2b (a rota `/mcp`
exige o protocolo MCP, então um `GET` simples sem handshake retorna 400 — é
sinal de que o processo está no ar, não de erro) significa que está tudo
certo. Logs ficam em `/tmp/tcc-backend.log`, `/tmp/tcc-frontend.log`,
`/tmp/tcc-calendar-mcp.log` e `/tmp/tcc-mcp-b2b.log` caso algo não suba.

## Tudo de uma vez (script único)

```bash
fuser -k 8000/tcp 2>/dev/null; fuser -k 3001/tcp 2>/dev/null; fuser -k 8090/tcp 2>/dev/null; fuser -k 8100/tcp 2>/dev/null; sleep 1
cd backend && docker compose up -d postgres qdrant && .venv/bin/alembic upgrade head
export GOOGLE_CLIENT_ID=$(python3 -c "import json; d=json.load(open('secrets/google_calendar_credentials.json')); b=d.get('installed') or d.get('web'); print(b['client_id'])")
export GOOGLE_CLIENT_SECRET=$(python3 -c "import json; d=json.load(open('secrets/google_calendar_credentials.json')); b=d.get('installed') or d.get('web'); print(b['client_secret'])")
export TOKEN_FILE_PATH=./secrets/calendar_mcp_token.json
nohup uvx calendar-mcp-server serve --transport http --port 8090 > /tmp/tcc-calendar-mcp.log 2>&1 & disown
nohup .venv/bin/python scripts/run_mcp_b2b_server.py > /tmp/tcc-mcp-b2b.log 2>&1 & disown
nohup .venv/bin/uvicorn src.app.main:app --host 0.0.0.0 --port 8000 > /tmp/tcc-backend.log 2>&1 & disown
cd ../frontend && PORT=3001 nohup npm run dev > /tmp/tcc-frontend.log 2>&1 & disown
cd ..
sleep 3
curl -s -o /dev/null -w "backend (8000): %{http_code}\n" --max-time 5 http://localhost:8000/docs
curl -s -o /dev/null -w "frontend (3001): %{http_code}\n" --max-time 5 http://localhost:3001
curl -s -o /dev/null -w "calendar-mcp (8090): %{http_code}\n" --max-time 5 http://localhost:8090/mcp
curl -s -o /dev/null -w "mcp-b2b (8100): %{http_code}\n" --max-time 5 http://localhost:8100/mcp
```

## 🌐 Acesso Externo via Internet (WSL2 + Windows + DuckDNS)

Como o projeto executa dentro do **WSL2**, para receber acessos vindos da internet via **DuckDNS** (`http://augustoglauco.duckdns.org:3001`), é necessário autorizar as portas no **Windows Defender Firewall** do host Windows (executar uma vez no **PowerShell como Administrador** no Windows):

```powershell
New-NetFirewallRule -DisplayName "TCC WSL2 Frontend (3001)" -Direction Inbound -LocalPort 3001 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "TCC WSL2 Backend (8000)" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

> 💡 **Dica de Teste Externo:** Devido à ausência de *NAT Loopback* em muitos roteadores residenciais (ex.: Huawei AX3 Pro), teste o acesso externo desligando o Wi-Fi do celular e abrindo pelo **4G/5G móvel**: `http://augustoglauco.duckdns.org:3001` (utilizando **http://** sem `s`).

## Derrubar tudo de novo (encerrar a sessão de testes)

```bash
fuser -k 8000/tcp 2>/dev/null; fuser -k 3001/tcp 2>/dev/null; fuser -k 8090/tcp 2>/dev/null; fuser -k 8100/tcp 2>/dev/null; echo "backend, frontend, calendar-mcp e mcp-b2b encerrados"
```

Docker (postgres/qdrant) fica de pé de propósito — não precisa derrubar entre
sessões. Se quiser mesmo assim: `cd backend && docker compose down`.

**Nunca inclua a porta 3000 nesses comandos de derrubar** — é o Open WebUI,
um serviço à parte, não deste projeto.
