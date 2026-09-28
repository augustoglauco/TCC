# Convenções de Desenvolvimento

## Stack

- **Python 3.14+** (otimizado com PEP 695 e PEP 649; baseline Python 3.11/3.13 e procedimento de rollback na seção "Rollback de Versões" abaixo), framework **FastAPI** (async-first) para as APIs do chat
  e do servidor MCP B2B.
- **Pydantic** para todos os schemas de entrada/saída (requisições HTTP,
  respostas de ferramentas MCP, eventos internos).
- **Ollama** ou **vLLM** para servir o modelo local; cliente HTTP simples
  para o(s) modelo(s) externo(s).
- **SDK oficial de MCP em Python** tanto para o cliente (Google Calendar)
  quanto para o servidor (MCP B2B).
- **Qdrant** como banco vetorial, para RAG de texto e de imagem — uma
  collection por tipo de conteúdo (ex.: `docs_texto`, `catalogo_imagens`),
  usando os filtros nativos do Qdrant (payload filtering) para restringir
  busca por domínio/categoria quando necessário. Roda bem em um único
  container Docker, ao lado do restante da stack no mesmo VPS/EC2 usado
  para o modelo local.
- **PostgreSQL** como banco de dados relacional — cobre tanto o conector de
  leitura exigido por R4 (o RAG lê catálogo/conteúdo estruturado de lá)
  quanto a persistência da aplicação: conversas e resumos (R9), perfil/
  classificação do usuário (R10) e o backend único de catálogo/estoque/
  preços/manuais compartilhado entre o RAG e o servidor MCP B2B (ver
  `docs/ARCHITECTURE.md`, Seção 6). Acesso via SQLAlchemy (async, `asyncpg`)
  ou driver assíncrono equivalente — manter as migrações em uma pasta
  `migrations/` versionada (ex.: Alembic).

- **Next.js + TypeScript** para o frontend (site institucional, produtos,
  pedidos e o widget de chat) — detalhes de stack, seções da interface e
  contrato de API em `docs/FRONTEND.md`.

Esta stack foi definida como ponto de partida; se uma tarefa específica
exigir revisão (ex.: trocar o banco vetorial ou o banco relacional),
registre o motivo em `docs/ARCHITECTURE.md` antes de trocar, não apenas no
código.

### Bibliotecas e versões em uso

Conferido em 2026-09-28 contra `backend/pyproject.toml`,
`frontend/package.json` e `backend/docker-compose.yml` (conteúdo trazido do
antigo `docs/TECHNOLOGY_STACK.md`, que citava bibliotecas que o projeto
nunca usou). O porquê das escolhas centrais está em `docs/ARCHITECTURE.md`
§2. Ao trocar uma dependência, atualize esta tabela.

| Área | Em uso |
| --- | --- |
| Linguagem e API | Python 3.14, FastAPI, Uvicorn, Pydantic v2, `pydantic-settings` (`.env`) |
| Banco relacional | PostgreSQL 15 (`postgres:15-alpine`), SQLAlchemy 2 async + `asyncpg`, migrações Alembic em `backend/migrations/` |
| Banco vetorial | Qdrant (`qdrant/qdrant`), `qdrant-client`; collections por perfil (`rag_collections`) e `catalogo_imagens` |
| Embeddings | `sentence-transformers`: texto `paraphrase-multilingual-MiniLM-L12-v2` (384 dims, configurável por collection), imagem `clip-ViT-B-32` (512 dims) |
| Modelo local | Ollama (cliente HTTP próprio); em uso `gemma4:12b-it-q4_K_M`, candidatos da avaliação em `docs/EVALUATION.md` |
| Modelo externo | OpenRouter via `httpx` (texto, visão e classificador Jev); modelo trocável em `/admin/modelos` |
| Documentos e imagem | `pdfplumber` (PDF), `beautifulsoup4` (crawler), Pillow, `pytesseract` (OCR) |
| Áudio | `faster-whisper` local (`STT_MODEL_SIZE`, default `small`) |
| MCP | SDK oficial `mcp` (cliente do `calendar-mcp-server` e servidor B2B); Caddy + DuckDNS para o HTTPS público do B2B |
| Testes e lint (backend) | `pytest`, `pytest-asyncio`, `aiosqlite` (SQLite dos testes), `ruff` (lint e format) |
| Frontend | Next.js 16 (App Router), React 19, TypeScript 5, Tailwind CSS 4, Zustand 5, Radix UI (dialog, tabs); SSE lido com `fetch` + `ReadableStream` |
| Testes e lint (frontend) | Vitest 4 + Testing Library, Playwright, ESLint 9 (`eslint-config-next`), Prettier 3 |
| Versões mínimas do ambiente | Python 3.14, Node.js 20, Docker com Compose v2, GPU NVIDIA com 16 GB de VRAM e driver com CUDA para o Ollama |

## Estrutura de pastas proposta (monorepo)

