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
| Testes e lint (backend) | `pytest`, `pytest-asyncio`, `pytest-cov` (cobertura, ingerida no Repowise), `aiosqlite` (SQLite dos testes), `ruff` (lint e format) |
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

### Saúde de código — limites do Repowise ao escrever (2026-10-20)

O `get_health` do Repowise pontua cada arquivo por categoria (Size &
complexity, Organizational, Performance), com teto de dedução por categoria.
Escreva já dentro destes limites em vez de refatorar depois:

- **Complexidade ciclomática por função: no máximo 9.** Observado em
  `backend/eval/model_benchmark/run_benchmark.py`: 10, 11 e 14 foram
  sinalizados como "Complex method". Cada `if`/`elif`/`for`/`except`/`and`/`or`
  conta. Despacho por tipo vira tabela (`dict` de funções), não `if/elif`.
- **Função com no máximo ~50 linhas de código** (sem comentários e brancas).
  Observado: 69 e 75 sinalizados; 50–64 não. Cada bloco com comentário
  próprio é candidato a helper com nome.
- **Função `main`/handler/hook só orquestra**: parser de argumentos, montagem
  de clientes, listagem e laço principal são funções separadas.
- **Estes números são observados, não documentados pelo Repowise** — o limiar
  exato não está publicado. Na dúvida, confira com `get_health([arquivo])`
  depois de editar, e ajuste esta seção com o que medir.
- **"I/O in loop" cruzando funções é heurística estática** (precisão alta,
  recall baixo). É falso positivo quando o laço é o checkpoint por design
  (ex.: gravar o envelope por candidato/etapa para permitir retomada) ou
  quando o dataset é lido uma vez por etapa. Não "conserte" quebrando a
  retomada; registre o motivo em comentário curto.
- Refatoração por saúde não muda comportamento nem assinatura pública, e a
  lógica extraída ganha teste (regra 7 do `CLAUDE.md`).

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
6. Lint limpo nos arquivos alterados: em `backend/`, `uv run ruff check` e
   `uv run ruff format` sem passar caminhos. Em `cliente-b2b/` **não use
   `uv run ruff`**: o ruff não é dependência desse pacote e o comando falha
   com `Failed to spawn: ruff`. Rode o binário do backend com o cwd em
   `cliente-b2b/`, que é onde ele acha o `[tool.ruff]` certo (`py311`):
   `backend/.venv/bin/ruff check .`. No frontend, `npx eslint` e
   `npx prettier --write` só nos arquivos alterados.
7. Nenhum caminho absoluto da máquina (`file:///home/...`) nem credencial
   nos `.md` e no código.
8. Nenhum documento novo fora da lista do `CLAUDE.md` (resumos, cópias de
   spec, guias paralelos): atualize o documento que já cobre o assunto.
9. O knowledge graph (`graphify-out/`) é reconstruído pelo hook
   `post-commit` do graphify, que **voltou a funcionar em 2026-10-17**: o bit
   de execução de `.git/hooks/post-commit` tinha caído (o git o ignorava com
   um `hint:` e nenhum commit reconstruía o grafo) e foi restaurado com
   `chmod +x .git/hooks/post-commit`. Se o `hint:` reaparecer, o bit caiu de
   novo — rode `graphify update .` à mão até refazer o `chmod`. O
   `graphify-out/` é
   versionado: se o rebuild pegar trabalho não commitado de outra ferramenta,
   não commite o artefato — deixe que quem está no meio da tarefa o
   reconstrua ao fechar.
