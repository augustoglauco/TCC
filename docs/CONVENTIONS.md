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
  cada commit. Os **dois** pacotes Python do repositório têm o mesmo conjunto
  de regras (`line-length = 100`, `select = ["E", "F", "I", "UP", "B"]`),
  configurado em `backend/pyproject.toml` e em `cliente-b2b/pyproject.toml`
  (adicionado em 2026-10-14; antes `cliente-b2b/` não tinha configuração
  própria e ficava fora de qualquer verificação). Rode `ruff check` e
  `ruff format` **na raiz de cada pacote** — um `ruff check` com caminhos
  explícitos (`ruff check src/ tests/`) deixa de fora o que não foi listado,
  foi assim que `backend/migrations/` acumulou 11 violações de E501 sem
  ninguém ver.
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
- **Sobrescrever a dependência `get_db_session` não basta.** A telemetria
  (`app.services.ai_usage` e `app.services.ingestion_metrics`) grava em
  *fire-and-forget*, por um sessionmaker **global de módulo** que o lifespan
  de `app.main` aponta para `settings.postgres_dsn` — caminho que não passa
  por nenhuma dependência do FastAPI. Até 2026-10-12, um teste que subia a
  app de verdade (`with TestClient(app)`) deixava esse global apontando para
  o Postgres do desenvolvedor, e os testes seguintes gravavam lá os dados
  dos seus dublês: 129 eventos de IA com modelo "desconhecido" apareceram no
  painel `/admin/metricas` como se fossem uso real. Duas fixtures `autouse`
  em `conftest.py` fecham isso — `_isola_banco_de_telemetria` (troca o DSN
  por um SQLite descartável da sessão de testes, com schema) e
  `_reset_sessionmakers_globais` (zera os dois globais entre testes). Ao
  criar um serviço novo com sessionmaker global, acrescente-o à segunda.
- Testes que dependem de GPU/modelo local devem ser marcados
  (`@pytest.mark.gpu` ou equivalente) para poderem ser pulados em ambientes
  sem GPU.
- `backend/pyproject.toml` fixa `pythonpath = ["src"]` em
  `[tool.pytest.ini_options]` (commit `40f99de`). Achado ao preparar um
  worktree deste repositório: o `.venv` instala o pacote em modo editável
  via um `.pth` com caminho **absoluto** para o checkout principal, então
  sem esse `pythonpath` a suíte roda num worktree mas importa `app` do
  checkout principal — passa (ou falha) em silêncio contra o código
  errado. Não remova essa opção ao tocar no `pyproject.toml`.
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

**Atalho (2026-10-15): `scripts/checar_mudanca.py`.** Cobre os itens 5, 6,
9–11 de forma proporcional à mudança, olhando só o que difere do `HEAD`:
ruff + pytest só dos testes que importam (direta ou por um importador) os
módulos alterados; prettier/eslint + `vitest related` só nos arquivos
alterados do frontend; gate de deriva de docs (`--since HEAD`: só a deriva pela qual a mudança
responde) e só se há `.md` alterado ou arquivo apagado/renomeado. GitNexus e Graphify são ferramentas de
consulta: o script não os executa e um índice defasado não bloqueia nada. `--dry-run` mostra o plano, `--full-backend` força a suíte inteira
e `--e2e` inclui o smoke do Playwright (fora do padrão: só ao mexer em
fluxo de chat/widget). **Não rode `graphify update .` à mão antes de
commitar** (item 9): o hook `post-commit` já reconstrói o grafo. A suíte
completa e o Playwright ficam para mudança transversal (`config.py`,
`db/models.py`, contrato de API) ou antes de entregar uma fase.

1. Mensagem diz o que mudou e cita requisito/fase (`(R12, Fase 5)`);
   "últimas mudanças" ou "ajustes" não servem.
2. Item do `docs/ROADMAP.md` marcado (ou criado, se não existia).
3. Contrato de API novo ou alterado está no `docs/FRONTEND.md`; decisão
   nova ou fora do MVP está no `docs/ARCHITECTURE.md`.
4. Simplificações marcadas com `# MVP:` (`// MVP:` em TypeScript).
5. Testes novos rodam sem Postgres/Qdrant reais (seção "Testes" acima) e
   passam.
6. Lint limpo nos arquivos alterados: `uv run ruff check` e
   `uv run ruff format` (backend e `cliente-b2b/`, cada um na sua raiz, sem
   passar caminhos); `npx eslint` e `npx prettier --write` só nos arquivos
   alterados (frontend).
7. Nenhum caminho absoluto da máquina (`file:///home/...`) nem credencial
   nos `.md` e no código.
8. Nenhum documento novo fora da lista do `CLAUDE.md` (resumos, cópias de
   spec, guias paralelos): atualize o documento que já cobre o assunto.
9. O knowledge graph (`graphify-out/`) é reconstruído pelo hook `post-commit`
   do graphify; só rode `graphify update .` à mão para consultar o grafo
   antes de commitar.
10. GitNexus é ferramenta de consulta: não há análise obrigatória antes do
    commit, e índice defasado não bloqueia nada (decisão do dono, 2026-10-15).
