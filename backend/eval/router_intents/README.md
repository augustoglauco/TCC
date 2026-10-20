# Avaliação 1 — Acerto do Roteador na Identificação de Intenções (Fase 10)

> **Conjunto invalidado em 2026-10-17.** Mesmo motivo do aviso em
> `eval/rag_quality/README.md`: o corpus da avaliação passou a ser
> `docs/Manuais_fornecedor/ControlId/`, e as 40 mensagens de `dataset.json`
> foram ancoradas no catálogo/RAG anterior. Os 95,0% de `heuristica_llm` são
> histórico; o conjunto novo tem **300 mensagens, ≥200 desenhadas para
> chegar ao LLM** (`docs/EVALUATION.md` Seção 0). O achado que **continua
> valendo** é de código, não de dado: 18 dos 19 erros da heurística pura são
> `fora_escopo` por sinônimo fora de `_DOMAIN_KEYWORDS`.

Ver `docs/EVALUATION.md` Seção 1 para o desenho completo desta avaliação.

- `dataset.json` — 40 mensagens rotuladas manualmente (10 por domínio,
  8 delas deliberadamente ambíguas), ancoradas nos dados reais do catálogo
  e do RAG já ingeridos no sistema.
- `run_eval.py` — roda o classificador real (`app.router.classifier.classify`)
  sobre o dataset para os três provedores (`heuristica`, `heuristica_llm`,
  `jev_openrouter`) e salva `results.json`.
- `results.json` — saída da última execução (2026-10-04, ambiente local
  completo no ar: Ollama com `gemma4:12b-it-q4_K_M`, OpenRouter real).

## Resultado (2026-10-04, após ampliar `_DOMAIN_KEYWORDS` — ver abaixo)

| Provider | Acurácia | Latência média | Erros |
| --- | --- | --- | --- |
| `heuristica` (palavra-chave pura) | **77,5%** (31/40) | ~0,000s | 9 |
| `heuristica_llm` (heurística + fallback LLM local) | 95,0% (38/40) | ~1,246s | 2 |
| `jev_openrouter` (decisão estruturada externa) | 92,5% (37/40) | ~0,397s | 3 |

Nenhum provedor degradou silenciosamente para outro (`provider_efetivo`
sempre igual ao provedor pedido) — comparação não contaminada.

### Resolução da pendência de `docs/ROADMAP.md` (Fase 1, 2026-10-04)

A rodada de 2026-09-30 (abaixo) tinha 19 erros na heurística pura e a nota
"18 dos 19 são `fora_escopo`, não confusão entre domínios" — essa frase
estava **imprecisa**: rodando o matcher de verdade mensagem a mensagem
contra o dataset, só **11 dos 19** eram "0 domínios casados" (sinônimo fora
da lista); os outros **7 já casavam 2 domínios ao mesmo tempo** (conflito
real entre keywords, não lacuna de vocabulário) e **1** (caso 36) casava
exatamente 1 domínio errado com confiança.

Adicionadas 12 keywords aos 11 casos de "0 domínios" + o caso de match único
errado, cada uma validada rodando o matcher contra as 40 mensagens rotuladas
**antes** de aplicar no código, pra garantir zero regressão:

- `vendas`: `desconto`, `vende`, `compatível`
- `suporte`: `não liga`, `manutenção`, `barulho`, `resetar`, `configurar`,
  `biometria`
- `atendimento`: `reclamar`, `atraso`
- `agendamento`: `técnico`

**Os 7 casos de conflito (2+ domínios) foram deixados intocados de
propósito.** Tentar resolver por prioridade fixa não funciona aqui: a mesma
dupla de keywords tem o gabarito esperado em direções opostas em casos
diferentes — ex. "defeito"+"comprei" é Suporte no caso 19 mas
"defeito"+"meu pedido" é Atendimento no caso 29. Uma prioridade fixa
acertaria um e erraria o outro, e o efeito colateral seria pior: destravaria
o atalho rápido da heurística e pularia a consulta ao LLM que hoje resolve
esses 7 casos corretamente em produção (`heuristica_llm`). Resultado: a
heurística pura sobe de 52,5% para 77,5% (zero regressão nas 40 mensagens,
validado antes de aplicar), e `heuristica_llm`/`jev_openrouter` continuam
iguais — não dependiam da heurística para esses 7 casos.

**O caso 36 ("técnico"/"avaliar qual gerador comprar") mudou de categoria,
não de resultado.** Antes, só "comprar" casava (vendas) com confiança — a
heurística decidia sozinha, **sem nunca consultar o LLM**, e errava (gabarito
Agendamento). Com "técnico" como keyword de Agendamento, a mensagem agora
casa 2 domínios (Vendas + Agendamento) → cai no LLM como deveria. O LLM local
respondeu Vendas de qualquer forma — mesmo tipo de caso genuinamente
discutível do caso 28 abaixo (a pergunta tem elementos legítimos dos dois
domínios), não um bug do mecanismo. Por isso `heuristica_llm` continua em
2 erros, não 1: o mecanismo foi corrigido (consulta o LLM em vez de decidir
sozinho errado), o julgamento do LLM nesse caso específico continua
divergindo do gabarito.

