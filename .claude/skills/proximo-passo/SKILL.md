---
name: proximo-passo
description: Executa o loop de trabalho recomendado em docs/AGENTIC_WORKFLOW.md para este projeto de TCC — escolhe o próximo item pendente de docs/ROADMAP.md, valida escopo, implementa, testa e marca como concluído. Use quando o usuário disser "próximo passo", "próxima tarefa", "continua o roadmap" ou invocar /proximo-passo.
---

# Próximo passo do roadmap

Objetivo: avançar `docs/ROADMAP.md` um item de cada vez, seguindo o loop de
`docs/AGENTIC_WORKFLOW.md`, sem pular a validação de escopo nem os testes.

## Passo a passo

1. **Leia `docs/ROADMAP.md` por completo.** Encontre a primeira fase (na
   ordem em que aparecem no documento) que ainda tenha item `- [ ]` ou
   `- [~]` pendente. Dentro da fase, pegue o primeiro item pendente, respeitando
   dependências óbvias (ex.: não implementar Fase 2 antes de Fase 0/1 estarem
   ao menos parcialmente prontas, salvo indicação contrária do usuário).
2. **Mostre o item escolhido ao usuário** (texto da linha do roadmap + fase +
   requisito `Rn` associado) e confirme rapidamente antes de prosseguir, a
   menos que o usuário já tenha indicado explicitamente qual item quer.
3. **Valide o escopo** invocando o agente `scope-guardian` com a descrição do
   item. Só prossiga se o veredito for "DENTRO DO MVP" (ou a parte
   correspondente, se "PARCIALMENTE").
4. **Implemente** invocando o agente `mvp-task` com o item validado — passe a
   ele o texto exato do item do roadmap e o requisito `Rn` relacionado.
5. **Revise o resultado**: leia o diff/resumo do `mvp-task`, confira que os
   testes relevantes rodaram e passaram, e que `docs/ROADMAP.md` foi marcado
   (`- [x]`) para esse item.
6. **Proponha o commit** com a mensagem sugerida pelo `mvp-task`, no formato
   de `docs/CONVENTIONS.md`. Não faça `git commit` sem o usuário confirmar,
   a menos que ele já tenha autorizado commits automáticos nesta sessão.
7. **Pare aí** — não encadeie automaticamente para o próximo item do roadmap
   sem o usuário pedir novamente (`/proximo-passo` ou "próximo").

## Guardrails

- Nunca implemente um item listado em "Explicitamente fora do MVP" (final de
  `docs/ROADMAP.md`) mesmo que pareça relacionado ao item atual.
- Se o item pendente depender de infraestrutura que não existe neste
  ambiente (ex.: GPU real, credenciais reais de Google Calendar), diga isso
  claramente em vez de simular/mockar sem avisar, e sugira o próximo item que
  não dependa disso.
- Se `docs/ROADMAP.md` não tiver nenhum item pendente, informe que o roadmap
  está completo e pergunte se é hora de revisar `docs/ARCHITECTURE.md` contra
  o que foi implementado (Fase final — "Preparação da Entrega").
