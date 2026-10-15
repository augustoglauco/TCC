#!/usr/bin/env bash
# Sobe o ambiente completo (Docker, migrações, calendar-mcp-server, MCP B2B,
# Caddy, backend, frontend e as ferramentas de inteligência de código da tela
# /admin/ferramentas) e confere cada serviço — os passos 1 a 7 do
# goup.md de uma vez. Para subir e já rodar os testes, use ./testar.sh.
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
    # Mata os processos do projeto nas portas de uma só vez. O Ollama (11434)
    # fica de fora: é um serviço do sistema, reaproveitado entre sessões.
    fuser -k 8000/tcp 3001/tcp 8090/tcp 8100/tcp 8443/tcp 2>/dev/null || true
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

    passo "Conferindo o Ollama (11434)"
    # O backend usa o Ollama na porta padrão (LOCAL_MODEL_BASE_URL). Só sobe
    # um `ollama serve` se ninguém responder lá — se ele já roda como serviço
    # do sistema, um segundo processo falharia com a porta ocupada.
    if curl -s -o /dev/null --max-time 3 http://localhost:11434/api/tags; then
        echo "Ollama já está no ar."
    elif command -v ollama >/dev/null 2>&1; then
        nohup ollama serve > /tmp/tcc-ollama.log 2>&1 & disown
        echo "Ollama iniciado (log em /tmp/tcc-ollama.log)."
    else
        echo "⚠️  Ollama não encontrado — o chat não vai responder sem ele (ver goup.md, passo 0.3)."
    fi

    passo "Conferindo as ferramentas de código (/admin/ferramentas)"
    # Mesma política do Ollama: Graphify, Repowise e GitNexus são ferramentas
    # de desenvolvimento reaproveitadas entre sessões, então este bloco só
    # sobe o que NÃO estiver respondendo — e, de propósito, elas ficam fora do
    # `fuser -k` lá em cima. Nenhuma delas é necessária para o assistente
    # funcionar; a tela /admin/ferramentas mostra o comando de cada uma
    # quando falta.

    # Graphify é artefato, não servidor: basta o HTML existir.
    if [ -f graphify-out/graph.html ]; then
        echo "Graphify: grafo já gerado."
    elif command -v graphify >/dev/null 2>&1; then
        if graphify update . > /tmp/tcc-graphify.log 2>&1; then
            echo "Graphify: grafo gerado agora."
        else
            echo "⚠️  Graphify falhou ao gerar o grafo (ver /tmp/tcc-graphify.log)."
        fi
    else
        echo "⚠️  Graphify não encontrado (ver CLAUDE.md, regra 13)."
    fi

    # As UIs reais sobem em portas internas — Repowise 3012 (`--ui-port` fixo:
    # sem ele escolhe a primeira livre a partir da 3000) e GitNexus 4757. As
    # portas públicas 3002 e 4747 são do Caddy (infra/caddy/Caddyfile.ferramentas),
    # com senha: o `localhost` do iframe é o do navegador, então de fora da
    # rede só funciona por uma porta pública deste servidor.
    if curl -s -o /dev/null --max-time 3 http://localhost:3012; then
        echo "Repowise já está no ar (3012)."
    elif command -v repowise >/dev/null 2>&1; then
        nohup repowise serve --ui-port 3012 > /tmp/tcc-repowise.log 2>&1 & disown
        echo "Repowise iniciado na 3012 (log em /tmp/tcc-repowise.log)."
    else
        echo "⚠️  Repowise não encontrado (ver docs/Manuais/repowise-manual.md)."
    fi

    # Binário do PATH primeiro, `.gitnexus/run.cjs` como alternativa — os dois
    # existem nesta máquina e o CLAUDE.md descreve o runner como intercambiável.
    if curl -s -o /dev/null --max-time 3 http://localhost:4757; then
        echo "GitNexus já está no ar (4757)."
    elif command -v gitnexus >/dev/null 2>&1; then
        nohup gitnexus serve -p 4757 > /tmp/tcc-gitnexus.log 2>&1 & disown
        echo "GitNexus iniciado na 4757 (log em /tmp/tcc-gitnexus.log)."
    elif [ -f .gitnexus/run.cjs ]; then
        nohup node .gitnexus/run.cjs serve -p 4757 > /tmp/tcc-gitnexus.log 2>&1 & disown
        echo "GitNexus iniciado na 4757 via .gitnexus/run.cjs (log em /tmp/tcc-gitnexus.log)."
    else
        echo "⚠️  GitNexus não encontrado (ver docs/Manuais/gitnexus-manual.md)."
    fi

    if [ -f infra/caddy/caddy.env ] && [ -x ~/.local/bin/caddy ]; then
        if curl -s -o /dev/null --max-time 3 http://localhost:3002; then
            echo "Proxy das ferramentas já está no ar (3002/4747)."
        else
            nohup ~/.local/bin/caddy run --config infra/caddy/Caddyfile.ferramentas --adapter caddyfile --envfile infra/caddy/caddy.env > /tmp/tcc-caddy-ferramentas.log 2>&1 & disown
            echo "Proxy das ferramentas iniciado (3002 Repowise, 4747 GitNexus; log em /tmp/tcc-caddy-ferramentas.log)."
        fi
    else
        echo "⚠️  Sem infra/caddy/caddy.env: ferramentas só acessíveis em localhost (3012/4757)."
    fi

    passo "Subindo o Caddy"
    [ -f infra/caddy/caddy.env ] && nohup ~/.local/bin/caddy run --config infra/caddy/Caddyfile --envfile infra/caddy/caddy.env > /tmp/tcc-caddy.log 2>&1 & disown

    passo "Subindo o Backend"
    (
        cd backend
        nohup .venv/bin/uvicorn src.app.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/tcc-backend.log 2>&1 & disown
    )

    passo "Subindo o Frontend"
    (
        cd frontend
        PORT=3001 nohup npm run dev > /tmp/tcc-frontend.log 2>&1 & disown
    )

    
# --- Bloco de Checagem ---
    passo "Checando o status dos serviços"
    sleep 3

    checar_servico "Ollama (11434)"      "http://localhost:11434/api/tags"
    checar_servico "Backend (8000)"      "http://localhost:8000/docs"
    checar_servico "Frontend (3001)"     "http://localhost:3001"
    checar_servico "Calendar MCP (8090)" "http://localhost:8090/mcp"
    checar_servico "MCP B2B (8100)"      "http://localhost:8100/mcp"
    checar_servico "Repowise (3012)"     "http://localhost:3012"
    checar_servico "GitNexus (4757)"     "http://localhost:4757"
    if [ -f graphify-out/graph.html ]; then
        printf "  ✅ %-22s -> artefato presente\n" "Graphify (grafo)"
    else
        printf "  ❌ %-22s -> AUSENTE (rode: graphify update .)\n" "Graphify (grafo)"
    fi
    
    if [ -f infra/caddy/caddy.env ]; then
        checar_servico "Caddy (8443)" "https://augustoglauco.duckdns.org:8443/mcp" "-k --resolve augustoglauco.duckdns.org:8443:127.0.0.1"
    fi
    printf "\n✨ Todos os testes de inicialização foram executados!\n"
}

main "$@"