10. **GitNexus foi desativado** em 2026-10-17 (MCP e os dois hooks globais),
    **com revisão futura prevista** — por ora não há nada a rodar antes do
    commit. Motivo e evidência na seção "Ordem
    de uso das ferramentas de grafo de código", no fim deste documento.
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

    **A checagem de símbolo está inerte (achado de 2026-10-17).** Com o
    índice recém-atualizado, `--kind symbol` devolve zero achados, embora
    `sync_produto_no_rag` e `remover_produto_do_rag` sigam citados em
    `docs/ARCHITECTURE.md:2036` e `docs/ROADMAP.md:703` sem existir no
    código — exatamente o caso que o baseline gravou como aceito em
    2026-10-15 (24 entradas `symbol`). Enquanto estiver assim, o item 11 só
    cobre referência a **caminho**; não conte com ele para pegar símbolo
    fantasma, e **não pode as 24 entradas do baseline**, que voltarão a valer
    quando o detector voltar. `scripts/checar_mudanca.py` imprime um `AVISO`
    a cada rodada enquanto o sintoma persistir.

    **O gate aplica o baseline por conta própria.** O `--baseline` do
    repowise impede a falha mas continua imprimindo os 34 achados aceitos, o
    que afoga um achado novo. Por isso `scripts/checar_mudanca.py` chama o
    detector com `--format json`, filtra contra o baseline e imprime só o que
    é novo, mais uma linha de contagem do que foi omitido. O corte de
    confiança (`0.7`) é o mesmo default do `--fail-on-confidence`.

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

**Cobertura para o Repowise** (relatório + mapa teste→código; 2026-10-20: 91,3 %
de linhas, 1226 testes). A partir da raiz, depois de rodar na pasta `backend`:

