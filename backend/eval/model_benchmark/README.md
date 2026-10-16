# Benchmark comparativo dos modelos locais candidatos

Fase 10, item 1 do `docs/ROADMAP.md`. Escolhe o `LOCAL_MODEL_NAME` final
medindo cada candidato **contra o sistema completo** — RAG real, playbooks
de domínio, prompts de produção —, não em testes sintéticos isolados. Essa
ordem foi decidida de propósito: medir na Fase 1, sem RAG nem playbooks,
descartaria ou escolheria um modelo com sinal incompleto.

## O que roda

O orquestrador (`run_benchmark.py`) não inventa avaliação nova: reexecuta as
três que já existem em `eval/`, trocando só o modelo local e reaproveitando
os datasets, os prompts de juiz e o caminho real de produção.

| Etapa | Dataset | O que entra em `metricas` |
| --- | --- | --- |
| `roteador` | `eval/router_intents/dataset.json` | `roteador_acuracia`, `json_invalido_taxa` |
| `rag` | `eval/rag_quality/dataset.json` | `rag_nota_media`, `rag_fonte_correta_taxa` |
| `injecao` | `eval/prompt_injection/dataset.json` | `injecao_resistencia` |

Em todas: `latencia_media_s`, `latencia_p95_s`, `chamadas_medidas`, mais
`carga_s` e `vram_bytes` em `config`.

## Uso

A partir de `backend/`, com o Ollama no ar:

```bash
.venv/bin/python eval/model_benchmark/run_benchmark.py --listar
.venv/bin/python eval/model_benchmark/run_benchmark.py --etapas roteador
.venv/bin/python eval/model_benchmark/run_benchmark.py --modelos gemma4-12b-q4,phi4-mini
.venv/bin/python eval/model_benchmark/run_benchmark.py --forcar
```

- `--listar` mostra, por candidato, se o modelo está baixado e quais etapas
  já foram medidas. Não chama modelo nenhum.
- `--etapas` aceita `roteador`, `rag`, `injecao` (padrão: as três).
- `--timeout-s` tem padrão de 180s, bem acima do `LOCAL_LLM_TIMEOUT_S` (30s)
  de produção: candidatos de 14B em Q5/Q8 numa GPU de 16GB levam muito mais
  tempo para carregar, e um timeout curto reprovaria o modelo por tempo de
  carga, não por qualidade.

**Dependências por etapa:** `roteador` só precisa do Ollama. `rag` e
`injecao` também precisam de `EXTERNAL_MODEL_API_KEY` no `.env` (o
LLM-as-judge é externo de propósito, para o modelo avaliado não se
autoavaliar). `rag` ainda precisa de Qdrant e Postgres no ar, com a
collection ativa populada.

## Retomada

Uma rodada completa leva horas e cai por motivos banais: OOM de VRAM num
candidato grande, Ollama reiniciado, rate limit (429) do juiz externo.
Cada etapa é gravada assim que termina, e rodar de novo pula o que já está
no arquivo do modelo — `--forcar` refaz. Um candidato que falha não derruba
os seguintes: o erro é impresso, a VRAM é liberada e a rodada continua.

A latência é sempre recalculada sobre **todas** as etapas presentes no
arquivo, então uma rodada retomada produz o mesmo número que uma rodada
única com as mesmas etapas.

## Saída

Um arquivo por modelo em `results/<id>.json`, no envelope que
`GET /api/avaliacao/resultados` já lê (`app.api.avaliacao._modelos`):

```json
{
  "versao": 1,
  "avaliacao": "model_benchmark",
  "modelo": "Gemma-4-12B 4-bit",
  "gerado_em": "2026-10-16T21:55:37+00:00",
  "config": { "ollama": "...", "quantizacao": "Q4_K_M", "vram_bytes": 8064094698 },
  "metricas": { "roteador_acuracia": 0.95, "latencia_p95_s": 1.032 },
  "itens": { "roteador": { "...": "respostas e matriz de confusão" } }
}
```

`itens` guarda as respostas geradas e **não sai pela API pública** — a rota
`/avaliacao` é sem login e só expõe `modelo`, `gerado_em`, `config` e
`metricas`.

## Decisões de medição

**Aquecimento descartado.** A primeira chamada depois de trocar de modelo
paga a carga na VRAM. O orquestrador faz `preload()` (cronometrado à parte
em `config.carga_s`), descarta uma geração de aquecimento e só então começa
a medir. Sem isso o cold start contaminaria a comparação entre candidatos.

**VRAM descarregada entre candidatos.** Em 16GB, dois modelos de 12–14B
residentes ao mesmo tempo derrubam o segundo por falta de memória; o
orquestrador chama `unload()` ao terminar cada um.

**`json_invalido_taxa` é medida à parte da acurácia.** Quando o modelo
devolve um JSON de classificação quebrado, `_classify_with_llm` cai para a
heurística **mantendo** `provider_efetivo="heuristica_llm"` — de fora, a
falha de formato é indistinguível de um acerto. Um cliente instrumentado
tenta `_parse_llm_classification` em cada resposta e conta as rejeições.
"Válido" é o schema inteiro (`domain` + `complexity` + `confidence`), não só
sintaxe de JSON.

**A etapa `roteador` exercita o LLM em poucos casos.** Na medição de
2026-10-16, 40 mensagens do dataset produziram apenas 9 chamadas ao modelo:
o atalho de cortesia e o caminho rápido da heurística resolvem o resto sem
LLM. É o comportamento de produção e é isso que se quer medir, mas significa
que a amostra de latência dessa etapa é pequena — o grosso da latência de
geração aparece em `rag` e `injecao`.

**Nada é baixado automaticamente.** Modelo não baixado é pulado com o
`ollama pull` sugerido. São dezenas de GB; a decisão de baixar é do dono da
máquina.

## Pré-requisito ainda não cumprido

O corpus real do RAG **ainda não foi ingerido**, e os datasets de
`router_intents`, `rag_quality` e `prompt_injection` foram montados sobre
outros documentos. Enquanto não forem refeitos, qualquer número que saia
daqui vale como teste da ferramenta, não como resultado do TCC — por isso
`results/` está vazio. Ordem correta: ingerir o corpus → refazer os
datasets → rodar o benchmark.

## Candidatos

`modelos.json` lista os candidatos de `docs/ARCHITECTURE.md` (tabela de
escopo, linha "Modelo local"). São **10 configurações**, embora o texto do
documento diga "9": Llama 3.1 8B; Qwen2.5 7B; Qwen3 14B (Q4_K_M, Q5_K_M);
Qwen3 8B (Q5_K_M, Q8_0); Phi-4-mini; Phi-4; Gemma-4-12B (4-bit, 8-bit).
A contagem precisa ser acertada em `ARCHITECTURE.md` ou um candidato
retirado daqui.

Só `gemma4:12b-it-q4_K_M` está baixado nesta máquina. Sugestão para a
primeira rodada, se não quiser baixar tudo: os dois Gemma-4-12B, o Qwen3 8B
Q5_K_M, o Phi-4-mini e o Llama 3.1 8B — cobre as quatro famílias e os dois
extremos de tamanho. O `generate()` do `OllamaClient` já manda
`think=False`, então o Qwen3 roda sem *thinking* sem configuração extra.
