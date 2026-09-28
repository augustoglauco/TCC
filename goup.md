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
> `docs/ARCHITECTURE.md` §5 e o passo 0.7 abaixo para
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

## 0. Instalação inicial (uma vez por máquina)

Só na primeira vez (ou numa máquina nova). Depois, a cada sessão, basta o
passo 1 em diante, o `./g.sh` ou o `./testar.sh`. Conteúdo trazido do antigo
`docs/Manuais/HOWTO_IMPLANTACAO_INFRA.md` e da parte de configuração do
`GUIA_TESTE_AGENDAMENTO.md` (consolidação de 2026-09-28).

### 0.1 Pré-requisitos

- **GPU** NVIDIA com 16 GB de VRAM (ex.: RTX 4080) e driver com CUDA;
  32 GB de RAM e ~100 GB de SSD (imagens Docker, collections do Qdrant,
  pesos dos modelos).
- **Sistema:** Ubuntu 22.04 ou WSL2 no Windows 11.
- **Docker** com Compose v2 (no WSL2: Docker Desktop com a integração WSL
  ligada), **Node.js 20+** com `npm`, **`uv`** (ele baixa o Python 3.14
  sozinho, ver `docs/CONVENTIONS.md`, "Stack").
- Pacotes do sistema para OCR e áudio:
  `sudo apt install tesseract-ocr tesseract-ocr-por ffmpeg`.

### 0.2 Bancos (Docker)

O `backend/docker-compose.yml` já existe; só sobe:
`cd backend && docker compose up -d postgres qdrant`.

As portas do host são **5433** (Postgres) e **6335/6336** (Qdrant), não as
padrão, para não conflitar com outros projetos na mesma máquina. O
`backend/.env.example` já usa essas portas; se mudar uma, mude o par
(`docker-compose.yml` e `POSTGRES_DSN`/`QDRANT_PORT`).

### 0.3 Ollama e modelo local

```bash
curl -fsSL https://ollama.com/install.sh | sh
nvidia-smi                           # a GPU precisa aparecer
ollama pull gemma4:12b-it-q4_K_M     # modelo em uso (LOCAL_MODEL_NAME)
curl http://localhost:11434/api/tags
```

Os outros candidatos da avaliação estão em `docs/EVALUATION.md`; também dá
para baixar e trocar pela tela `/admin/modelos`.

### 0.4 Backend

```bash
cd backend
uv sync --all-extras          # cria o .venv e instala tudo (inclui pytest/ruff)
cp .env.example .env          # nunca crie o .env do zero
.venv/bin/alembic upgrade head
```

No `backend/.env`, ajuste pelo menos `LOCAL_MODEL_NAME`
(`gemma4:12b-it-q4_K_M`), `EXTERNAL_MODEL_API_KEY` e `EXTERNAL_MODEL_NAME`
(OpenRouter, formato `provedor/modelo`) e, para o MCP B2B,
`MCP_B2B_PARTNER_KEYS` (ver "MCP B2B público"). A lista completa e comentada
está no próprio `.env.example`. O `.env` nunca vai para o git.

### 0.5 Frontend

`cd frontend && npm install`. O frontend descobre sozinho o endereço do
backend pelo host da página (`lib/api/apiBaseUrl.ts`), então não precisa de
`.env.local` para uso local nem pela rede.

### 0.6 Carga inicial do RAG

Com Postgres e Qdrant no ar e as migrações aplicadas, a partir de
`backend/`:

```bash
.venv/bin/python scripts/ingest_sample_docs.py        # PDFs/textos de scripts/sample_docs/<domínio>/
.venv/bin/python scripts/ingest_db_table.py --table produtos --domain vendas   # opcional (conector R4)
```

O catálogo de exemplo já vem semeado pelas migrações. Produtos, fotos (com
vetor no CLIP) e catálogos em PDF entram pela tela `/admin/produtos`;
manuais e documentos, por `/admin/ingestao`.

### 0.7 Agendamento: autorização do Google Calendar

O agendamento (R11) fala com o `calendar-mcp-server`, um MCP de terceiro
rodando localmente na porta 8090 (decisão em `docs/ARCHITECTURE.md` §5).
Configuração única:

