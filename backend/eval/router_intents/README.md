# Avaliação 1 — Acurácia do Roteador de Intenção (R3, Fase 1)

Ver `docs/EVALUATION.md` Seção 1 para o desenho completo desta avaliação.

- `dataset.json` — 40 mensagens rotuladas manualmente (10 por domínio,
  8 delas deliberadamente ambíguas), ancoradas nos dados reais do catálogo
  e do RAG já ingeridos no sistema.
- `run_eval.py` — roda o classificador real (`app.router.classifier.classify`)
  sobre o dataset para os três provedores (`heuristica`, `heuristica_llm`,
  `jev_openrouter`) e salva `results.json`.
- `results.json` — saída da última execução (2026-09-30, ambiente local
  completo no ar: Ollama com `gemma4:12b-it-q4_K_M`, OpenRouter real).

## Resultado (2026-09-30)

| Provider | Acurácia | Latência média | Erros |
| --- | --- | --- | --- |
| `heuristica` (palavra-chave pura) | 52,5% (21/40) | ~0,000s | 19 |
| `heuristica_llm` (heurística + fallback LLM local) | **95,0%** (38/40) | ~0,670s | 2 |
| `jev_openrouter` (decisão estruturada externa) | 92,5% (37/40) | ~0,302s | 3 |

Nenhum provedor degradou silenciosamente para outro (`provider_efetivo`
sempre igual ao provedor pedido) — comparação não contaminada.

**Principal padrão de erro (heurística pura):** 18 dos 19 erros foram
`fora_escopo`, não confusão entre domínios — a mensagem usava um sinônimo
fora da lista fixa de `_DOMAIN_KEYWORDS` (ex.: "manutenção"/"reclamar"/
"atraso" não estão na lista de Suporte/Atendimento; "compatível"/"desconto"
não estão na de Vendas). Isso confirma, com dados, a limitação já registrada
em `docs/ROADMAP.md` (Fase 1: "revisitar a resolução de ambiguidade entre
domínios no classificador") — este dataset é exatamente o que faltava para
decidir se vale a pena ampliar as listas de palavras-chave ou aceitar a
heurística pura só como atalho rápido (o sistema já usa `heuristica_llm`
por padrão em produção, `DEFAULT_INTENT_ROUTER_PROVIDER`).

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
