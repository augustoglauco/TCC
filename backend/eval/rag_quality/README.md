# Avaliação 2 — Qualidade das Respostas do RAG (R4, Fase 10)

Ver `docs/EVALUATION.md` Seção 2 para o desenho completo desta avaliação.

- `bateria_perguntas_rag.md` — fonte narrativa original das 20 perguntas
  (com o "porquê" de cada uma), construída a partir dos manuais/datasheets
  reais já enviados por upload no RAG (domínio Suporte).
- `dataset.json` — as mesmas 20 perguntas + gabarito, extraídas para
  consumo pelo script de avaliação.
- `run_eval.py` — reproduz o caminho real de produção para o domínio
  "suporte" (busca RAG + prompt + geração pelo modelo local), sem passar
  pelo classificador de intenção (avaliado separadamente em
  `eval/router_intents/`), e usa um LLM-as-judge (modelo externo, diferente
  do gerador) para notar cada resposta — prompt documentado em
  `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md`.
- `results.json` — saída da última execução (2026-09-30, ambiente local
  completo no ar: Ollama com `gemma4:12b-it-q4_K_M` gerando, OpenRouter real
  julgando).

## Resultado (2026-09-30)

| Métrica | Valor |
| --- | --- |
| Nota média geral (LLM-as-judge, 1–5) | **2,5** |
| Taxa de recuperação da fonte correta | **70%** (14/20) |
| Nota média quando a fonte correta foi recuperada | **3,0** (n=14) |
| Nota média quando a fonte correta NÃO foi recuperada | **1,3** (n=6) |

| Dificuldade | n | Nota média | Fonte correta |
| --- | --- | --- | --- |
| Fácil | 7 | 2,43 | 86% |
| Média | 7 | 3,14 | 71% |
| Difícil | 6 | 1,83 | 50% |

**Nota manual (1–5):** coluna `nota_manual` em `results.json` fica `null` de
propósito — pendente de preenchimento humano (ver decisão abaixo).

## Achados

1. **A qualidade da resposta está fortemente ligada a recuperar a fonte
   certa** — não é só a geração que falha: nota média cai de 3,0 para 1,3
   quando o documento certo não está entre os `top_k=3` chunks recuperados.
   Isso separa, como o `docs/EVALUATION.md` pede, erro de recuperação de
   erro de geração — aqui os dois pesam, mas a recuperação pesa mais.
2. **Perguntas difíceis (raciocínio, RAG negativo) recuperam pior** (50% x
   71-86% das fáceis/médias) — plausível: perguntas como "isso é
   verdade?" (checagem de alucinação) ou comparativos entre duas versões de
   produto casam pior por similaridade de embedding do que uma pergunta
   direta sobre uma especificação.
3. **Mesmo com a fonte certa recuperada, o modelo local
   (`gemma4:12b-it-q4_K_M`, quantizado) erra números específicos com
   frequência** — ex.: pergunta 6 (resolução máxima do iNVU 9164, gabarito
   32 MP) recebeu a fonte certa mas respondeu "6 MP/1080p"; pergunta 12
   (tipos de DTMF do V3001) recebeu a fonte certa mas inventou um quarto
   tipo ("AUTO") além dos 3 do gabarito. Ainda assim, quando a fonte é
   recuperada, a nota média (3,0) é bem melhor que quando não é (1,3) — o
   modelo às vezes também responde "não encontrei" mesmo com a informação
   certa na base recuperada (subutilização da fonte, não alucinação).
4. **Achado sobre a ferramenta de medição, não sobre o sistema:** o nome
   real de um dos PDFs enviados por upload tem espaço duplo
   ("...IA  FT..."), diferente do nome usado no gabarito — a checagem
   ingênua de `fonte_correta` (substring) marcava falso negativo em 2 das
   20 perguntas mesmo com o documento certo recuperado. Corrigido
   normalizando espaços antes de comparar (`_normalizar_nome_arquivo` em
   `run_eval.py`) — números acima já refletem a correção.

## Decisão registrada: por que a nota manual fica em branco

`docs/EVALUATION.md` pede duas notas independentes por pergunta — manual
(1–5) e LLM-as-judge — precisamente para ter duas fontes de sinal
distintas. Preencher a nota manual com outra chamada de LLM (mesmo que um
terceiro modelo) não cumpriria esse propósito: seria um segundo
LLM-as-judge disfarçado, não o julgamento humano que a avaliação pede. A
pontuação automatizada (LLM-as-judge, retrieval, geração) está completa;
falta só o desenvolvedor/orientador preencher `nota_manual` em
`results.json` olhando as 20 respostas geradas — o comparativo entre as
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
