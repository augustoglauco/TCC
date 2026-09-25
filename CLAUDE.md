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

| Documento | Quando consultar |
| --- | --- |
| `docs/ARCHITECTURE.md` | Antes de implementar qualquer requisito — arquitetura, os 12 requisitos funcionais, escopo do MVP x evolução futura, riscos conhecidos. |
| `docs/FRONTEND.md` | Antes de trabalhar no site/widget de chat — seções da interface, stack (Next.js), contrato de API com o backend. |
| `docs/ROADMAP.md` | Para saber a próxima tarefa a implementar e marcar o progresso. |
| `docs/CONVENTIONS.md` | Antes de escrever código — stack, estrutura de pastas, estilo, testes, git. |
| `docs/EVALUATION.md` | Ao implementar ou rodar a avaliação experimental (roteador, RAG, latência). |
| `docs/AGENTIC_WORKFLOW.md` | Para entender a divisão de trabalho entre Antigravity e Claude Code CLI. |
| `docs/TESTE_LOCAL.md` | Quando o código precisa ser validado na máquina do desenvolvedor (GPU/Ollama/dados reais) — roteiro `backend/scripts/teste_local.py` e formato do relatório devolvido ao agente. |

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

## Fora de escopo (não implementar sem pedido explícito)

- Integração com CRM.
- Fine-tuning de modelo, otimização de latência em produção.
- Exposição pública do MCP B2B a parceiros externos reais (autenticação por
  parceiro, OAuth, rate limiting, auditoria completa) — a versão do MVP é
  interna, sem autenticação por parceiro.
- Integração real com fila de atendimento humano e sistema de ticketing.
- Reagendamento/cancelamento de visita, checagem de disponibilidade em
  múltiplas agendas.

Motivo detalhado de cada exclusão: `docs/ARCHITECTURE.md`, seções "Escopo do
MVP e Evolução Futura" e "Riscos e Limitações".