Backend e frontend vivem no mesmo repositório, como projetos irmãos — mais
simples de manter para um TCC com um desenvolvedor, e facilita manter
`docs/` como fonte de verdade única para os dois.

```
repo/
├── CLAUDE.md
├── .agents/rules/project.md
├── docs/
│   ├── ARCHITECTURE.md
│   ├── FRONTEND.md
│   ├── ROADMAP.md
│   ├── CONVENTIONS.md
│   ├── EVALUATION.md
│   └── AGENTIC_WORKFLOW.md
├── backend/
│   ├── src/app/
│   │   ├── api/            # rotas HTTP (FastAPI routers)
│   │   ├── router/          # Roteador/Orquestrador (classificação de intenção)
│   │   ├── rag/             # ingestão, embeddings, busca vetorial (texto e imagem)
│   │   ├── stt/             # conversão de áudio em texto
│   │   ├── ocr/             # OCR e identificação de imagem
│   │   ├── tone_monitor/    # monitoramento de tom
│   │   ├── mcp_client/      # cliente MCP (Google Calendar)
│   │   ├── mcp_server/      # servidor MCP B2B (provido)
│   │   ├── memory/          # persistência e resumo de conversa
│   │   ├── user_profile/    # classificação Cliente/Lead/Esporádico
│   │   ├── db/              # engine/sessão do PostgreSQL, modelos SQLAlchemy
│   │   ├── models/          # schemas Pydantic
│   │   └── config.py
│   ├── migrations/          # migrações do PostgreSQL (ex.: Alembic)
│   ├── eval/
│   │   ├── router_intents/  # conjunto de teste + script de avaliação do roteador
│   │   ├── rag_quality/     # perguntas de referência + script de avaliação do RAG
│   │   └── latency/         # script de benchmark de latência local x externo
│   ├── tests/
│   ├── .env.example
│   └── pyproject.toml
├── infra/
│   └── caddy/               # proxy HTTPS público do MCP B2B (Caddyfile + caddy.env.example)
└── frontend/                # ver estrutura detalhada em docs/FRONTEND.md §5
    ├── app/
    ├── components/
    ├── lib/
    ├── public/
    ├── tests/
    ├── .env.example
    └── package.json
```

Cada módulo em `backend/src/app/` corresponde a um bloco do diagrama de
arquitetura em `docs/ARCHITECTURE.md` — ao criar um módulo novo, verifique se
ele já não deveria existir dentro de um desses (evite criar pastas ad hoc).
O frontend segue sua própria estrutura, detalhada em `docs/FRONTEND.md`.

## Estilo de código

- Type hints em todo código novo; funções públicas com docstring curta.
- Formatação/lint com `ruff` (inclui a função de `black`); rodar antes de
  cada commit.
- Preferir funções e módulos pequenos e testáveis a classes grandes com
  muita responsabilidade — especialmente no roteador e no RAG, onde a lógica
  de decisão deve ser fácil de testar isoladamente.
- Operações de I/O (chamadas a LLM, MCP, banco de dados) devem ser `async`.
- Nunca hardcode chaves de API, tokens ou credenciais — usar variáveis de
  ambiente documentadas em `.env.example`.

## Comentários de escopo do MVP

Sempre que uma implementação for uma versão simplificada por decisão de
escopo (ver tabela em `docs/ARCHITECTURE.md`), marque com um comentário no
formato:

```python
# MVP: crawler com execução síncrona por chamada, sem fila de background nem agendamento (ver docs/ARCHITECTURE.md §5)
```

Isso evita que uma sessão futura do Claude Code "corrija" uma simplificação
intencional achando que é um bug ou uma tarefa esquecida.

## Testes

- `pytest` para testes unitários e de integração.
- Cobertura mínima esperada para os componentes centrais do MVP:
  - Classificação de intenção do roteador (casos por domínio + casos
    ambíguos).
  - Recuperação do RAG (texto e imagem) — dado um conjunto pequeno de
    documentos/imagens conhecidos, a busca retorna o item esperado.
  - Handlers das quatro ferramentas do MCP B2B (compatibilidade, frete,
    cotação, reserva/pedido) — incluindo o caso de concorrência simples em
    reserva/pedido.
  - Parsing e validação de schemas Pydantic de entrada/saída.
- Testes automatizados **nunca** usam o Postgres, o Qdrant nem a pasta de
  fotos reais do desenvolvedor: banco via SQLite em memória (fixture
  `db_session` em `backend/tests/conftest.py`) e, para testes de API com o
  app inteiro, a fixture `app_sqlite` (`create_app()` com o banco no
  SQLite, o CLIP/Qdrant por um dublê e as fotos em `tmp_path`). Chamar
  `create_app()` direto num teste que grava ou lê o banco é bug: até
  2026-09-28, os testes das APIs de produtos criavam e apagavam produtos no
  catálogo real e deixavam lixo quando falhavam (limpeza:
  `backend/scripts/limpar_produtos_de_teste.py`).
