---
inclusion: always
---

# Regra de Workspace — Assistente Virtual Multimodal (TCC) — Kiro CLI

Este é o arquivo de regras do **Kiro CLI** para este projeto. Ele cumpre o
mesmo papel que `CLAUDE.md` (Claude Code CLI) e `.agents/rules/project.md`
(Antigravity): dar a todo agente o contexto do projeto **antes de iniciar
qualquer trabalho**. As três ferramentas apontam para os mesmos documentos
em `docs/` — a fonte de verdade única.

**Não duplique arquitetura ou escopo aqui.** Leia os documentos abaixo (na
raiz do workspace) antes de propor ou implementar qualquer mudança:

- `CLAUDE.md` — o "como trabalhar aqui" (regras 1–9). Leia por completo.
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

## Antes de iniciar qualquer trabalho

1. Leia `CLAUDE.md` por completo e o(s) documento(s) de `docs/` relevante(s)
   para a tarefa (ver tabela "Documentos de referência" em `CLAUDE.md`).
2. Confirme que a tarefa está descrita como **MVP** em
   `docs/ARCHITECTURE.md` §5 e/ou `docs/ROADMAP.md`. Em dúvida sobre escopo,
   use o agente `scope-guardian` antes de codificar.

## Regras rápidas (resumo — a versão completa está em `CLAUDE.md`)

1. **Escopo do MVP é lei.** Não implemente itens de "Evolução futura" ou da
   lista "fora do MVP" sem decisão explícita do desenvolvedor.
2. **Marque simplificações de MVP no código** com `# MVP: <limitação>`
   (`// MVP: ...` em TypeScript), referenciando `docs/ARCHITECTURE.md`.
3. **Diffs pequenos e rastreáveis**, focados em um item de `docs/ROADMAP.md`;
   referencie o requisito (ex.: `R4`, `R12`) e a fase.
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
   correspondente (`ARCHITECTURE.md`, `FRONTEND.md`, `CONVENTIONS.md`,
   `EVALUATION.md`) na mesma tarefa.

## Regra de ouro (comum às três ferramentas)

Ao mudar uma decisão de arquitetura ou escopo, edite os documentos em
`docs/` — nunca duplique a decisão apenas nos arquivos de regras
(`CLAUDE.md`, `.agents/rules/project.md`, este arquivo). Os arquivos de
regras ficam curtos e estáveis; `docs/` concentra o conteúdo que muda.
