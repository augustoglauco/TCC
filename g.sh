set -uo pipefail
cd "$(dirname "$0")"

passo() { printf '\n==> %s\n' "$1"; }
falha() { printf '\n❌ %s\n' "$1"; exit 1; }
checar_servico() {
    local nome="$1"
    local url="$2"
    local extra_flags="${3:-}"
    local status_code="000"

    # Tenta até 5 vezes (aguardando a inicialização do processo)
    for _ in {1..5}; do
        status_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 $extra_flags "$url" 2>/dev/null)
        status_code="${status_code:-000}"
        if [ "$status_code" != "000" ]; then
            break
        fi
        sleep 2
    done

    case "$status_code" in
        200|201|204|301|302|307|308)
            printf "  ✅ %-22s -> HTTP %s (No ar)\n" "$nome" "$status_code"
            ;;
        400|401|403|405)
            printf "  ✅ %-22s -> HTTP %s (No ar - MCP ativo)\n" "$nome" "$status_code"
            ;;
        000)
            printf "  ❌ %-22s -> OFFLINE / TIMEOUT\n" "$nome"
            ;;
        *)
            printf "  ⚠️  %-22s -> HTTP %s (Verificar)\n" "$nome" "$status_code"
            ;;
    esac
}

main() {

    passo "Desligando Serviços"
    # Mata todos os processos nas portas de uma só vez (inclui 8089 do Ollama)
    fuser -k 8000/tcp 3001/tcp 8089/tcp 8090/tcp 8100/tcp 8443/tcp 2>/dev/null || true
    sleep 1

    passo "Subindo o Docker e Migrações"
    if ! command -v docker >/dev/null 2>&1; then
        falha "Comando 'docker' não encontrado! Ative a integração com WSL2 no Docker Desktop (Settings > Resources > WSL integration)."
    elif ! docker info >/dev/null 2>&1; then
        falha "O daemon do Docker não está em execução! Abra o Docker Desktop e aguarde ele iniciar."
    fi

    (
        cd backend
        docker compose up -d postgres qdrant
        .venv/bin/alembic upgrade head
    )

    passo "Subindo o MCP Calendar"
    local calendar_creds="backend/secrets/google_calendar_credentials.json"
    if [ -f "$calendar_creds" ]; then
        read -r GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET < <(
            python3 -c "import json; d=json.load(open('$calendar_creds')); b=d.get('installed') or d.get('web'); print(f\"{b['client_id']} {b['client_secret']}\")"
        )
        export GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET
        export TOKEN_FILE_PATH="./backend/secrets/calendar_mcp_token.json"
        nohup uvx calendar-mcp-server serve --transport http --port 8090 > /tmp/tcc-calendar-mcp.log 2>&1 & disown
    else
        echo "⚠️  Credenciais do Calendar não encontradas em $calendar_creds"
    fi

    passo "Subindo o MCP B2B"
    (
        cd backend
        nohup .venv/bin/python scripts/run_mcp_b2b_server.py > /tmp/tcc-mcp-b2b.log 2>&1 & disown
    )

    passo "Subindo o MCP Ollama"
    nohup ollama serve --transport http --port 8089 > /tmp/tcc-ollama.log 2>&1 &

    passo "Subindo o Caddy"
    [ -f infra/caddy/caddy.env ] && nohup ~/.local/bin/caddy run --config infra/caddy/Caddyfile --envfile infra/caddy/caddy.env > /tmp/tcc-caddy.log 2>&1 & disown

    passo "Subindo o Backend"
    (
        cd backend
        nohup .venv/bin/uvicorn src.app.main:app --host 0.0.0.0 --port 8000 > /tmp/tcc-backend.log 2>&1 & disown
    )

    passo "Subindo o Frontend"
    (
        cd frontend
        PORT=3001 nohup npm run dev > /tmp/tcc-frontend.log 2>&1 & disown
    )

    
# --- Bloco de Checagem ---
    passo "Checando o status dos serviços"
    sleep 3

    checar_servico "Backend (8000)"      "http://localhost:8000/docs"
    checar_servico "Frontend (3001)"     "http://localhost:3001"
    checar_servico "Calendar MCP (8090)" "http://localhost:8090/mcp"
    checar_servico "MCP B2B (8100)"      "http://localhost:8100/mcp"
    
    if [ -f infra/caddy/caddy.env ]; then
        checar_servico "Caddy (8443)" "https://augustoglauco.duckdns.org:8443/mcp" "-k --resolve augustoglauco.duckdns.org:8443:127.0.0.1"
    fi
    printf "\n✨ Todos os testes de inicialização foram executados!\n"
}

main "$@"