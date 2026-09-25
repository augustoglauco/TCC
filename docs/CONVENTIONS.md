# Convenções de Desenvolvimento

## Stack

- **Python 3.11+**, framework **FastAPI** (async-first) para as APIs do chat
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
- Não commitar arquivos de ambiente com segredos reais (`.env` — apenas
  `.env.example` vai para o repositório).

## Ao usar Claude Code CLI ou Antigravity para gerar código

- Leia `CLAUDE.md` (Claude Code) ou confirme que a regra de workspace do
  Antigravity está ativa (ver `.agents/rules/project.md`) antes de começar.
- Prefira revisar o diff/plano antes de aceitar mudanças em arquivos de
  `docs/` — esses arquivos são a fonte de verdade para futuras sessões.
- Ver `docs/AGENTIC_WORKFLOW.md` para a divisão de trabalho recomendada entre
  Antigravity (Editor View / Manager Surface) e Claude Code CLI.