1. No [Google Cloud Console](https://console.cloud.google.com/), crie um
   projeto e ative a **Google Calendar API**.
2. Crie uma credencial OAuth 2.0 do tipo **"App para computador"** (o único
   tipo que funciona com o fluxo local do `calendar-mcp-server`) e salve o
   JSON em `backend/secrets/google_calendar_credentials.json`.
3. Na tela de consentimento OAuth, adicione sua conta em **"Usuários de
   teste"**.
4. Autorize uma vez (gera `backend/secrets/calendar_mcp_token.json`):

   ```bash
   cd backend
   export GOOGLE_CLIENT_ID=$(python3 -c "import json; d=json.load(open('secrets/google_calendar_credentials.json')); b=d.get('installed') or d.get('web'); print(b['client_id'])")
   export GOOGLE_CLIENT_SECRET=$(python3 -c "import json; d=json.load(open('secrets/google_calendar_credentials.json')); b=d.get('installed') or d.get('web'); print(b['client_secret'])")
   export TOKEN_FILE_PATH=./secrets/calendar_mcp_token.json
   uvx calendar-mcp-server auth
   ```

   Abra a URL mostrada, escolha a conta e conceda a permissão.
5. No `backend/.env`: `CALENDAR_MCP_URL=http://127.0.0.1:8090/mcp`,
   `GOOGLE_CALENDAR_CALENDAR_ID=primary` e as regras de expediente
   (`AGENDAMENTO_TIMEZONE=America/Sao_Paulo`,
   `AGENDAMENTO_EXPEDIENTE_DIAS=seg-sex`,
   `AGENDAMENTO_EXPEDIENTE_INICIO=09:00`,
   `AGENDAMENTO_EXPEDIENTE_FIM=18:00`).

A cada sessão, o servidor sobe no passo 4 abaixo. Os casos de teste manuais
do agendamento estão em `docs/TESTE_LOCAL.md`, "Roteiro manual:
agendamento".

## 1. Derrubar processos antigos do projeto (portas 8000, 3001, 8090, 8100 e 8443)

```bash
fuser -k 8000/tcp 2>/dev/null; fuser -k 3001/tcp 2>/dev/null; fuser -k 8090/tcp 2>/dev/null; fuser -k 8100/tcp 2>/dev/null; fuser -k 8443/tcp 2>/dev/null; sleep 1; echo "portas 8000/3001/8090/8100/8443 liberadas"
```

Se `fuser` não existir na sua máquina, alternativa com `lsof`:

```bash
lsof -ti:8000 | xargs -r kill; lsof -ti:3001 | xargs -r kill; lsof -ti:8090 | xargs -r kill; lsof -ti:8100 | xargs -r kill; lsof -ti:8443 | xargs -r kill; sleep 1; echo "portas 8000/3001/8090/8100/8443 liberadas"
```

Conferir se ficou algo preso:

```bash
ss -ltnp 2>/dev/null | grep -E ':(8000|3001|8090|8100|8443)\s' || echo "nada escutando em 8000/3001/8090/8100/8443"
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
passo 0.7 se ainda não fez isso):

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
[ -f infra/caddy/caddy.env ] && curl -k -s -o /dev/null -w "caddy (8443): %{http_code}\n" --max-time 5 https://localhost:8443/mcp
```

`200` no backend/frontend, `400` no calendar-mcp (a rota `/mcp` exige o
protocolo MCP, então um `GET` simples sem handshake retorna 400) e `401` no
mcp-b2b/caddy (pede a chave do parceiro) significam que está tudo no ar. Logs ficam em `/tmp/tcc-backend.log`, `/tmp/tcc-frontend.log`,
`/tmp/tcc-calendar-mcp.log`, `/tmp/tcc-mcp-b2b.log` e `/tmp/tcc-caddy.log` caso algo não suba.

## Tudo de uma vez (script único)

`./g.sh`, na raiz do repositório, faz os passos 1 a 7 em sequência: derruba
as portas, sobe Docker e migrações, o `calendar-mcp-server` (se houver
credenciais em `backend/secrets/`), o MCP B2B, o Caddy (se
`infra/caddy/caddy.env` existir), o backend e o frontend, e confere cada
serviço. Para subir e já rodar os testes, use o `./testar.sh`
(`docs/TESTE_LOCAL.md`).

## 🌐 Acesso Externo via Internet (WSL2 + Windows + DuckDNS)

Como o projeto executa dentro do **WSL2**, para receber acessos vindos da internet via **DuckDNS** (`http://augustoglauco.duckdns.org:3001`), é necessário autorizar as portas no **Windows Defender Firewall** do host Windows (executar uma vez no **PowerShell como Administrador** no Windows):

```powershell
New-NetFirewallRule -DisplayName "TCC WSL2 Frontend (3001)" -Direction Inbound -LocalPort 3001 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "TCC WSL2 Backend (8000)" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

> 💡 **Dica de Teste Externo:** Devido à ausência de *NAT Loopback* em muitos roteadores residenciais (ex.: Huawei AX3 Pro), teste o acesso externo desligando o Wi-Fi do celular e abrindo pelo **4G/5G móvel**: `http://augustoglauco.duckdns.org:3001` (utilizando **http://** sem `s`).

## Derrubar tudo de novo (encerrar a sessão de testes)

```bash
fuser -k 8000/tcp 2>/dev/null; fuser -k 3001/tcp 2>/dev/null; fuser -k 8090/tcp 2>/dev/null; fuser -k 8100/tcp 2>/dev/null; fuser -k 8443/tcp 2>/dev/null; echo "backend, frontend, calendar-mcp, mcp-b2b e caddy encerrados"
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

O `./testar.sh` já sobe o Caddy sozinho quando ele não está rodando (e o
`infra/caddy/caddy.env` existe), e espera o certificado. Para subir à mão:

```bash
nohup ~/.local/bin/caddy run --config infra/caddy/Caddyfile --envfile infra/caddy/caddy.env > /tmp/tcc-caddy.log 2>&1 & disown
```

Para desligar: `pkill -f "caddy run"`.

Na primeira vez o Caddy leva de 30 s a 2 min para obter o certificado:
acompanhe com `tail -f /tmp/tcc-caddy.log` até aparecer
`certificate obtained successfully`. Se aparecer "address already in use",
um PortProxy esquecido está ocupando a 8443 (ver passo 4).

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

### Para o parceiro (manual de integração)

O que entregar ao fornecedor junto com a chave dele. Conteúdo trazido do
antigo `docs/Manuais/MANUAL_INTEGRACAO_MCP_B2B.md` e conferido contra
`backend/src/app/mcp_server/b2b.py` em 2026-09-28 (o manual antigo tinha
nomes de recursos e argumentos errados).

- **Endereço:** `https://augustoglauco.duckdns.org:8443/mcp` (MCP via
  Streamable HTTP, sobre HTTPS).
