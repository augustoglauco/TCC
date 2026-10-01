# Avaliação 2 — Qualidade das Respostas do RAG (R4, Fase 10)

Ver `docs/EVALUATION.md` Seção 2 para o desenho completo desta avaliação.

- `bateria_perguntas_rag.md` — fonte narrativa original das 20 perguntas
  (com o "porquê" de cada uma), construída a partir dos manuais/datasheets
  reais já enviados por upload no RAG (domínio Suporte). **20 perguntas
  originais**, 2 marcadas como excluídas (ver abaixo).
- `dataset.json` — **18 perguntas avaliadas de fato** (Q8 e Q19 removidas) +
  gabarito, extraídas para consumo pelo script de avaliação.
- `run_eval.py` — reproduz o caminho real de produção para o domínio
  "suporte" (busca RAG + prompt + geração pelo modelo local), sem passar
  pelo classificador de intenção (avaliado separadamente em
  `eval/router_intents/`), e usa um LLM-as-judge (modelo externo, diferente
  do gerador) para notar cada resposta — prompt documentado em
  `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md`.
- `results.json` — saída da última execução (2026-10-01, ambiente local
  completo no ar: Ollama com `gemma4:12b-it-q4_K_M` gerando, OpenRouter real
  julgando).

## Por que só 18 perguntas (não 20)

Q8 e Q19 citam `Comparativo de funções - Intelbras Defense IA & Lite -
V1.pdf` como fonte — um PDF que existe em `docs/Manuais_fornecedor/` mas
**nunca foi ingerido no RAG**. Sem o documento no corpus, nenhuma
configuração de chunking/retrieval algum dia acertaria essas duas; mantê-las
contaminava qualquer avaliação com um problema que não é de chunking nem de
geração, é de ingestão ausente. Removidas de `dataset.json` em 2026-10-01
(continuam documentadas, marcadas, em `bateria_perguntas_rag.md`, por
completude histórica). Se o PDF for ingerido futuramente, reintroduzir as
duas no conjunto avaliado.

## Resultado (2026-10-01, 18 perguntas)

| Métrica | Valor |
| --- | --- |
| Nota média geral (LLM-as-judge, 1–5) | **2,78** |
| Taxa de recuperação da fonte correta | **78%** (14/18) |
| Nota média quando a fonte correta foi recuperada | **3,0** (n=14) |
| Nota média quando a fonte correta NÃO foi recuperada | **2,0** (n=4) |

| Dificuldade | n | Nota média | Fonte correta |
| --- | --- | --- | --- |
| Fácil | 7 | 2,71 | 86% |
| Média | 6 | 2,67 | 83% |
| Difícil | 5 | 3,00 | 60% |

**Nota manual (1–5):** coluna `nota_manual` em `results.json` fica `null` de
propósito — pendente de preenchimento humano (ver decisão abaixo).

## Achados

1. **A correlação entre fonte certa e nota caiu bastante** depois de
   remover Q8/Q19 (3,0 x 2,0, antes 3,0 x 1,3) — a amostra de "fonte
   errada" ficou pequena (n=4), então essa diferença é menos conclusiva
   agora; ainda assim a direção se mantém (fonte certa → nota melhor).
2. **Um caso notável de resposta certa com fonte errada** (Q16, nota 5): o
   RAG recuperou os manuais errados, mas o modelo respondeu corretamente
   sobre o papel do software IP Utility mesmo assim — conhecimento
   paramétrico do modelo, não grounding pelo RAG. Vale como lembrete de que
   `fonte_correta` mede recuperação, não garante (nem é garantido por) a
   qualidade da resposta.
3. **Difícil já não é a categoria pior** (3,00, a melhor das três) — o
   resultado anterior (1,83) vinha majoritariamente de Q19, que era
   impossível de acertar. Com só 5 perguntas difíceis restantes, a amostra
   é pequena demais para tirar conclusão forte sobre dificuldade x nota.
4. **Achado sobre a ferramenta de medição, não sobre o sistema:** o nome
   real de um dos PDFs enviados por upload tem espaço duplo
   ("...IA  FT..."), diferente do nome usado no gabarito — corrigido
   normalizando espaços antes de comparar (`_normalizar_nome_arquivo` em
   `run_eval.py`).
5. **Achado operacional:** 18 chamadas sequenciais ao LLM-as-judge (OpenRouter)
   esbarram em rate limit (429) ocasionalmente — `run_eval.py` agora tenta
   de novo com backoff exponencial (até 4 tentativas) em vez de derrubar a
   rodada inteira.

## Decisão registrada: por que a nota manual fica em branco

`docs/EVALUATION.md` pede duas notas independentes por pergunta — manual
(1–5) e LLM-as-judge — precisamente para ter duas fontes de sinal
distintas. Preencher a nota manual com outra chamada de LLM (mesmo que um
terceiro modelo) não cumpriria esse propósito: seria um segundo
LLM-as-judge disfarçado, não o julgamento humano que a avaliação pede. A
pontuação automatizada (LLM-as-judge, retrieval, geração) está completa;
falta só o desenvolvedor/orientador preencher `nota_manual` em
`results.json` olhando as 18 respostas geradas — o comparativo entre as
duas notas (concordância/divergência) é, em si, um dado interessante para o
relatório final.

## Reproduzir

```bash
cd backend
.venv/bin/python eval/rag_quality/run_eval.py
```

Exige Ollama, Qdrant e Postgres reais no ar (a collection `docs_texto`
ativa, populada com os manuais) e `EXTERNAL_MODEL_API_KEY` configurada no
`.env` (LLM-as-judge via OpenRouter).
