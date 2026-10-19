#!/usr/bin/env bash
# Teste local em um comando: atualiza o código, reinicia o backend, roda o
# teste que o agente deixou configurado e sobe o relatório para o GitHub.
#
#   ./testar.sh
#
# Detalhes em docs/TESTE_LOCAL.md. Argumentos extras são repassados para
# backend/scripts/teste_local.py (ex.: ./testar.sh --sem-pytest).

set -uo pipefail
cd "$(dirname "$0")"

passo() { printf '\n==> %s\n' "$1"; }
falha() { printf '\n❌ %s\n' "$1"; exit 1; }

# Aguarda até $2 segundos que $1 responda HTTP (qualquer código != 000).
_aguardar_http() {
  local url=$1 limite=$2
  for _ in $(seq 1 "$limite"); do
    if curl -s -o /dev/null --max-time 2 "$url"; then return 0; fi
    sleep 1
  done
  return 1
}

_passo_backend() {
  fuser -k 8000/tcp 2>/dev/null || lsof -ti:8000 | xargs -r kill 2>/dev/null
  sleep 1
  (cd backend && nohup .venv/bin/uvicorn src.app.main:app --host 0.0.0.0 --port 8000 \
    > /tmp/tcc-backend.log 2>&1 & disown)
  _aguardar_http http://localhost:8000/docs 60 \
    || { tail -30 /tmp/tcc-backend.log; falha "Backend não subiu em 60s (log acima)."; }
  echo "Backend no ar"
}

_passo_mcp_b2b() {
  echo "Reiniciando o MCP B2B (porta 8100, log em /tmp/tcc-mcp-b2b.log)"
  (cd backend
    fuser -k 8100/tcp 2>/dev/null || lsof -ti:8100 | xargs -r kill 2>/dev/null
    sleep 1
    nohup .venv/bin/python scripts/run_mcp_b2b_server.py \
      > /tmp/tcc-mcp-b2b.log 2>&1 &
    echo $! > /tmp/tcc-mcp-b2b.pid
    disown)
  # Até 90 s: só os imports (bibliotecas de embeddings) levam ~20 s.
  for _ in $(seq 1 90); do
    if curl -s -o /dev/null --max-time 2 http://127.0.0.1:8100/mcp; then break; fi
    kill -0 "$(cat /tmp/tcc-mcp-b2b.pid)" 2>/dev/null || break
    sleep 1
  done
  if curl -s -o /dev/null --max-time 2 http://127.0.0.1:8100/mcp; then
    echo "MCP B2B no ar"
  else
    tail -15 /tmp/tcc-mcp-b2b.log
    echo "⚠️  MCP B2B não subiu (log acima) — a suíte mcp_b2b vai falhar; as outras seguem."
  fi
}

_passo_frontend() {
  echo "Reiniciando o frontend (porta 3001, log em /tmp/tcc-frontend.log)"
  fuser -k 3001/tcp 2>/dev/null || lsof -ti:3001 | xargs -r kill 2>/dev/null
  sleep 1
  (cd frontend && npm install --no-audit --no-fund --silent >/dev/null 2>&1
    PORT=3001 nohup npm run dev > /tmp/tcc-frontend.log 2>&1 & disown)
  if _aguardar_http http://localhost:3001 60; then
    echo "Frontend no ar"
  else
    tail -10 /tmp/tcc-frontend.log
    echo "⚠️  Frontend não subiu em 60 s (log acima) — o teste segue; confira à mão."
  fi
}

# Sobe o Caddy se a porta 8443 estiver livre; deixa o PID em PID_CADDY (vazio
# se ele já estava rodando). Global porque `$!` não atravessa `$(...)`.
_caddy_subir() {
  local caddy_bin=$1
  PID_CADDY=""
  if ss -ltnH 'sport = :8443' 2>/dev/null | grep -q .; then
    echo "Caddy já está rodando (porta 8443 ocupada)"
    return
  fi
  echo "Iniciando o Caddy (porta 8443, log em /tmp/tcc-caddy.log)"
  nohup "$caddy_bin" run --config infra/caddy/Caddyfile \
    --envfile infra/caddy/caddy.env > /tmp/tcc-caddy.log 2>&1 &
  PID_CADDY=$!
  disown
}

