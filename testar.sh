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

# Tudo dentro de main(): o `git pull` do passo 1 pode reescrever este próprio
# arquivo, e o bash lê scripts aos poucos — com a função, ele já carregou o
# corpo inteiro antes de executar.

main() {
  passo "1/6 Atualizando o código (git pull)"
  if [ -n "$(git status --porcelain -- . ':!testes_locais')" ]; then
    git status --short -- . ':!testes_locais'
    falha "Há alterações locais sem commit (lista acima). Faça commit ou 'git stash' e rode de novo."
  fi
  git pull --ff-only || falha "git pull falhou."
  echo "Branch $(git rev-parse --abbrev-ref HEAD) @ $(git rev-parse --short HEAD)"

  passo "2/6 Dependências e migrações do banco"
  docker compose -f backend/docker-compose.yml up -d >/dev/null || falha "docker compose falhou (Docker está rodando?)."
  (cd backend && uv sync --all-extras -q) || falha "uv sync falhou."
  (cd backend && uv run alembic upgrade head) || falha "Migração do banco falhou."

  passo "3/6 Conferindo o Ollama"
  if curl -s --max-time 5 http://localhost:11434/api/tags >/dev/null; then
    echo "Ollama OK"
  else
    echo "⚠️  Ollama não respondeu em localhost:11434 — os cenários de chat vão falhar."
  fi

  passo "4/6 Reiniciando o backend (porta 8000, log em /tmp/tcc-backend.log)"
  fuser -k 8000/tcp 2>/dev/null || lsof -ti:8000 | xargs -r kill 2>/dev/null
  sleep 1
  (cd backend && nohup .venv/bin/uvicorn src.app.main:app --host 0.0.0.0 --port 8000 \
    > /tmp/tcc-backend.log 2>&1 & disown)
  for _ in $(seq 1 60); do
    if curl -s -o /dev/null --max-time 2 http://localhost:8000/docs; then break; fi
    sleep 1
  done
  curl -s -o /dev/null --max-time 2 http://localhost:8000/docs \
    || { tail -30 /tmp/tcc-backend.log; falha "Backend não subiu em 60s (log acima)."; }
  echo "Backend no ar"

  passo "5/6 Rodando o teste"
  (cd backend && .venv/bin/python scripts/teste_local.py "$@") || falha "O roteiro de teste quebrou — copie o erro acima e mande para o agente."
  relatorio=$(ls -t testes_locais/*.md 2>/dev/null | head -1)
  [ -n "$relatorio" ] || falha "Nenhum relatório foi gerado."

  passo "6/6 Enviando o relatório ($relatorio)"
  git add "$relatorio"
  git commit -q -m "test: resultado do teste local ($(basename "$relatorio" .md))" || falha "git commit falhou."
  for espera in 0 2 4 8; do
    sleep "$espera"
    if git push -q -u origin "$(git rev-parse --abbrev-ref HEAD)"; then
      printf '\n✅ Pronto. Relatório enviado: %s\n   Avise o agente: "rodei o teste".\n' "$relatorio"
      exit 0
    fi
  done
  falha "git push falhou. O relatório está em $relatorio — rode 'git push' à mão ou cole o conteúdo no chat."
}

main "$@"
