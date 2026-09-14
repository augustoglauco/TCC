# Fluxo de Trabalho Agêntico: Antigravity + Claude Code CLI

Este projeto é desenvolvido combinando duas ferramentas agênticas:

- **Antigravity** (IDE): interface visual com **Editor View** (edição
  assistida, completions, comandos inline) e **Manager Surface** (orquestra e
  observa múltiplos agentes trabalhando de forma assíncrona, cada um gerando
  **Artifacts** — listas de tarefas, planos de implementação, screenshots e
  gravações de navegador — para revisão rápida sem precisar ler logs brutos).
  Suporta múltiplos modelos, incluindo Claude.
- **Claude Code CLI**: agente de terminal para sessões de codificação
  focadas, especialmente úteis para mudanças que exigem raciocínio
  arquitetural mais profundo ou trabalho fora da interface gráfica.

Ambas as ferramentas devem enxergar o **mesmo contexto de projeto**. Isso é
garantido por dois arquivos de regras que apontam para os mesmos documentos
em `docs/`:

| Ferramenta | Arquivo de regras | Onde aponta |
| --- | --- | --- |
| Claude Code CLI | `CLAUDE.md` (raiz do repo) | `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/CONVENTIONS.md` |
| Antigravity | `.agents/rules/project.md` | os mesmos documentos |

**Regra de ouro:** ao mudar uma decisão de arquitetura ou escopo, edite os
documentos em `docs/` — nunca duplique a decisão apenas em um dos dois
arquivos de regras. Os arquivos de regras devem ficar curtos e estáveis;
os documentos em `docs/` concentram o conteúdo que muda.

## Quando usar cada ferramenta

- **Antigravity — Editor View:** para trabalho interativo, um arquivo/tarefa
  por vez, com o desenvolvedor acompanhando de perto (ex.: implementar um
  handler de ferramenta do MCP B2B enquanto revisa cada trecho gerado).
- **Antigravity — Manager Surface:** para tarefas mais longas e paralelizáveis
  do `docs/ROADMAP.md` que podem rodar em segundo plano (ex.: um agente
  implementando a Fase 3 enquanto você revisa a Fase 2 no Editor View).
  Revise o resultado pelos **Artifacts** gerados (plano, screenshots,
  gravações) antes de aceitar.
- **Claude Code CLI:** para sessões de terminal, mudanças que cruzam vários
  módulos, refatorações maiores, ou quando não há necessidade da interface
  gráfica (ex.: rodar testes, revisar uma fase inteira do roadmap, escrever
  os scripts de `eval/`).

Não há uma regra rígida — na dúvida, use a ferramenta com a qual for mais
fácil revisar o resultado antes de aceitar.

## Loop de trabalho recomendado

1. Escolha o próximo item pendente (`- [ ]`) em `docs/ROADMAP.md`.
2. Implemente (Antigravity Editor View, Manager Surface ou Claude Code CLI).
3. Verifique o resultado:
   - No Antigravity, revise os **Artifacts** (plano, screenshots, gravações
     de navegador/terminal) em vez de aceitar às cegas.
   - Com o Claude Code CLI, revise o diff proposto e rode os testes
     relevantes (`pytest`) antes de aceitar.
4. Rode a skill/comando `code-review` sobre o diff do item (e também
   `security-review` quando o item tocar algo sensível — MCPs, autenticação,
   segredos/`.env`, endpoints expostos). Achados `high`/`critical` bloqueiam
   o commit; achados de estilo/baixo risco só ficam registrados. O
   `/proximo-passo` já automatiza esse passo.
5. Marque o item como concluído (`- [x]`) em `docs/ROADMAP.md`.
6. Faça commit seguindo a convenção de `docs/CONVENTIONS.md` (mensagem
   referenciando requisito + fase).

## Boas práticas de revisão de agentes

- Trate os **Artifacts** do Antigravity como a interface principal de
  revisão — eles existem justamente para não depender de ler logs brutos.
- Peça explicitamente que o agente rode os testes automatizados antes de
  considerar uma tarefa concluída, especialmente para roteador, RAG e
  handlers do MCP B2B (ver `docs/CONVENTIONS.md`).
- Se um agente (em qualquer uma das duas ferramentas) propuser implementar
  algo listado como "fora do MVP" em `CLAUDE.md`/`docs/ROADMAP.md`, rejeite e
  redirecione para o item correto do roadmap.
- Se uma tarefa exigir uma decisão de arquitetura não coberta em
  `docs/ARCHITECTURE.md`, peça ao agente para parar e registrar a decisão no
  documento antes de continuar — não deixe a decisão implícita apenas no
  código.

## Guardrails comuns às duas ferramentas

- Nunca aceitar credenciais, chaves de API ou tokens reais gerados/inseridos
  por um agente — sempre via variável de ambiente (`.env.example`).
- Simplificações de MVP devem ficar marcadas no código (`# MVP: ...`, ver
  `docs/CONVENTIONS.md`) para que um agente futuro não tente "completá-las"
  por conta própria.
- Mudanças em `docs/ARCHITECTURE.md` ou `docs/ROADMAP.md` feitas por um
  agente devem ser revisadas por você antes do commit — esses documentos são
  a fonte de verdade para todas as sessões futuras, humanas ou agênticas.

## Referências

- Antigravity — visão geral do produto e Artifacts:
  https://developers.googleblog.com/build-with-google-antigravity-our-new-agentic-development-platform/
- Antigravity — regras de workspace (`.agents/rules`):
  https://antigravity.google/docs/rules-workflows/