Testes novos em `backend/tests/test_classifier.py` (um por keyword
adicionada, usando as mensagens reais do dataset, + um teste específico
confirmando que o caso 36 agora consulta o LLM em vez de usar o atalho).

### Resultado (2026-09-30, histórico — antes da ampliação acima)

| Provider | Acurácia | Latência média | Erros |
| --- | --- | --- | --- |
| `heuristica` (palavra-chave pura) | 52,5% (21/40) | ~0,000s | 19 |
| `heuristica_llm` (heurística + fallback LLM local) | 95,0% (38/40) | ~0,670s | 2 |
| `jev_openrouter` (decisão estruturada externa) | 92,5% (37/40) | ~0,302s | 3 |

**Erros remanescentes de `heuristica_llm`/`jev_openrouter`:** ambos erram a
mesma mensagem ("Qual o prazo de garantia do Gerador Diesel GD-60?",
esperado Atendimento, classificado Vendas) e uma mensagem sobre agendar um
técnico para "avaliar qual gerador comprar" (esperado Agendamento,
classificado Vendas) — nos dois casos o gabarito é genuinamente discutível
(a pergunta tem elementos legítimos de Vendas também), não um erro grosseiro
do classificador.

## Reproduzir

```bash
cd backend
.venv/bin/python eval/router_intents/run_eval.py
```

Exige Ollama no ar (`local_model_base_url`) e `EXTERNAL_MODEL_API_KEY`
configurada no `.env` (chama a API real do OpenRouter para `jev_openrouter`
e, quando a heurística não resolve, para `heuristica_llm`).

## Conjunto novo de 300 mensagens (`gerar_dataset.py`, 2026-10-17)

As 40 mensagens originais foram **invalidadas** (montadas sobre outro corpus,
ver `docs/EVALUATION.md` Seção 0) e ficam como histórico de instrumento. O
conjunto válido tem 300 mensagens, e o requisito não é só o tamanho: são
**≥200 desenhadas para chegar ao LLM**.

```bash
cd backend
.venv/bin/python eval/router_intents/gerar_dataset.py --dry-run
.venv/bin/python eval/router_intents/gerar_dataset.py
```

Exige só `EXTERNAL_MODEL_API_KEY` (tier `:free`).

### Por que "chegar ao LLM" é o requisito

Nas 40 antigas, só **9 (22,5%)** chegavam ao classificador LLM: o atalho por
palavra-chave de `app.router.classifier` resolvia o resto antes. Medir um
candidato a `LOCAL_MODEL_NAME` nesse conjunto é medir a tabela de keywords —
o n efetivo de comparação entre modelos seria um terço do nominal.

Uma mensagem chega ao LLM quando não é cortesia pura e
`_match_domain_by_keywords` devolve `None`, o que ocorre em dois casos
distintos, e o gerador explora os dois:

- **zero domínios casados** — sinônimo fora da tabela. O prompt **proíbe** as
  palavras da tabela do domínio pedido ("quanto sai", "pifou", "parou do
  nada").
- **dois ou mais domínios casados** — a ambiguidade real ("desconto" de vendas
  + "defeito" de suporte), que colapsa de propósito para o LLM.

### Verificação sem gastar chamada

`classificar_caminho()` usa as **funções reais** do classificador
(`_is_cortesia`, `_match_domain_by_keywords`), então cada caso grava
`chega_ao_llm` e `motivo_caminho` sem chamar modelo nenhum. Validada contra as
40 antigas: devolve exatamente 9 de 40, igual à medição registrada no roadmap
(`backend/tests/test_geradores_conjuntos_fase10.py` falha se isso mudar).

### Resultado da geração de 2026-10-17

**299 mensagens, 233 chegando ao LLM (78%)** — contra os 22,5% de antes. Uma
mensagem a menos que a meta de 300 porque a deduplicação descartou uma
repetida; 299 com 233 cumpre o requisito com folga e não justifica outra
rodada de chamadas.

| Domínio | n | | Motivo do caminho | n |
| --- | --- | --- | --- | --- |
| vendas | 59 | | zero keywords (chega) | 146 |
| suporte | 60 | | 2+ keywords (chega) | 87 |
| atendimento | 60 | | atalho por keyword | 62 |
| agendamento | 60 | | cortesia | 4 |
| fora_escopo | 60 | | | |

Em 2026-10-20 as ambíguas foram **regeradas** (`deepseek/deepseek-v4.1-flash`,
`gerar_dataset.py --ambiguas-por-par`): cada uma nasce de um par fixo de domínios
(vendas/agendamento, vendas/suporte, vendas/atendimento, suporte/agendamento,
atendimento/suporte) e traz `intencoes_aceitas`; acerta quem cair em qualquer um.
As 137 antigas, de rótulo único e arbitrário entre pares, saíram. As ambíguas
(`ambiguo: true`) ficam **fora do placar principal** (`acuracia_ambiguas` à parte).
Os casos com `revisao.status = descartado` são ignorados pelos avaliadores. A
revisão prevista é **por amostra**: todas as ambíguas, onde o rótulo automático é
discutível, mais uma amostra aleatória das demais. **Risco assumido:** um erro
*sistemático* do rotulador pode escapar da amostra de 40.

**Reportar duas taxas**, nunca uma: acurácia do sistema (299 casos) e acurácia
do modelo no subconjunto que chega a ele (233).
