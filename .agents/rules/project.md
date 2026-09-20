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

- `docs/ARCHITECTURE.md` — arquitetura completa, os 12 requisitos
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
- `docs/AGENTIC_WORKFLOW.md` — divisão de trabalho entre Antigravity e
  Claude Code CLI, loop de trabalho e boas práticas de revisão.
- `CLAUDE.md` — o mesmo contexto, na versão consumida pelo Claude Code CLI.
- `.kiro/steering/project.md` — o mesmo contexto, na versão consumida pelo
  Kiro CLI (+ agentes customizados em `.kiro/agents/*.json`).

> O projeto é desenvolvido em três ferramentas (Antigravity, Claude Code CLI
> e Kiro CLI), muitas vezes em paralelo. Os três arquivos de regras são
> ponteiros equivalentes para `docs/`. Manter `docs/` sempre atualizado
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
