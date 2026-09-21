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
| Postgres | 5433 | Docker (`backend/docker-compose.yml`) |
| Qdrant | 6335 / 6336 | Docker (`backend/docker-compose.yml`) |
| Ollama | 11434 | serviço do sistema (`ollama serve`) |

> ⚠️ **Não usamos a porta 3000** — nesta máquina ela já é ocupada pelo
> **Open WebUI**, um serviço separado que não é deste projeto. O frontend
> deste projeto sobe na **3001**, e o backend já está configurado para
> aceitar CORS de `http://localhost:3001` (`CORS_ALLOWED_ORIGIN` em
> `backend/.env` — local, não commitado; o padrão em `.env.example`
> continua 3000, pois isso é uma particularidade desta máquina, não do
> projeto). **Nunca derrube nada na porta 3000.**

Só backend e frontend costumam precisar ser "derrubados" manualmente — Docker
e Ollama normalmente já ficam de pé entre sessões.

## 1. Derrubar processos antigos do projeto (portas 8000 e 3001)

```bash
fuser -k 8000/tcp 2>/dev/null; fuser -k 3001/tcp 2>/dev/null; sleep 1; echo "portas 8000/3001 liberadas"
```

Se `fuser` não existir na sua máquina, alternativa com `lsof`:

```bash
lsof -ti:8000 | xargs -r kill; lsof -ti:3001 | xargs -r kill; sleep 1; echo "portas 8000/3001 liberadas"
```

Conferir se ficou algo preso:

```bash
ss -ltnp 2>/dev/null | grep -E ':(8000|3001)\s' || echo "nada escutando em 8000/3001"
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

## 4. Subir o backend (porta 8000, em background)

```bash
cd backend && nohup .venv/bin/uvicorn src.app.main:app --host 0.0.0.0 --port 8000 > /tmp/tcc-backend.log 2>&1 & disown; cd ..
```

## 5. Subir o frontend (porta 3001, em background)

```bash
cd frontend && PORT=3001 nohup npm run dev > /tmp/tcc-frontend.log 2>&1 & disown; cd ..
```

## 6. Checar se tudo respondeu

```bash
sleep 3
curl -s -o /dev/null -w "backend (8000): %{http_code}\n" --max-time 5 http://localhost:8000/docs
curl -s -o /dev/null -w "frontend (3001): %{http_code}\n" --max-time 5 http://localhost:3001
```

`200` nos dois significa que está tudo no ar. Logs ficam em `/tmp/tcc-backend.log`
e `/tmp/tcc-frontend.log` caso algo não suba.

## Tudo de uma vez (script único)

```bash
fuser -k 8000/tcp 2>/dev/null; fuser -k 3001/tcp 2>/dev/null; sleep 1
cd backend && docker compose up -d postgres qdrant && .venv/bin/alembic upgrade head
nohup .venv/bin/uvicorn src.app.main:app --host 0.0.0.0 --port 8000 > /tmp/tcc-backend.log 2>&1 & disown
cd ../frontend && PORT=3001 nohup npm run dev > /tmp/tcc-frontend.log 2>&1 & disown
cd ..
sleep 3
curl -s -o /dev/null -w "backend (8000): %{http_code}\n" --max-time 5 http://localhost:8000/docs
curl -s -o /dev/null -w "frontend (3001): %{http_code}\n" --max-time 5 http://localhost:3001
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
fuser -k 8000/tcp 2>/dev/null; fuser -k 3001/tcp 2>/dev/null; echo "backend e frontend encerrados"
```

Docker (postgres/qdrant) fica de pé de propósito — não precisa derrubar entre
sessões. Se quiser mesmo assim: `cd backend && docker compose down`.

**Nunca inclua a porta 3000 nesses comandos de derrubar** — é o Open WebUI,
um serviço à parte, não deste projeto.
