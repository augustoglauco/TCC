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
| **mcp-b2b-server (MCP B2B provido — catálogo/estoque/preços/manuais)** | **8100** (só `127.0.0.1`) | processo solto (`.venv`, `scripts/run_mcp_b2b_server.py`) |
| **Caddy (HTTPS público do MCP B2B)** | **8443** | processo solto (`caddy run`, ver "MCP B2B público" no fim) |
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
> B2B só é consultado por integradores/IAs de parceiros externas ao chat.
> **Desde 2026-09-25** exige chave por parceiro (`MCP_B2B_PARTNER_KEYS` no
> `backend/.env`; sem chave ele não sobe) e é exposto na internet pelo Caddy
> (HTTPS, porta 8443) — ver "MCP B2B público" no fim e
> `docs/ARCHITECTURE.md` §6.

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

**Não sobe sem chave:** precisa de `MCP_B2B_PARTNER_KEYS` no `backend/.env`
(ver "MCP B2B público" no fim). Sem chave, o log mostra
`mcp_b2b_server_sem_autenticacao` e o processo sai.

Escuta só em `127.0.0.1:8100`: de fora, o acesso passa pelo Caddy (HTTPS).
Se o seu `backend/.env` ainda tiver `MCP_B2B_HOST=0.0.0.0`, copiado de um
`.env.example` antigo, troque para `127.0.0.1`. Com `0.0.0.0` o log mostra o
aviso `mcp_b2b_server_exposto_na_rede`, porque o acesso direto pula o HTTPS.

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

`200` no backend/frontend, `400` no calendar-mcp (a rota `/mcp` exige o
protocolo MCP, então um `GET` simples sem handshake retorna 400) e `401` no
mcp-b2b (pede a chave do parceiro) significam que está tudo no ar. Logs ficam em `/tmp/tcc-backend.log`, `/tmp/tcc-frontend.log`,
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

## 🔐 MCP B2B público (DuckDNS + Caddy + chave por parceiro)

Fornecedores fora da rede local acessam o MCP B2B por
`https://augustoglauco.duckdns.org:8443/mcp`, com a chave do parceiro no
cabeçalho `Authorization: Bearer <chave>`. Caminho: roteador (porta 8443) →
Windows → WSL2 → **Caddy** (HTTPS) → servidor em `127.0.0.1:8100`. Decisão
em `docs/ARCHITECTURE.md` §6.

### Configuração única

1. **Chave do parceiro.** Gere uma chave (repita para cada parceiro):

   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

   No `backend/.env`:

   ```bash
   MCP_B2B_HOST=127.0.0.1
   MCP_B2B_PARTNER_KEYS=fornecedor-demo:<chave-gerada>
   MCP_B2B_PUBLIC_URL=https://augustoglauco.duckdns.org:8443/mcp
   ```

   Para vários parceiros: `nome1:chave1,nome2:chave2`. Para revogar um,
   tire a entrada dele e reinicie o servidor. A chave é o que você entrega
   ao fornecedor; nunca a coloque em commit.

2. **Caddy com o módulo DuckDNS** (binário pronto, sem compilar):

   ```bash
   mkdir -p ~/.local/bin
   curl -fL -o ~/.local/bin/caddy "https://caddyserver.com/api/download?os=linux&arch=amd64&p=github.com%2Fcaddy-dns%2Fduckdns"
   chmod +x ~/.local/bin/caddy
   ~/.local/bin/caddy list-modules | grep duckdns   # deve mostrar dns.providers.duckdns
   ```

   Os comandos abaixo usam o caminho completo (`~/.local/bin/caddy`), que
   funciona mesmo se `~/.local/bin` não estiver no `PATH`.

3. **Token do DuckDNS** (o certificado HTTPS sai pelo desafio DNS, sem abrir
   as portas 80/443):

   ```bash
   cp infra/caddy/caddy.env.example infra/caddy/caddy.env
   # edite infra/caddy/caddy.env: DUCKDNS_DOMAIN=augustoglauco.duckdns.org
   # e DUCKDNS_TOKEN=<token do topo da página em duckdns.org>
   ~/.local/bin/caddy validate --config infra/caddy/Caddyfile --envfile infra/caddy/caddy.env
   ```

   O `infra/caddy/caddy.env` fica fora do git.

4. **Windows** (PowerShell como Administrador): regra de firewall, uma vez só.

   ```powershell
   New-NetFirewallRule -DisplayName "TCC WSL2 MCP B2B HTTPS (8443)" -Direction Inbound -LocalPort 8443 -Protocol TCP -Action Allow
   ```

   Depois, confira o modo de rede do WSL2. No PowerShell:
   `wsl wslinfo --networking-mode` (ou `wslinfo --networking-mode` direto no
   terminal do WSL). Em versões antigas do WSL, sem o `wslinfo`, use
   `Get-Content $env:USERPROFILE\.wslconfig`: a linha
   `networkingMode=mirrored` indica o modo espelhado; sem ela, é `nat`.

   - **`mirrored`** (o caso desta máquina: a 3001 funciona sem PortProxy): o
     WSL2 compartilha o IP do Windows, e a regra de firewall basta. **Não
     crie PortProxy:** ele ocuparia a 8443 no Windows e o Caddy não
     conseguiria usá-la dentro do WSL. Se criou por engano, remova com
     `netsh interface portproxy delete v4tov4 listenport=8443 listenaddress=0.0.0.0`.
   - **`nat`** (padrão do WSL2): é preciso encaminhar do Windows para o IP
     do WSL2, e esse IP muda a cada reinício do Windows, então o bloco
     abaixo precisa ser repetido depois de reiniciar:

     ```powershell
     $wslIp = (wsl hostname -I).Trim().Split()[0]
     netsh interface portproxy delete v4tov4 listenport=8443 listenaddress=0.0.0.0 2>$null
     netsh interface portproxy add v4tov4 listenport=8443 listenaddress=0.0.0.0 connectport=8443 connectaddress=$wslIp
     ```

   Nos dois modos, só a 8443: a 8100 (servidor MCP) nunca é encaminhada.

5. **Roteador:** encaminhe a porta **TCP 8443** para o IP deste PC na rede
   local (o mesmo destino já usado para a 3001). Só a 8443: a 8100 nunca
   deve ser encaminhada.

### A cada sessão

```bash
nohup ~/.local/bin/caddy run --config infra/caddy/Caddyfile --envfile infra/caddy/caddy.env > /tmp/tcc-caddy.log 2>&1 & disown
```

Na primeira vez o Caddy leva de 30 s a 2 min para obter o certificado:
acompanhe com `tail -f /tmp/tcc-caddy.log` até aparecer
`certificate obtained successfully`. Se aparecer "address already in use",
um PortProxy esquecido está ocupando a 8443 (ver passo 4). O `./testar.sh` reinicia o servidor MCP
B2B, mas não o Caddy.

### Testar

- **Daqui:** `./testar.sh` (suíte `mcp_b2b`). Confere 401 sem chave e com
  chave errada, a sessão MCP completa com a chave, a porta 8100 fechada para
  a rede e o Caddy com o certificado do domínio.
- **De fora da rede** (o roteador costuma não ter NAT loopback, então de
  dentro da rede o domínio público pode não responder): num notebook no
  4G/5G, com Python e `pip install "mcp>=2.0"`, copie
  `backend/scripts/cliente_mcp_b2b.py` e rode:

  ```bash
  python cliente_mcp_b2b.py --url https://augustoglauco.duckdns.org:8443/mcp --chave <chave>
  ```

  Esperado: `Sem chave: HTTP 401 ✅` e as três etapas com chave ✅,
  terminando com a cotação.

