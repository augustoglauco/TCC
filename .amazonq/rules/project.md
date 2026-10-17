# Regra de Projeto — Assistente Virtual Multimodal (TCC) — Amazon Q Developer CLI

Este é o arquivo de regras do **Amazon Q Developer CLI** para este projeto.
O agente padrão inclui `file://.amazonq/rules/**/*.md` automaticamente, então
este arquivo entra no contexto sem nenhum `/context add`.

Ele cumpre o mesmo papel que `CLAUDE.md` (Claude Code CLI),
`.agents/rules/project.md` (Antigravity) e `.kiro/steering/project.md` (Kiro
CLI): dar a todo agente o contexto do projeto **antes de iniciar qualquer
trabalho**. As quatro ferramentas apontam para os mesmos documentos em
`docs/` — a fonte de verdade única.

> **Não confunda com `AGENTS.md` na raiz.** O Amazon Q **não** lê `AGENTS.md`
> nativamente (feature request `aws/amazon-q-developer-cli#2712`), e aquele
> arquivo é artefato gerado por uma ferramenta que foi removida do projeto em
> 2026-10-17. Este arquivo aqui é o que vale.

**Não duplique arquitetura ou escopo aqui.** Leia os documentos abaixo (na
raiz do workspace) antes de propor ou implementar qualquer mudança:

- `CLAUDE.md` — o "como trabalhar aqui" (regras 1–11). Leia por completo.
- `docs/ARCHITECTURE.md` — arquitetura completa, os 12 requisitos funcionais
  (R1–R12), escopo do MVP x evolução futura, riscos conhecidos.
- `docs/ROADMAP.md` — próxima tarefa a implementar e progresso (checklist por
  fase).
- `docs/CONVENTIONS.md` — stack (Python/FastAPI + Next.js), estrutura de
  pastas (monorepo), estilo de código, convenções de teste e git.
- `docs/FRONTEND.md` — interface (site + widget de chat), stack Next.js e
  contrato de API com o backend.
- `docs/EVALUATION.md` — avaliação experimental (acurácia do roteador,
  qualidade do RAG, latência local x externo).
- `docs/AGENTIC_WORKFLOW.md` — divisão de trabalho entre as ferramentas
  agênticas e loop de trabalho recomendado.
- `docs/TESTE_LOCAL.md`, `goup.md` (instalação e subida do ambiente) e
  `docs/Manuais/` — lista completa e a regra de "não criar documentos
  paralelos" estão na tabela do `CLAUDE.md`.

## Antes de iniciar qualquer trabalho

1. Leia `CLAUDE.md` por completo e o(s) documento(s) de `docs/` relevante(s)
   para a tarefa (ver tabela "Documentos de referência" em `CLAUDE.md`).
2. Confirme que a tarefa está descrita como **MVP** em
   `docs/ARCHITECTURE.md` §5 e/ou `docs/ROADMAP.md`. Em dúvida sobre escopo,
   pergunte ao desenvolvedor antes de codificar.

## Estilo de código — o que mais costuma passar batido

A configuração do `ruff` deste projeto usa **largura de linha 100**, e é
verificada no checklist de commit. Rodar o formatador **da raiz de cada
pacote, sem passar caminhos**:

```bash
cd backend      && uv run ruff format && uv run ruff check
cd cliente-b2b  && uv run ruff format && uv run ruff check
cd frontend     && npx prettier --write <arquivos alterados> && npx eslint <arquivos alterados>
```

E a checagem proporcional à mudança, que é o portão antes de commitar:

```bash
backend/.venv/bin/python scripts/checar_mudanca.py
```

Ela roda ruff + os testes que importam os módulos alterados, prettier/eslint
nos arquivos de frontend alterados, e o gate de deriva de documentação. Sai 0
quando está tudo certo. **Arquivos mais sujeitos a regressão**, que pedem
cuidado extra e teste rodado: `backend/src/app/router/orchestrator.py`,
`backend/src/app/api/chat.py`, `backend/src/app/router/classifier.py` e os
testes correspondentes.

## Regras rápidas (resumo — a versão completa está em `CLAUDE.md`)

1. **Escopo do MVP é lei.** Não implemente itens de "Evolução futura" ou da
   lista "fora do MVP" sem decisão explícita do desenvolvedor.
2. **Marque simplificações de MVP no código** com `# MVP: <limitação>`
   (`// MVP: ...` em TypeScript), referenciando `docs/ARCHITECTURE.md`.
3. **Diffs pequenos e rastreáveis**, focados em um item de `docs/ROADMAP.md`;
   referencie o requisito (ex.: `R4`, `R12`) e a fase na mensagem de commit.
4. **Nunca invente credenciais/chaves de API reais** — use variáveis de
   ambiente documentadas em `.env.example`.
5. **Ao concluir uma tarefa, marque a caixa** (`- [x]`) do item em
   `docs/ROADMAP.md`; se a tarefa não existir no roadmap, adicione-a antes.
6. **Decisão de arquitetura nova → atualize `docs/ARCHITECTURE.md` primeiro**
   (ou junto), nunca só no commit.
7. **Teste o que for testável antes de concluir** — roteador, RAG e handlers
   do MCP B2B em especial (ver `docs/CONVENTIONS.md`).
8. **Na dúvida entre duas abordagens, prefira a mais simples** que atenda ao
   MVP — este é um protótipo de TCC, não um produto de produção.
9. **Documentação sempre reflete o estado atual.** Ao mudar stack, estrutura
   de pastas, contrato de API, fluxo ou convenção de teste, atualize o `.md`
   correspondente na mesma tarefa.
10. **Antes de cada commit, siga o checklist** de `docs/CONVENTIONS.md`
    ("Checklist antes de cada commit").
11. **Prompt/instrução de LLM alterado ou novo → revise
    `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md`.** Vale para qualquer texto
    enviado a um LLM: prompts de sistema, playbooks por domínio, templates de
    extração estruturada, prompts de visão.

## Ferramentas de inteligência de código

**Repowise é a fonte única** (decisão de 2026-10-17). O GitNexus foi
desativado, com revisão futura prevista — enquanto isso, ignore qualquer
instrução que mande rodar `impact`,
`detect-changes` ou `node .gitnexus/run.cjs`, inclusive a do `AGENTS.md` da
raiz. O Graphify segue disponível como CLI opcional (`graphify query`,
`explain`, `path`) e **não** precede o `grep`. Motivo e evidência em
`docs/CONVENTIONS.md`, "Ordem de uso das ferramentas de grafo de código".

## Trabalho concorrente — importante neste repo

Quatro ferramentas agênticas compartilham este repositório **e a mesma
identidade git**. Consequências práticas:

- Uma árvore limpa pode significar que outra ferramenta já commitou o seu
  trabalho. Confira `git log` antes de concluir que algo foi perdido.
- Commite **apenas os arquivos da sua tarefa** (`git add <caminhos>`), nunca
  `git add -A` nem `git commit -a`: há boa chance de haver trabalho de outra
  ferramenta não commitado na árvore.
- Se `scripts/checar_mudanca.py` falhar em arquivo que você não tocou,
  provavelmente é trabalho em andamento de outra ferramenta — relate, não
  corrija por conta.

## Regra de ouro (comum às quatro ferramentas)

Ao mudar uma decisão de arquitetura ou escopo, edite os documentos em
`docs/` — nunca duplique a decisão apenas nos arquivos de regras
(`CLAUDE.md`, `.agents/rules/project.md`, `.kiro/steering/project.md`, este
arquivo). Os arquivos de regras ficam curtos e estáveis; `docs/` concentra o
conteúdo que muda.