- **Autenticação:** cabeçalho `Authorization: Bearer <chave-do-parceiro>`
  em toda requisição; sem chave ou com chave errada, `HTTP 401`.
- **Recursos (leitura):**

  | URI | Conteúdo |
  | --- | --- |
  | `catalogo://produtos{?categoria}` | Catálogo, com filtro opcional por categoria |
  | `catalogo://produtos/{produto_id}` | Detalhe de um produto (sem preço nem estoque) |
  | `estoque://produtos/{produto_id}` | Estoque por centro de distribuição |
  | `precos://produtos/{produto_id}` | Preço, promoção vigente e descontos por volume |
  | `manuais://busca/{domain}{?query}` | Busca semântica nos manuais do canal B2B |

- **Ferramentas:**

  | Ferramenta | Argumentos | Retorno |
  | --- | --- | --- |
  | `validar_compatibilidade` | `produto_id`, `produto_relacionado_id` | `{produto_id, produto_relacionado_id, compativel}` |
  | `consultar_frete` | `cep`, `itens: [{produto_id, quantidade}]` | `{cep, peso_total_kg, custo_estimado, prazo_dias}` (estimativa interna, sem transportadora real) |
  | `cotar` | `itens: [{produto_id, quantidade}]` | `{itens, total}`, com desconto por volume |
  | `reservar_pedido` | `itens: [{produto_id, quantidade, centro_distribuicao}]` | `{id, status: "reservado", criado_em, itens}` (cria pedido de verdade) |