# Imprime o código HTTP do /mcp via HTTPS (000 se não respondeu). Até 2 min: na
# primeira vez o Caddy obtém o certificado pelo DuckDNS.
_caddy_status_https() {
  local dominio=$1 status=000
  for _ in $(seq 1 120); do
    status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 \
      --resolve "$dominio:8443:127.0.0.1" "https://$dominio:8443/mcp")
    [ "$status" != "000" ] && break
    if [ -n "$PID_CADDY" ] && ! kill -0 "$PID_CADDY" 2>/dev/null; then break; fi
    sleep 1
  done
  echo "$status"
}

_passo_caddy() {
  local caddy_bin dominio status_caddy
  caddy_bin=$(command -v caddy || echo "$HOME/.local/bin/caddy")
  if [ ! -f infra/caddy/caddy.env ] || [ ! -x "$caddy_bin" ]; then
    echo "Caddy não configurado (falta infra/caddy/caddy.env ou o binário) — pulando."
    return
  fi
  dominio=$(sed -n 's/^DUCKDNS_DOMAIN=//p' infra/caddy/caddy.env | tr -d '[:space:]')
  _caddy_subir "$caddy_bin"
  status_caddy=$(_caddy_status_https "$dominio")
  if [ "$status_caddy" = "000" ]; then
    tail -15 /tmp/tcc-caddy.log
    echo "⚠️  Caddy sem HTTPS em $dominio:8443 (log acima) — as verificações M5/M6 vão falhar; o resto segue."
  else
    echo "Caddy no ar com HTTPS (HTTP $status_caddy em https://$dominio:8443/mcp)"
  fi
}

_passo_git_pull() {
  passo "1/6 Atualizando o código (git pull)"
  if [ -n "$(git status --porcelain --untracked-files=no -- . ':!testes_locais')" ]; then
    git status --short --untracked-files=no -- . ':!testes_locais'
    falha "Há alterações locais sem commit (lista acima). Faça commit ou 'git stash' e rode de novo."
  fi
  git pull --rebase || falha "git pull falhou."
  echo "Branch $(git rev-parse --abbrev-ref HEAD) @ $(git rev-parse --short HEAD)"
}

_passo_dependencias() {
  passo "2/6 Dependências e migrações do banco"
  docker compose -f backend/docker-compose.yml up -d >/dev/null || falha "docker compose falhou (Docker está rodando?)."
  (cd backend && uv sync --all-extras -q) || falha "uv sync falhou."
  (cd backend && uv run alembic upgrade head) || falha "Migração do banco falhou."
}

_passo_ollama() {
  passo "3/6 Conferindo o Ollama"
  if curl -s --max-time 5 http://localhost:11434/api/tags >/dev/null; then
    echo "Ollama OK"
  else
    echo "⚠️  Ollama não respondeu em localhost:11434 — os cenários de chat vão falhar."
  fi
}

_passo_servicos() {
  passo "4/6 Backend (8000), MCP B2B (8100), frontend (3001) e Caddy (8443)"
  _passo_backend
  _passo_mcp_b2b
  _passo_frontend
  _passo_caddy
}

# Deixa o caminho do relatório mais recente em RELATORIO (usado pelo passo 6).
_passo_teste() {
  passo "5/6 Rodando o teste"
  (cd backend && .venv/bin/python scripts/teste_local.py "$@") || falha "O roteiro de teste quebrou — copie o erro acima e mande para o agente."
  RELATORIO=$(ls -t testes_locais/*.md 2>/dev/null | head -1)
  [ -n "$RELATORIO" ] || falha "Nenhum relatório foi gerado."
}

_passo_enviar_relatorio() {
  local branch espera
  passo "6/6 Enviando o relatório ($RELATORIO)"
  git add "$RELATORIO"
  git commit -q -m "test: resultado do teste local ($(basename "$RELATORIO" .md))" || falha "git commit falhou."
  branch=$(git rev-parse --abbrev-ref HEAD)
  for espera in 0 2 4 8; do
    sleep "$espera"
    if git push -q -u origin "$branch" \
      || { git pull -q --rebase && git push -q -u origin "$branch"; }; then
      printf '\n✅ Pronto. Relatório enviado: %s\n   Avise o agente: "rodei o teste".\n' "$RELATORIO"
      exit 0
    fi
  done
  falha "git push falhou. O relatório está em $RELATORIO — rode 'git push' à mão ou cole o conteúdo no chat."
}

# Tudo dentro de main(): o `git pull` do passo 1 pode reescrever este próprio
# arquivo, e o bash lê scripts aos poucos — com a função, ele já carregou o
# corpo inteiro antes de executar.

main() {
  _passo_git_pull
  _passo_dependencias
  _passo_ollama
  _passo_servicos
  _passo_teste "$@"
  _passo_enviar_relatorio
}

main "$@"