- Testes que dependem de GPU/modelo local devem ser marcados
  (`@pytest.mark.gpu` ou equivalente) para poderem ser pulados em ambientes
  sem GPU.
- Teste manual ponta a ponta contra a aplicação no ar (Ollama, Qdrant,
  Postgres reais): `./testar.sh`, na raiz do repo, que chama
  `backend/scripts/teste_local.py` e dá push do relatório em
  `testes_locais/` para o agente ler. Ver `docs/TESTE_LOCAL.md`.
- Os scripts em `eval/` (ver `docs/EVALUATION.md`) não substituem os testes
  automatizados — eles medem qualidade/latência, não corretude funcional.
- Convenções de teste do frontend (Vitest, Testing Library, Playwright) estão
  em `docs/FRONTEND.md` §6, não duplicadas aqui.

## Git e commits

- Branches: `feature/<fase>-<descricao-curta>` (ex.:
  `feature/fase5-mcp-b2b-ferramentas`).
- Mensagens de commit: descrever o que mudou e referenciar o requisito e o
  item do roadmap, ex.:
  `feat(mcp-b2b): implementa ferramenta de cotação automática (R12, Fase 5)`.
- Um commit deve corresponder, quando possível, a um item concluído do
  `docs/ROADMAP.md` — facilita revisar o histórico por fase/requisito.

### Checklist antes de cada commit (qualquer ferramenta)

Criado na revisão de 2026-09-28: das 34 entregas de 25 a 27/09, só 4
atualizaram o roadmap, nenhuma marcou `# MVP:` e o lint ficou com 61 erros
no backend e 10 no frontend. Antes de commitar, confira:

1. Mensagem diz o que mudou e cita requisito/fase (`(R12, Fase 5)`);
   "últimas mudanças" ou "ajustes" não servem.
2. Item do `docs/ROADMAP.md` marcado (ou criado, se não existia).
3. Contrato de API novo ou alterado está no `docs/FRONTEND.md`; decisão
   nova ou fora do MVP está no `docs/ARCHITECTURE.md`.
4. Simplificações marcadas com `# MVP:` (`// MVP:` em TypeScript).
5. Testes novos rodam sem Postgres/Qdrant reais (seção "Testes" acima) e
   passam.
6. Lint limpo nos arquivos alterados: `uv run ruff check` e
   `uv run ruff format` (backend); `npx eslint` e `npx prettier --write`
   só nos arquivos alterados (frontend).
7. Nenhum caminho absoluto da máquina (`file:///home/...`) nem credencial
   nos `.md` e no código.
8. Nenhum documento novo fora da lista do `CLAUDE.md` (resumos, cópias de
   spec, guias paralelos): atualize o documento que já cobre o assunto.
- Não commitar arquivos de ambiente com segredos reais (`.env` — apenas
  `.env.example` vai para o repositório).

## Rollback de Versões

### Reverter a migração para o Python 3.14

Referências no git:

- tag `pre-python314-baseline` → commit `00bdaed` (estado antes da
  migração);
- `2ee1dd2`: alterações de código (PEP 695 em `b2b.py`, PEP 649 em
  `models/` e `rag/`, `pyproject.toml`); `f4a4eff`: `backend/uv.lock`;
- `5885d05`: merge da migração no `master`.

Commits posteriores podem depender do Python 3.14; depois de reverter,
rode os testes antes de subir os serviços.

**Opção A — `git revert` (recomendada, mantém o histórico):**

```bash
git checkout master && git pull origin master
git revert -m 1 5885d05 -m "revert: rollback da migracao para Python 3.14"
git push origin master
```

**Opção B — voltar à tag.** Só para inspecionar:
`git checkout pre-python314-baseline`. Para forçar o `master` de volta
(reescreve o histórico e descarta tudo o que veio depois; só com decisão
explícita do desenvolvedor):

```bash
git checkout master
git reset --hard pre-python314-baseline
git push origin master --force
```

**Ambiente virtual:** recrie o `.venv` com o Python anterior e reinstale:

```bash
cd backend
uv venv --python 3.13 .venv --clear
uv sync --all-extras
.venv/bin/python --version                   # Python 3.13.x
.venv/bin/pytest -m "not gpu and not qdrant"
```

Depois, reinicie backend e MCP B2B (`./testar.sh` já faz isso, ver
`docs/TESTE_LOCAL.md`, ou os passos do `goup.md`).

## Ao usar Claude Code CLI ou Antigravity para gerar código

- Leia `CLAUDE.md` (Claude Code) ou confirme que a regra de workspace do
  Antigravity está ativa (ver `.agents/rules/project.md`) antes de começar.
- Prefira revisar o diff/plano antes de aceitar mudanças em arquivos de
  `docs/` — esses arquivos são a fonte de verdade para futuras sessões.
- Ver `docs/AGENTIC_WORKFLOW.md` para a divisão de trabalho recomendada entre
  Antigravity (Editor View / Manager Surface) e Claude Code CLI.
