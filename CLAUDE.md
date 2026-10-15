# CLAUDE.md — Guia do Projeto para Desenvolvimento Agêntico

Este arquivo é o ponto de entrada para o Claude Code (CLI) ao trabalhar neste
repositório. Ele é lido automaticamente no início de cada sessão. Leia-o por
completo antes de propor ou implementar qualquer mudança.

O projeto também é desenvolvido na IDE **Antigravity**, que lê suas próprias
regras de workspace em `.agents/rules/project.md`, e no **Kiro CLI**, que lê
`.kiro/steering/project.md` (+ agentes em `.kiro/agents/*.json`). Esses três
arquivos de regras **apontam para os mesmos documentos em `docs/`** — evite
duplicar decisões de arquitetura ou escopo diretamente nos arquivos de regras;
atualize sempre os documentos em `docs/` e deixe os três arquivos de regras
como resumos/ponteiros. O trabalho é dividido entre as três ferramentas, então
manter `docs/` sempre atualizado (regra 9) é o que garante que todas vejam a
mesma coisa — ver `docs/AGENTIC_WORKFLOW.md`.

Há ainda um quarto arquivo de escopo restrito: `frontend/CLAUDE.md`, que só
inclui `frontend/AGENTS.md` com avisos da versão do Next.js em uso. Esse
`AGENTS.md` é **gerado e reescrito pelo `next dev`** (ver
`frontend/node_modules/next/dist/server/lib/generate-agent-files.js`), então
não edite nem apague o bloco dele: a alteração reaparece como diff sujo na
próxima subida do servidor de desenvolvimento. Regras do projeto para o
frontend vão em `docs/FRONTEND.md`, não ali.

## O que é este projeto

Assistente virtual multimodal (texto, imagem e áudio) para uma empresa
fictícia/real, cobrindo quatro domínios de atendimento — Vendas, Suporte
Técnico, Atendimento ao Usuário e Agendamento de Visita — orquestrados por um
Roteador/Orquestrador baseado em LLM. O roteador decide entre modelo local
(GPU 16GB) e modelo externo, aciona RAG (texto e imagem) e integra dois MCPs
(Model Context Protocol): um consumido (Google Calendar, para agendamento) e
um provido pela própria empresa (catálogo/estoque/preços/manuais + ferramentas
transacionais para IAs de parceiros B2B).

Este é um projeto de TCC (curso de especialização em IA generativa) cujo
objetivo central é a construção do chat/roteador — o site (apresentação da
empresa, produtos, pedidos) é o contexto ao redor dele, não o foco de esforço.

Documentação completa da proposta (o "porquê" de cada decisão): veja
`docs/ARCHITECTURE.md`. Este `CLAUDE.md` cobre apenas o "como trabalhar aqui".

## Documentos de referência

