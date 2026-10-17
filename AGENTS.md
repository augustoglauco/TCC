# AGENTS.md — este não é o arquivo de regras deste projeto

Se você é um agente e chegou aqui procurando as regras do projeto, elas não
estão neste arquivo. Cada ferramenta tem o seu:

| Ferramenta | Arquivo de regras |
| --- | --- |
| Claude Code CLI | `CLAUDE.md` (raiz) |
| Antigravity | `.agents/rules/project.md` |
| Kiro CLI | `.kiro/steering/project.md` |
| Amazon Q Developer CLI | `.amazonq/rules/project.md` |

Os quatro são ponteiros curtos para os documentos em `docs/`, que são a fonte
de verdade única. Comece por `CLAUDE.md` e pela tabela "Documentos de
referência" nele. A divisão de trabalho entre as ferramentas está em
`docs/AGENTIC_WORKFLOW.md`.

## Por que este arquivo existe assim

Até 2026-10-17 este arquivo era um bloco gerado pelo **GitNexus**, que
instruía a rodar `impact` antes de qualquer edição e `detect-changes` antes
de qualquer commit. **O GitNexus foi desativado do projeto** naquela data
(MCP e hooks), **com revisão futura prevista** — não é decisão definitiva.
Enquanto isso, aquelas instruções não valem: elas apontam para uma
ferramenta que não está no fluxo.

A ferramenta de inteligência de código em uso é o **Repowise**
(`get_answer`, `search_codebase`, `get_context`, `get_why`). O **Graphify**
segue disponível como CLI opcional e não precede o `grep`. Motivo e evidência
em `docs/CONVENTIONS.md`, seção "Ordem de uso das ferramentas de grafo de
código".

### Bloco do GitNexus, preservado comentado

O bloco original está no fim deste arquivo, **dentro de um comentário HTML** —
inerte para quem lê o arquivo renderizado, e pronto para voltar quando o
GitNexus for reavaliado. Não siga nada do que está ali enquanto estiver
comentado.

Os dois marcadores `gitnexus:start`/`gitnexus:end` foram retirados de
propósito: comentário HTML não aninha, e o primeiro `-->` encerraria o
comentário externo. Como efeito colateral desejado, um `gitnexus setup`
futuro não vai encontrar os marcadores e escreverá um bloco novo e atual, em
vez de remendar este — que aí pode ser apagado. A versão intacta, com os
marcadores, está em `git show 55b83ed^:AGENTS.md`.

**Nota sobre o Amazon Q:** ele **não** lê `AGENTS.md` nativamente — é um
feature request aberto (`aws/amazon-q-developer-cli#2712`). O arquivo que ele
lê é `.amazonq/rules/**/*.md`, incluído automaticamente pelo agente padrão.
Não mova as regras para cá esperando que ele as veja.

> `frontend/AGENTS.md` é outra coisa e não tem relação com este arquivo: é
> gerado e reescrito pelo `next dev` a cada subida do servidor de
> desenvolvimento. Não edite o bloco dele (ver `CLAUDE.md`).

---

<!--
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **TCC** (9509 symbols, 16710 relationships, 451 execution flows).

> Index stale? Run `node .gitnexus/run.cjs analyze --index-only` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? Bootstrap with `npx`, `bunx`, or `pnpm dlx` — e.g. `bunx gitnexus@latest analyze` (npm 11 npx crash; #1939).

## Always Do

- **MUST run impact before editing.** Use `impact({target: "symbolName", direction: "upstream"})` or `node .gitnexus/run.cjs impact "symbolName" --direction upstream --repo .`; report callers, processes, and risk. Never substitute grep for graph analysis.
- **MUST analyze graph changes before committing.** Use `detect_changes({scope: "all"})` (MCP) or `node .gitnexus/run.cjs detect-changes --scope all --repo .` (CLI fallback). `partial: true` or `truncated: true` is not a clean check — a zero means unseen, not unaffected; re-run it. For regression review: `detect_changes({scope: "compare", base_ref: "master"})` or `node .gitnexus/run.cjs detect-changes --scope compare --base-ref "master" --repo .`.
- MUST warn on HIGH/CRITICAL `risk` pre-edit; never use `riskSharedAxes` to waive a HIGH/CRITICAL `risk` warning. Compare File/symbol: MCP File omits axes; Graph-RAG expands File.
- **MUST treat `risk: UNKNOWN` as unresolved, not as low.** An empty caller set is not evidence the symbol is unused — it can also mean the callers are not resolvable by the index (plain-object property access, dynamic dispatch, cross-language calls). `impact` pairs `UNKNOWN` with a `riskNote` saying so. Confirm with a text search before treating the symbol as safe to change or delete; do not proceed on the strength of a zero.
- **MUST use `query({search_query: "concept"})` for concepts/flows, `context({name: "symbolName"})` for a named symbol, or `impact` for blast radius, on read-only callers, dependencies, imports, or execution flow.** Graph first; text search only for empty/`UNKNOWN`/literals.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method before MCP/CLI impact analysis.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis, and never read `UNKNOWN` as an all-clear — it means the walk could not answer, which is the one verdict that requires confirming by other means.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit before MCP/CLI graph change analysis.

## Resources

| Resource | Use for |
| --- | --- |
| `gitnexus://repo/TCC/context` | Codebase overview, check index freshness |
| `gitnexus://repo/TCC/clusters` | All functional areas |
| `gitnexus://repo/TCC/processes` | All execution flows |
| `gitnexus://repo/TCC/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
| --- | --- |
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus-cli/SKILL.md` |
-->
