# Fluxo de Trabalho Agêntico: Antigravity + Claude Code CLI + Kiro CLI

Este projeto é desenvolvido combinando três ferramentas agênticas, muitas
vezes em paralelo (parte em uma, parte em outra):

- **Antigravity** (IDE): interface visual com **Editor View** (edição
  assistida, completions, comandos inline) e **Manager Surface** (orquestra e
  observa múltiplos agentes trabalhando de forma assíncrona, cada um gerando
  **Artifacts** — listas de tarefas, planos de implementação, screenshots e
  gravações de navegador — para revisão rápida sem precisar ler logs brutos).
  Suporta múltiplos modelos, incluindo Claude.
- **Claude Code CLI**: agente de terminal para sessões de codificação
  focadas, especialmente úteis para mudanças que exigem raciocínio
  arquitetural mais profundo ou trabalho fora da interface gráfica.
- **Kiro CLI**: agente de terminal com steering files e agentes customizados
  próprios. Também usado para sessões de codificação/revisão no terminal,
  com o mesmo contexto de projeto das outras duas ferramentas.

As três ferramentas devem enxergar o **mesmo contexto de projeto**. Isso é
garantido por três arquivos de regras que apontam para os mesmos documentos
em `docs/`:

| Ferramenta | Arquivo de regras | Onde aponta |
| --- | --- | --- |
| Claude Code CLI | `CLAUDE.md` (raiz do repo) | `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/CONVENTIONS.md`, etc. |
| Antigravity | `.agents/rules/project.md` | os mesmos documentos |
| Kiro CLI | `.kiro/steering/project.md` (+ agentes em `.kiro/agents/*.json`) | os mesmos documentos |

Os três arquivos de regras são **ponteiros equivalentes** para `docs/` — eles
resumem as regras de trabalho, mas a fonte de verdade é sempre `docs/`. Ao
portar um agente/skill de uma ferramenta para outra (ex.: `scope-guardian` e
`mvp-task` existem tanto em `.claude/agents/` quanto em `.kiro/agents/`),
mantenha o comportamento equivalente e aponte para os mesmos documentos.

**Regra de ouro:** ao mudar uma decisão de arquitetura ou escopo, edite os
documentos em `docs/` — nunca duplique a decisão apenas em um dos arquivos de
regras. Os arquivos de regras devem ficar curtos e estáveis; os documentos em
`docs/` concentram o conteúdo que muda.

## Sincronização: todos veem a mesma coisa

Como o trabalho é dividido entre três ferramentas (e entre sessões humanas e
agênticas), a consistência da documentação é o que mantém todos sincronizados.
Regras práticas:

1. **Conhecimento vive em `docs/`, não na memória de uma sessão.** Qualquer
   decisão, simplificação ou mudança de contrato que outra ferramenta precise
   conhecer tem de estar num `.md` de `docs/` — não basta ter sido dito no
   chat de uma das ferramentas.
2. **Atualize a documentação na mesma tarefa que muda o código** (regra 9 do
   `CLAUDE.md`): stack, estrutura de pastas, contrato de API, fluxos,
   playbooks e convenções de teste vão para o `.md` correspondente
   imediatamente. Documentação desatualizada é tratada como bug a corrigir
   antes de considerar a tarefa concluída.
3. **`docs/ROADMAP.md` é o estado compartilhado do progresso** — marque
   `- [x]` ao concluir para que a próxima sessão (em qualquer ferramenta)
   comece do ponto certo.
4. **Commite as mudanças de `docs/` junto com o código.** Uma ferramenta só
   "vê o que a outra fez" depois que o commit entra no repositório; evite
   deixar documentação atualizada apenas no working tree local.
5. **Ao começar uma sessão em qualquer ferramenta, releia `docs/` (via o
   arquivo de regras da ferramenta) antes de trabalhar** — nunca assuma que o
   contexto em memória de uma sessão anterior ainda vale.

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
- **Kiro CLI:** para sessões de terminal equivalentes às do Claude Code CLI,
  usando os agentes customizados de `.kiro/agents/` (`scope-guardian` para
  checar escopo, `mvp-task` para implementar um item do roadmap) e o steering
  de `.kiro/steering/project.md`, que carrega o contexto do projeto
  automaticamente.

Não há uma regra rígida — na dúvida, use a ferramenta com a qual for mais
fácil revisar o resultado antes de aceitar. O importante é que, seja qual for
a ferramenta, o contexto lido e a documentação atualizada sejam os mesmos.

## Loop de trabalho recomendado

1. Escolha o próximo item pendente (`- [ ]`) em `docs/ROADMAP.md`.
2. Implemente (Antigravity Editor View, Manager Surface, Claude Code CLI ou
   Kiro CLI).
3. Verifique o resultado:
   - No Antigravity, revise os **Artifacts** (plano, screenshots, gravações
     de navegador/terminal) em vez de aceitar às cegas.
   - Com o Claude Code CLI ou o Kiro CLI, revise o diff proposto e rode os
     testes relevantes (`pytest`) antes de aceitar.
   - Quando o agente roda na nuvem (sem GPU/Ollama/dados reais), a validação
     ponta a ponta é feita na máquina do desenvolvedor com `./testar.sh`,
     que roda o teste e dá push do relatório para o agente ler (ver
     `docs/TESTE_LOCAL.md`).
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
- Se um agente (em qualquer uma das três ferramentas) propuser implementar
  algo listado como "fora do MVP" em `CLAUDE.md`/`docs/ROADMAP.md`, rejeite e
  redirecione para o item correto do roadmap.
- Se uma tarefa exigir uma decisão de arquitetura não coberta em
  `docs/ARCHITECTURE.md`, peça ao agente para parar e registrar a decisão no
  documento antes de continuar — não deixe a decisão implícita apenas no
  código.

## Guardrails comuns às três ferramentas

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