| Documento                                    | Quando consultar                                                                                                                                                                                                                                                                                            |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/ARCHITECTURE.md`                     | Antes de implementar qualquer requisito — arquitetura, os 12 requisitos funcionais, escopo do MVP x evolução futura, riscos conhecidos.                                                                                                                                                                  |
| `docs/FRONTEND.md`                         | Antes de trabalhar no site/widget de chat — seções da interface, stack (Next.js), contrato de API com o backend.                                                                                                                                                                                         |
| `docs/ROADMAP.md`                          | Para saber a próxima tarefa a implementar e marcar o progresso.                                                                                                                                                                                                                                            |
| `docs/CONVENTIONS.md`                      | Antes de escrever código — stack (versões e bibliotecas), estrutura de pastas, estilo, testes, git e rollback do Python 3.14.                                                                                                                                                                            |
| `docs/EVALUATION.md`                       | Ao implementar ou rodar a avaliação experimental (roteador, RAG, latência).                                                                                                                                                                                                                              |
| `docs/AGENTIC_WORKFLOW.md`                 | Para entender a divisão de trabalho entre Antigravity, Claude Code CLI e Kiro CLI.                                                                                                                                                                                                                                   |
| `docs/TESTE_LOCAL.md`                      | Quando o código precisa ser validado na máquina do desenvolvedor (GPU/Ollama/dados reais) — `./testar.sh` roda o teste (`backend/scripts/teste_local.py`, suíte `SUITE_ATUAL`) e dá push do relatório em `testes_locais/`.                                                                    |
| `goup.md` (raiz)                           | Para instalar numa máquina nova (passo 0) ou subir o ambiente à mão; acesso externo, MCP B2B público com o manual do parceiro, solução de problemas. `./g.sh` sobe tudo de uma vez.                                                                                                                 |
| `docs/Manuais/`                            | Manuais de uso do sistema (`HOWTO_USUARIO.md`, `HOWTO_ADMINISTRADOR.md`) e guias de ferramentas locais de desenvolvimento (`strata-manual.md`, `headroom-manual.md`, `repowise-manual.md`, `gitnexus-manual.md`, `graphify-manual.md`).                                                                               |
| `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md` | Mapeamento de todos os prompts/instruções de sistema/playbooks/extratores estruturados enviados a um LLM no código. Consulte antes de alterar qualquer prompt existente (para achar todos os pontos relacionados) e atualize sempre que um prompt for alterado ou um novo for criado — ver regra 11.    |
| `graphify-out/` (Knowledge Graph)          | **Primeira consulta** ao receber perguntas sobre código ou pedidos de alteração — comandos na seção "Graphify" deste arquivo. |
| `README.md` e `README_TCC.md`            | Apresentação do projeto; o `README_TCC.md` é a entrega acadêmica no formato do curso.                                                                                                                                                                                                                 |

Não crie documentos novos fora desta lista (resumos, cópias de spec, guias
paralelos): o conteúdo vai para o documento acima que já cobre o assunto.
Consolidação de 2026-09-28: `resumo.md`, `docs/TECHNOLOGY_STACK.md` e cinco
manuais foram incorporados aos documentos acima e apagados.

## Stack técnica

- **Modelo local:** servido via Ollama ou vLLM, modelo quantizado 7B–8B
  (ex.: Llama 3.1 8B, Qwen2.5 7B) — hardware-alvo: GPU única de 16GB de VRAM.
- Detalhes de estrutura de pastas e ferramentas (lint, testes, etc.) estão em
  `docs/CONVENTIONS.md`.

## Regras de como trabalhar neste repositório

1. **Escopo do MVP é lei.** Antes de "melhorar" algo além do que está descrito
   como MVP em `docs/ARCHITECTURE.md`, pare e pergunte. Itens listados como
   "Evolução futura" não devem ser implementados por iniciativa própria — eles
   estão fora do MVP por decisão consciente, não por esquecimento.
2. **Simplificações do MVP ficam explícitas no código.** Sempre que
   implementar uma versão simplificada de algo (ex.: crawler restrito a
   páginas fixas, conector de BD somente leitura, MCP B2B sem autenticação por
   parceiro), adicione um comentário curto `# MVP: <limitação>` e, se for algo
   novo, garanta que também conste em `docs/ARCHITECTURE.md`.
3. **Mudanças pequenas e rastreáveis.** Prefira diffs pequenos e focados em um
   único item do `docs/ROADMAP.md`. Referencie o requisito (ex.: `R4`, `R12`)
   e o item do roadmap na mensagem de commit.
4. **Nunca invente credenciais ou chaves de API.** Para MCPs e serviços
   externos (Google Calendar, modelo externo via API, etc.), use variáveis de
   ambiente com valores de exemplo em `.env.example` — nunca valores reais no
   código ou em commits.
5. **Toda tarefa nova ou concluída atualiza `docs/ROADMAP.md`.** Marque a
   caixa (`- [x]`) do item correspondente ao terminar; se a tarefa não existir
   no roadmap, adicione-a antes de implementar.
6. **Decisão de arquitetura nova → atualize `docs/ARCHITECTURE.md` primeiro.**
   Se uma tarefa exige uma decisão que não está coberta na Seção de riscos ou
   nas tabelas de escopo, registre a decisão no documento antes (ou junto) da
   implementação, não só no commit.
