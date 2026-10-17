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
de qualquer commit. **O GitNexus foi removido do projeto** naquela data — MCP
e hooks — então aquelas instruções apontavam para uma ferramenta que já não
está no fluxo. O motivo e a evidência da remoção estão em
`docs/CONVENTIONS.md`, seção "Ordem de uso das ferramentas de grafo de
código".

A ferramenta de inteligência de código deste projeto é o **Repowise**
(`get_answer`, `search_codebase`, `get_context`, `get_why`). O **Graphify**
segue disponível como CLI opcional e não precede o `grep`.

**Nota sobre o Amazon Q:** ele **não** lê `AGENTS.md` nativamente — é um
feature request aberto (`aws/amazon-q-developer-cli#2712`). O arquivo que ele
lê é `.amazonq/rules/**/*.md`, incluído automaticamente pelo agente padrão.
Não mova as regras para cá esperando que ele as veja.

> `frontend/AGENTS.md` é outra coisa e não tem relação com este arquivo: é
> gerado e reescrito pelo `next dev` a cada subida do servidor de
> desenvolvimento. Não edite o bloco dele (ver `CLAUDE.md`).
