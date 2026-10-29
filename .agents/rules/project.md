# Regra de Workspace — Assistente Virtual Multimodal (TCC)

> Recomendação: ative esta regra como **Always On** nas configurações de
> regras do Antigravity, para que todo agente (Editor View ou Manager
> Surface) tenha este contexto sem precisar de `@mention` manual.

Este é um projeto de TCC: um assistente virtual multimodal (texto, imagem,
áudio) com um Roteador/Orquestrador baseado em LLM, RAG (texto e imagem) e
dois MCPs — um consumido (Google Calendar) e um provido pela empresa
(catálogo/estoque/preços + ferramentas B2B).

**Não duplique arquitetura ou escopo aqui.** Os documentos abaixo, na raiz
deste workspace, são a fonte de verdade — leia-os antes de propor ou
implementar qualquer mudança:

- `docs/ARCHITECTURE.md` — arquitetura completa, os 13 requisitos
  funcionais, escopo do MVP x evolução futura, riscos conhecidos.
- `docs/FRONTEND.md` — seções da interface (site + widget de chat), stack
  (Next.js) e contrato de API com o backend.
- `docs/ROADMAP.md` — próxima tarefa a implementar e progresso atual
  (checklist por fase).
- `docs/CONVENTIONS.md` — stack (Python/FastAPI + Next.js), estrutura de
  pastas (monorepo backend/frontend), estilo de código, convenções de teste
  e git.
- `docs/EVALUATION.md` — como implementar a avaliação experimental
  (acerto do roteador, qualidade do RAG, latência local x externo).
- `docs/AGENTIC_WORKFLOW.md` — divisão de trabalho entre Antigravity,
  Claude Code CLI, Kiro CLI e Amazon Q, loop de trabalho e boas práticas de revisão.
- `docs/TESTE_LOCAL.md`, `goup.md` (instalação e subida do ambiente) e
  `docs/Manuais/` (manuais de uso, implantação, integração B2B, prompts/LLM e
  ferramentas de desenvolvimento) — lista completa
  e regra de "não criar documentos paralelos" na tabela do `CLAUDE.md`.
- `CLAUDE.md` — o mesmo contexto, na versão consumida pelo Claude Code CLI.
- `.kiro/steering/project.md` — o mesmo contexto, na versão consumida pelo
  Kiro CLI (+ agentes customizados em `.kiro/agents/*.json`).
- `.amazonq/rules/project.md` — o mesmo contexto, na versão consumida pelo
  Amazon Q Developer CLI.

> O projeto é desenvolvido em quatro ferramentas (Antigravity, Claude Code
> CLI, Kiro CLI e Amazon Q), muitas vezes em paralelo. Os quatro arquivos de
> regras são ponteiros equivalentes para `docs/`. Manter `docs/` sempre atualizado
> (regra 7 abaixo) é o que garante que todas as ferramentas vejam a mesma
> coisa — ver `docs/AGENTIC_WORKFLOW.md`.

## Regras rápidas para qualquer agente neste workspace

1. Implemente apenas o que está descrito como MVP em `docs/ARCHITECTURE.md`
   e `docs/ROADMAP.md`. Itens em "Evolução futura" ou na lista "fora do MVP"
   não devem ser implementados sem decisão explícita do desenvolvedor.
2. Marque simplificações de escopo no código com `# MVP: <limitação>`.
3. Ao concluir uma tarefa, marque a caixa correspondente em
   `docs/ROADMAP.md` (`- [x]`).
4. Nunca gere ou insira credenciais/chaves de API reais — use variáveis de
   ambiente (`.env.example`).
5. Gere Artifacts (plano, screenshots, gravações) para qualquer tarefa
   executada no Manager Surface, para permitir revisão sem ler logs brutos.
6. Se uma tarefa exigir uma decisão de arquitetura não coberta nos
   documentos acima, pare e proponha a atualização de
   `docs/ARCHITECTURE.md` antes de prosseguir.
7. Documentação sempre reflete o estado atual: ao desenvolver, alterar ou
   evoluir algo que um `.md` acima descreve, atualize esse documento na
   mesma tarefa (não só o `ROADMAP.md` ou decisões novas de arquitetura —
   também `CONVENTIONS.md`, `FRONTEND.md`, `EVALUATION.md` quando o que
   mudou for stack, estrutura de pastas, contrato de API ou avaliação).
8. Antes de cada commit, siga o checklist de `docs/CONVENTIONS.md`
   ("Checklist antes de cada commit").
9. Para se orientar no código, use o **Repowise** — fonte única desde
   2026-10-17 (`get_answer`, `search_codebase`, `get_context`, `get_why`).
   O GitNexus foi desativado (a rever). O Graphify continua disponível como CLI
   (`graphify query`/`explain`/`path`) mas **não é obrigatório** e não
   precede mais o `grep`; depois de alterar código, o hook `post-commit`
   reconstrói `graphify-out/` sozinho (bit de execução restaurado em
   2026-10-17). O grafo orienta, não substitui a leitura do trecho que
   você vai editar. Motivo e evidência em `docs/CONVENTIONS.md`, "Ordem de
   uso das ferramentas de grafo de código".
10. **Escreva dentro dos limites de saúde do Repowise** (complexidade ciclomática ≤ 9 por função, ≤ ~50 linhas por função, `main`/handlers só orquestram) — números, origem e falsos positivos de "I/O in loop" em `docs/CONVENTIONS.md`, "Saúde de código — limites do Repowise ao escrever".
11. **Prompt/instrução de LLM alterado ou novo → revise `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md`** (regra 11 do `CLAUDE.md`): vale para qualquer texto enviado a um LLM.