7. **Teste o que for testável antes de marcar como concluído** — especialmente
   classificação de intenção do roteador, recuperação do RAG e handlers das
   ferramentas do MCP B2B. Ver `docs/CONVENTIONS.md` para convenções de teste.
8. **Ao ficar em dúvida entre duas abordagens de implementação**, prefira a
   mais simples que atenda ao MVP descrito — não a mais "completa" ou
   "genérica". Este é um protótipo de TCC, não um produto de produção.
9. **Documentação sempre reflete o estado atual.** Sempre que desenvolver,
   alterar ou evoluir algo que um documento de `docs/` descreve (stack,
   estrutura de pastas, contrato de API, fluxos, playbooks, convenções de
   teste, etc.), atualize o `.md` correspondente (`ARCHITECTURE.md`,
   `FRONTEND.md`, `CONVENTIONS.md`, `EVALUATION.md`) na mesma tarefa, não
   depois — isso vale além do `ROADMAP.md` (regra 5) e de decisões de
   arquitetura novas (regra 6). Documentação desatualizada é tratada como um
   bug a corrigir antes de considerar a tarefa concluída.
10. **Antes de cada commit, siga o checklist** de `docs/CONVENTIONS.md`
    ("Checklist antes de cada commit").
11. **Prompt/instrução de LLM alterado ou novo → revise
    `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md`.** Vale para qualquer texto
    enviado a um LLM (local ou externo): prompts de sistema, playbooks por
    domínio, templates de extração estruturada (JSON), prompts de visão
    computacional, critérios de classificação, etc. Ao alterar um prompt já
    mapeado, atualize a entrada correspondente; ao criar um prompt novo,
    adicione uma entrada nova. Trate esse documento como desatualizado (bug a
    corrigir) se um prompt existir no código e não constar nele.

## Fora de escopo (não implementar sem pedido explícito)

- Integração com CRM.
- Fine-tuning de modelo, otimização de latência em produção.
- Autorização de produção do MCP B2B (OAuth, permissões por ferramenta,
  rate limiting, auditoria completa, expiração/rotação de chaves). O MVP
  expõe o MCP B2B publicamente só com uma chave estática por parceiro, via
  HTTPS (decisão de 2026-09-25, `docs/ARCHITECTURE.md` §6).
- Integração real com fila de atendimento humano e sistema de ticketing.
- Reagendamento/cancelamento de visita, checagem de disponibilidade em
  múltiplas agendas.

Motivo detalhado de cada exclusão: `docs/ARCHITECTURE.md`, seções "Escopo do
MVP e Evolução Futura" e "Riscos e Limitações".

<!-- graphify:start -->

## Graphify — Knowledge Graph (`graphify-out/`)

Grafo do código (comunidades, nós centrais e relações entre arquivos) gerado
via AST — rápido e sem custo de API.

- **Consulte o grafo antes de abrir arquivo bruto**, ao responder sobre
  código ou ao receber um pedido de alteração: `graphify query "<pergunta>"`
  (subgrafo enxuto), `graphify explain "<símbolo/conceito>"` (nó focalizado),
  `graphify path "<A>" "<B>"` (dependência entre dois pontos).
- `graphify-out/GRAPH_REPORT.md` só para visão macro da arquitetura, ou
  quando `query`/`explain`/`path` não derem contexto suficiente. (Não procure
  um `graphify-out/wiki/`: esta CLI não tem comando que o gere — a menção a
  `wiki/index.md` saiu daqui e do `AGENTIC_WORKFLOW.md` em 2026-10-15.)
- **Depois de qualquer alteração em código**, sem esperar pedido:
  `graphify update .`. É o item 9 do checklist de `docs/CONVENTIONS.md`,
  cobrado pela regra 10.
- O grafo orienta, não substitui: ler o arquivo bruto continua obrigatório
  antes de editá-lo.

A ordem de uso em relação ao outro grafo do repositório está em
`docs/CONVENTIONS.md`, "Ordem de uso dos dois grafos de código" — fonte única
para as três ferramentas.

<!-- graphify:end -->