11. Se mexeu em `.md` ou renomeou/apagou arquivo citado por documento, rode
    o gate de deriva de documentação:

    ```bash
    repowise update --working-tree    # obrigatório: ver a armadilha abaixo
    repowise doc-drift --check \
      --kind path --kind link --kind anchor --kind command --kind symbol \
      --baseline .doc-drift-baseline.json
    ```

    Sai 0 quando não há deriva nova e 1 quando há, citando documento e linha.
    Os `--kind` são necessários: sem eles o detector não checa referência a
    símbolo, que é a classe que pegou o módulo fantasma `app.rag.product_sync`
    em `docs/ARCHITECTURE.md` — ver o achado abaixo.

    **Armadilha (medida em 2026-10-15):** `--kind symbol` resolve contra o
    índice do repowise, e o índice reflete o **último commit** — não o que
    está no disco. Com edições de `.md` ainda não commitadas (o caso normal
    ao rodar um checklist de pré-commit), o mesmo comando devolve 38 achados
    em vez de 72; e se o baseline for gravado nesse estado, as ~34
    referências a símbolo saem dele e voltam como "deriva nova" na execução
    seguinte, com o gate falhando sem nada ter mudado nos documentos. Um
    `repowise update` simples **não** resolve: é preciso
    `repowise update --working-tree`, que inclui as edições não commitadas.
    Com isso o resultado é estável (verificado em duas execuções seguidas).

    O `.doc-drift-baseline.json` registra os 72 achados que existiam em
    2026-10-15 e por isso o gate só reclama de **deriva nova**: 54 deles estão
    em `docs/superpowers/plans|specs/`, documentos datados de design em que
    citar um arquivo renomeado depois é história correta, não defeito; e vários
    dos demais são menções deliberadas ao que foi apagado na consolidação de
    2026-09-28 ("do antigo `MANUAL_...`"). Para aceitar deriva nova de
    propósito, regrave o baseline trocando `--baseline` por
    `--write-baseline` e commite o arquivo junto, explicando no commit.
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

## Ao usar Claude Code CLI, Antigravity ou Kiro CLI para gerar código

- Leia `CLAUDE.md` (Claude Code) ou confirme que a regra de workspace está
  ativa (Antigravity: `.agents/rules/project.md`; Kiro:
  `.kiro/steering/project.md`) antes de começar.
- Prefira revisar o diff/plano antes de aceitar mudanças em arquivos de
  `docs/` — esses arquivos são a fonte de verdade para futuras sessões.
- Ver `docs/AGENTIC_WORKFLOW.md` para a divisão de trabalho recomendada entre
  Antigravity (Editor View / Manager Surface), Claude Code CLI e Kiro CLI.

### Ferramentas que escrevem nos arquivos de regras

`graphify`, `gitnexus` e `repowise` têm instaladores que **escrevem no
`CLAUDE.md` e em `.claude/`** — bloco de instruções próprio, entradas de MCP,
skills e hooks de git. Isso já sobrescreveu diretriz do projeto mais de uma
vez, então, ao (re)instalar qualquer uma delas:

- **`repowise init`**: passe `--no-claude-md`, senão o gerador padrão
  substitui o `CLAUDE.md` do projeto (ver `docs/Manuais/repowise-manual.md`).
- **`graphify install --platform claude`**: anexa um bloco de instruções ao
  `CLAUDE.md` e hooks `PreToolUse` ao `.claude/settings.json`. Em 2026-10-14
  isso duplicou a seção "Graphify" (em inglês, sem delimitador). A seção agora
  fica entre `<!-- graphify:start -->` e `<!-- graphify:end -->`; confira se o
  instalador respeitou o delimitador em vez de anexar de novo.
- **`gitnexus setup`**: regenera o bloco entre `<!-- gitnexus:start -->` e
  `<!-- gitnexus:end -->` e reinstala MCP/skills/hooks. Conteúdo dentro desses
  marcadores é gerado — não edite à mão, que a próxima execução descarta.
- **Hook com caminho absoluto não vai para arquivo versionado.**
  `.claude/settings.json` é commitado e lido também pelo Antigravity e pelo
  Kiro; um `command` com `/home/<usuário>/...` quebra em qualquer outra
  máquina (ver `goup.md`, passo 0). Esse tipo de hook mora em
  `.claude/settings.local.json`, que não é versionado.
- **Depois de instalar, rode `git status`** e reverta o que o instalador
  mexeu fora do que você pediu. É a mesma regra do item 7 do checklist (nada
  de caminho absoluto da máquina em arquivo versionado).

### Ordem de uso dos dois grafos de código

O repositório é indexado por **duas** ferramentas de grafo, e as duas pedem
para ser consultadas "primeiro". Elas não competem: são etapas em sequência
de uma mesma tarefa. Registrado aqui (e não nos arquivos de regras) para
existir uma única descrição, válida para as três ferramentas — o bloco do
GitNexus no `CLAUDE.md` é gerado por `gitnexus setup` e reescrito a cada
execução, então não serve de fonte de verdade.

1. **Orientar — Graphify.** `graphify query "<pergunta>"` para um subgrafo
   enxuto, `graphify explain "<símbolo/conceito>"` para um nó focalizado,
   `graphify path "<A>" "<B>"` para a dependência entre dois pontos. Serve
   para descobrir *onde* está o quê antes de abrir arquivo.
2. **Medir o alcance — GitNexus.** `impact` no símbolo que você vai mexer,
   antes de editar: quem chama, que fluxos passam ali, qual o risco.
   `risk: UNKNOWN` não é risco baixo — significa que a varredura não
   respondeu, e aí vale confirmar por busca textual.
3. **Ler e editar.** O grafo orienta, não substitui: ler o arquivo bruto
   continua obrigatório antes de alterá-lo.
4. **Fechar.** Atualizar os dois grafos antes de commitar — itens 9 e 10
   do checklist acima, que são a única descrição desses comandos.