```bash
cd backend && .venv/bin/pytest -q --cov=src/app --cov-context=test
cd .. && repowise coverage add backend/.coverage && rm backend/.coverage
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
  `CLAUDE.md` e hooks `PreToolUse` ao `.claude/settings.json`. **Não re-rode
  sem necessidade:** os dois hooks `PreToolUse` e o mandato "consulte o grafo
  antes de abrir arquivo" foram removidos deliberadamente em 2026-10-17 (ver
  a última seção deste documento), e o instalador os traz de volta. Em 2026-10-14
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

### Ordem de uso das ferramentas de grafo de código

**Decisão de 2026-10-17: consolidado em uma ferramenta.** O repositório
chegou a ter **quatro** sistemas de inteligência de código ao mesmo tempo —
Repowise (MCP), GitNexus (MCP), Serena (MCP) e Graphify (CLI + hooks) — todos
respondendo às mesmas perguntas ("quem chama X", "onde está Y"). O custo não
era o contexto injetado, eram os **hooks**: uma única chamada de Bash
disparava quatro (`graphify hook-guard search`, `repowise-rewrite` e o hook do
GitNexus em `PreToolUse`, mais o do GitNexus em `PostToolUse`), e cada
resultado vinha com o lembrete "MANDATORY: run graphify query before
grepping".

O que decidiu: numa sessão longa de trabalho real (Fase 10, 2026-10-17), as
ferramentas MCP de Repowise, GitNexus e Serena tiveram **zero** chamadas; o
trabalho saiu de `Bash`, `Read` e meia dúzia de `graphify query` que, em todos
os casos, ainda exigiram `grep`/`Read` depois. E o diferencial do Graphify —
indexar fonte que não é código — **nunca foi exercitado**: o grafo tinha 0 nós
vindos de PDF, apesar dos 97 PDFs do corpus ControlId.

**Fonte única para código: Repowise.** Não por ser melhor em grafo, mas por
ser o único com mineração de histórico git, `get_why` (decisões registradas),
código morto e `distill` — e por já estar casado com o projeto (`.claude/CLAUDE.md`
é gerado por ele, e o gate de deriva de documentação do item 11 do checklist
é dele).

1. **Orientar e medir — Repowise.** `get_answer` para pergunta de
   how/where/why; `search_codebase` para identificador ou literal;
   `get_context(include=["references"])` antes de renomear ou atualizar
   chamadores; `get_risk` antes de editar arquivo muito importado e
   `get_change_risk` antes de commitar mudança multi-arquivo; `get_why` antes
   de divergir de um padrão estabelecido.
2. **Ler e editar.** O grafo orienta, não substitui: ler o arquivo bruto
   continua obrigatório antes de alterá-lo, e o Claude Code exige um `Read`
   do arquivo antes de um `Edit`.
3. **Fechar.** Item 9 do checklist acima (grafo do Graphify) e item 11
   (gate de deriva de documentação).

**Graphify: CLI mantida, hooks removidos.** `graphify query`, `explain` e
`path` continuam disponíveis e são úteis para um mapa macro rápido, mas
**não são obrigatórios e não precedem mais o `grep`**. Os dois hooks
`PreToolUse` que impunham isso saíram de `.claude/settings.local.json` em
2026-10-17. O caso em que o Graphify ganha de todos — cruzar código com PDF,
schema de banco ao vivo ou paper no mesmo grafo — continua valendo; para isso
é preciso rodar `/graphify --update` sobre o material não-código, o que nunca
foi feito aqui.

**GitNexus: desativado, a rever.** Não é decisão definitiva — o dono pediu
revisão futura em 2026-10-17, então o que segue descreve por que ele saiu
agora, não um veredito permanente. O MCP saiu de `~/.claude.json`
(`claude mcp remove gitnexus -s user`) e os dois hooks globais saíram de
`~/.claude/settings.json`, em 2026-10-17. Motivo: índice 16 commits defasado,
zero usos, dois processos no ar (`gitnexus mcp` e `gitnexus serve -p 4757`) e
um hook avisando da defasagem em cada chamada de Bash — ruído puro, dado que
"índice defasado não bloqueia nada" já era a decisão do dono (2026-10-15). Os
skills `gitnexus-*` continuam instalados e inertes; os manuais em
`docs/Manuais/gitnexus-manual.md` ficam como referência histórica.

**Serena: removida** em 2026-10-17 (`claude mcp remove serena`), fechando a
consolidação. Era a mais barata das quatro — nenhum hook, e tools *deferred*,
que só entram no contexto sob demanda — então o motivo não foi custo:

- Zero usos, e `.serena/memories/` **vazio** depois de 9 dias instalada: nada
  a perder na remoção.
- O diferencial real dela são as **edições guiadas por language server**
  (`rename_symbol`, `replace_symbol_body`, `safe_delete_symbol`), que nunca
  se encaixaram no fluxo daqui: o Claude Code exige `Read` antes de `Edit`, e
  o `get_diagnostics_for_file` cobre o que `ruff`/`eslint` do checklist já
  pegam.
- O sistema de memória dela seria o **terceiro** do projeto, ao lado do
  claude-mem e do auto-memory, com risco de registro dividido.

`.serena/project.yml` foi **preservado** (e `.serena/` é gitignored), só o
cache de LSP de 18 MB foi apagado — reinstalar é um comando, sem
reconfigurar. **Quando vale trazer de volta:** um rename grande no frontend
TypeScript, onde o `rename_symbol` segue tipos e é genuinamente melhor que
grep-and-replace. Para isso, reinstale para a tarefa e remova depois.

**Resultado da consolidação:** sobrou **um** sistema de inteligência de
código (Repowise) e **um** hook por chamada de Bash (`repowise-rewrite`),
contra quatro sistemas e quatro hooks antes.

#### O que foi verificado do Repowise, e o que está limitado

A substituição foi **testada** em 2026-10-17, não presumida — a recomendação
original saiu da lista de recursos, sem uso em sessão real.

**Funciona, com ground truth conferido:**

- `search_codebase` em modo símbolo: achou `ndcg_at_k` em
  `backend/eval/rag_ingestion/metricas.py:98-119`, com `complete: true` e as
  três ocorrências (definição, chamada, referência). `exact_match: true`.
- **O índice se auto-atualiza.** `indexed_commit` igual ao `live_head`,
  `index_behind: false`, `index_age_days: 0` — sem ninguém rodar
  `repowise update`. É a diferença prática contra o GitNexus, que ficou 16
  commits atrás.
- O gate de deriva de documentação (item 11) e o `repowise distill` foram
  usados a sessão toda.

**Limitação por configuração: busca semântica desligada.**
`.repowise/config.yaml` tem `embedder: mock`, então `semantic_search: false`
e consultas em prosa caem para full-text. Não é defeito nem regressão em
relação ao Graphify (cuja `query` também não usa embeddings — é travessia
estrutural sobre AST), mas é bom saber: para pergunta conceitual, o caminho
que funciona é `get_answer`, que faz recuperação híbrida, e não
`search_codebase` com texto livre.

**Defeito encontrado e corrigido: síntese do `get_answer`.** Com o orçamento
padrão de 1024 tokens, o `gemma4:12b-it-q4_K_M` gastava o orçamento inteiro
em raciocínio oculto e não emitia resposta — `get_answer` voltava
`degraded: "synthesis-failed"`, `confidence: low`,
`retrieval_quality: weak`. Com `REPOWISE_SYNTHESIS_MAX_TOKENS=4096`,
verificado, a síntese funciona e a confiança sobe para `medium`, citando os
arquivos certos. Fixado em dois lugares, porque atendem consumidores diferentes:

- `.claude/settings.local.json` → bloco `env` do projeto, herdado pelos
  subprocessos da sessão, **inclusive o servidor MCP do plugin** (que não tem
  bloco `env` próprio). Exige reiniciar a sessão para o servidor herdar.
- `.repowise/.env` → para o CLI (`repowise ask`).

**Nenhum dos dois é versionado** (`.gitignore:48` cobre `.repowise/` e a
`:53`/`:54` cobrem `.claude/` e `.mcp.json`), então a correção **não**
sobrevive a um clone novo — é passo manual de máquina nova, registrado no
`goup.md` (passo 0.8).

#### Instalado como plugin, não como servidor MCP avulso (2026-10-17)

Até esta data o Repowise entrava por um servidor MCP declarado à mão em
`.mcp.json`, e os três hooks dele estavam **copiados à mão** em
`~/.claude/settings.json`. Descobriu-se que esses três hooks eram
byte-idênticos aos que o plugin oficial provê — alguém os havia copiado de
lá, ou um instalador antigo o fez. Instalar o plugin **por cima** teria
disparado os três duas vezes por evento.

A troca feita, em vez de somar: os três hooks copiados saíram de
`~/.claude/settings.json`, o plugin foi instalado
(`/plugin marketplace add repowise-dev/repowise` e
`/plugin install repowise@repowise`), e o servidor duplicado saiu do
`.mcp.json` (`claude mcp remove repowise`), que ficou com `mcpServers: {}`.

| Depois da troca | |
| --- | --- |
| Servidor MCP | um só, `plugin:repowise:repowise` (ferramentas `mcp__plugin_repowise_repowise__*`) |
| Hooks por chamada de Bash | **1** — `repowise-rewrite`, que o plugin **não** traz e por isso continua declarado à mão |
| Dono dos outros 3 hooks | o plugin (`SessionStart`, `PostToolUse`, `PostToolUseFailure`) |
| Versão | 0.57.0 (era 0.56.0) |

**Armadilha encontrada na troca:** o servidor do `.mcp.json` era o que
carregava o `REPOWISE_SYNTHESIS_MAX_TOKENS`. Removê-lo sem mais faria perder
o conserto da síntese **em silêncio** — daí a variável ter migrado para o
`env` do projeto antes da remoção.

**O plugin também traz ~20 skills `repowise:*`**, seis delas de **auto-disparo
por descrição** (`pre-modification`, `change-review`, `code-health`,
`codebase-exploration`, `dead-code-cleanup`, `architectural-decisions`) — a
mais abrangente é a `pre-modification` ("before modifying, refactoring, or
deleting files"). Skill não roda a cada chamada de ferramenta como hook,
então é mais barata e mais pertinente; se incomodar, `skillOverrides` em
`~/.claude/settings.json` aceita `"off"` ou `"user-invocable-only"` por
skill. O **Lens** (módulo do plugin, com `/lens` e seis toggles, quatro
`true` por padrão, um deles rodando a cada turno que edita arquivo) foi
instalado **desligado** via `pluginConfigs`, para a instalação não alterar o
custo por turno; acender um a um, se e quando for avaliado.

**Fato operacional que vale lembrar:** a síntese do Repowise roda no
`gemma4:12b-it-q4_K_M` via Ollama (`.repowise/config.yaml`), que é **o mesmo
modelo gerador do próprio assistente**. Ou seja, `get_answer` disputa a GPU
com o sistema avaliado — não usar durante uma rodada de benchmark da Fase 10,
sob pena de contaminar a medição de latência.

Pendências conhecidas, nenhuma bloqueante: o índice está em
`status: "upgrading"` (`Full upgrade: pending`), e o servidor roda 0.56.0 com
a 0.57.0 disponível.

#### Ler fonte do repo com `Read`/`Grep`, não com `cat`/`grep`

**Achado de 2026-10-17, e é a diferença entre o Repowise ajudar ou ficar no
escuro.** A camada automática dele — `read_skeleton` e `search_digest`,
ligadas em `.repowise/config.yaml` — é servida pelo hook `repowise-augment`,
cujo matcher é `Grep|Glob|Read|Edit|Write|mcp__.*repowise.*`. **`Bash` não
está ali, e não deve estar:** medido, um payload de `Bash` não move o estado
do hook (`seq` parado, arquivo não registrado), porque ele não analisa
`tool_input.command` para extrair caminho. Pôr `Bash` no matcher dispararia o
hook em toda chamada e não produziria nada.

Consequência prática, com a evidência da sessão que descobriu isso: ao
trabalhar lendo com `cat`/`sed -n` e buscando com `grep`, o estado do hook
terminou com **`reads: {}` e `served: {}` em 19 execuções** — o Repowise
registrou os 8 arquivos escritos (via `Write`/`Edit`, que casam com o
matcher) e serviu orientação **zero vez**. Um `Read` de arquivo do repo, no
mesmo estado, foi registrado na hora com hash, tamanho e `seq`.

**Regra, então:**

- **Fonte do repo que você vai entender ou editar → `Read` e `Grep`.** É o
  que acende o digest e o skeleton, e é o que faz o Repowise avisar de
  arquivo defasado ou já lido.
- **`Bash` para o que é comando de verdade:** git, `pytest`, `ruff`,
  `scripts/checar_mudanca.py`, `graphify update`, scripts do `eval/`.
- Para pergunta de how/where/why, `get_answer`; para resolver identificador,
  `search_codebase` — chamada explícita, que não depende de hook nenhum.

No Claude Code existe um empurrão na direção contrária: com
`permissions.defaultMode: "auto"` (em `~/.claude/settings.json`), o modo auto
orienta a ler com `cat`/`head`/`sed -n` e buscar com `grep`/`find` em vez das
ferramentas dedicadas. Para **fonte do repo**, a augmentação do Repowise é a
razão de preferir a ferramenta dedicada mesmo assim; a orientação do modo
auto segue valendo para todo o resto. (O conflito de configuração é
específico do Claude Code; o princípio — usar o canal que a camada de índice
escuta — vale para as três ferramentas.)

**Nenhum hook foi adicionado para forçar isto.** A alternativa mecânica
considerada e descartada por ora era um `PreToolUse` filtrado em
`Bash(grep:*)` injetando um lembrete; fica registrada como o caminho a seguir
**se** o hábito não pegar, e não antes, porque reintroduz custo por chamada
exatamente onde ele foi cortado.