- **Exemplo em Python** (`pip install "mcp>=2.0"`):

  ```python
  import asyncio
  from mcp.client.session import ClientSession
  from mcp.client.streamable_http import streamable_http_client
  from mcp.shared._httpx_utils import create_mcp_http_client

  URL = "https://augustoglauco.duckdns.org:8443/mcp"
  CHAVE = "<chave-do-parceiro>"

  async def main() -> None:
      async with create_mcp_http_client(headers={"Authorization": f"Bearer {CHAVE}"}) as http:
          async with streamable_http_client(URL, http_client=http) as (leitura, escrita):
              async with ClientSession(leitura, escrita) as sessao:
                  await sessao.initialize()
                  cotacao = await sessao.call_tool(
                      "cotar", arguments={"itens": [{"produto_id": 1, "quantidade": 2}]}
                  )
                  print(cotacao.structured_content or cotacao.content)

  asyncio.run(main())
  ```

  O `backend/scripts/cliente_mcp_b2b.py` faz o mesmo teste pronto (ver
  "Testar" acima).
- **Erros comuns:** `401` = chave ausente ou errada (`Bearer <chave>`);
  timeout ou conexão recusada = servidor fora do ar ou porta 8443 bloqueada
  na rede do parceiro; erro de ferramenta "produto não encontrado" = ID
  inexistente (consulte `catalogo://produtos`).

## Solução de problemas e logs

Logs: `/tmp/tcc-backend.log`, `/tmp/tcc-frontend.log`,
`/tmp/tcc-calendar-mcp.log`, `/tmp/tcc-mcp-b2b.log` e `/tmp/tcc-caddy.log`
(backend em JSON, com o `conversation_id` em cada linha); bancos com
`docker compose logs -f postgres` ou `qdrant` (em `backend/`); Ollama com
`journalctl -u ollama -f`.

| Sintoma | Causa provável | O que fazer |
| --- | --- | --- |
| Falta de memória na GPU (OOM) | Modelo grande demais para 16 GB, ou STT/CLIP disputando a GPU com o modelo local (`docs/ARCHITECTURE.md` §7) | Use um modelo menor (`/admin/modelos` ou `LOCAL_MODEL_NAME`) e evite testar áudio/imagem ao mesmo tempo que carga pesada de chat |
| "Serviço temporariamente indisponível" no chat | Ollama fora do ar, ou 429 do OpenRouter (comum com modelos `:free`) | Confira `curl http://localhost:11434/api/tags`; no log do backend, procure `chat_dependencia_indisponivel` com o erro; troque o modelo externo em `/admin/modelos` |
| Resposta muito lenta num modelo novo | Modelo com a capacidade `thinking` gerando raciocínio longo | O cliente já manda `think: false`; confira com `ollama show <modelo>` |
| Erro no OCR | `tesseract` fora do `PATH` | `sudo apt install tesseract-ocr tesseract-ocr-por` |
| Erro no áudio | Falta o `ffmpeg`, ou o modelo do `faster-whisper` ainda não foi baixado | `sudo apt install ffmpeg`; a primeira transcrição baixa o modelo (`STT_MODEL_SIZE`) |
| Containers não sobem | Porta 5433 ou 6335/6336 ocupada | `sudo lsof -i :5433`; se mudar a porta no `docker-compose.yml`, mude também no `.env` |
| Agendamento falha com "MCP do Google Calendar indisponível" | `calendar-mcp-server` fora do ar ou token expirado | `curl http://127.0.0.1:8090/mcp` (400 = no ar); sem resposta, suba no passo 4; token expirado, repita o `auth` do passo 0.7 |
| Horário do agendamento deslocado | Fuso errado | `AGENDAMENTO_TIMEZONE=America/Sao_Paulo` no `.env` |
| Agendamento "esquece" os dados no meio | Backend reiniciado: os dados da coleta ficam só em memória (`# MVP`) | Recomece a conversa de agendamento |

