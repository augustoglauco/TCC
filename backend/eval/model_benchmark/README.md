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
| `imagem` | `imagens/dataset.json` (aqui) | `visao_local`, `imagem_portfolio_acerto`, `imagem_categoria_acerto`, `imagem_json_valido_taxa` |

Em todas: `latencia_media_s`, `latencia_p95_s`, `chamadas_medidas`, mais
`carga_s`, `vram_bytes`, `capabilities` e `visao_local` em `config`.

## Visão: por que a etapa existe e por que ninguém é excluído

O sistema é multimodal (R2/R5), e **visão local não é um slot separado**:
`OllamaClient.describe_image` usa o mesmo `self._model` do texto — não
existe `LOCAL_VISION_MODEL_NAME`. Se o modelo escolhido não tiver a
capability `vision`, o método levanta `VisionModelIndisponivelError` e a
imagem cai para a visão **externa**.

Por isso um candidato text-only não é descartado nem pulado em silêncio: o
resultado registra `visao_local: false`, que **é** o resultado — significa
que toda imagem de cliente passa a ir para a API externa, com custo por
token e saindo da máquina. Omitir a linha faria dois candidatos parecerem
empatados quando um resolve imagem em casa e o outro terceiriza.

As capabilities vêm do próprio Ollama (`GET /api/show`), a mesma fonte que
`describe_image` consulta — não há tabela mantida à mão para desatualizar.

A pontuação da etapa é determinística, sem LLM-as-judge: o gabarito é
objetivo. E **não se exige o SKU exato**, porque no fluxo real quem
identifica com precisão é o CLIP contra o catálogo interno; a visão é o
fallback que só precisa dizer se é do portfólio e, grosso modo, o que é.
Daí as três taxas: formato (`json_valido`), `e_do_portfolio` correto, e
categoria dentro dos termos aceitos do caso.

Medição de 2026-10-16 com `gemma4:12b-it-q4_K_M`: JSON válido 8/8,
`e_do_portfolio` 8/8, categoria 4/8 — o modelo responde "identificador
biométrico" para quase tudo, o que acerta os leitores e erra a impressora
(`Print iD Touch`) e a fonte de alimentação (`iDPower`). É sinal útil: o
candidato é confiável para "é do nosso portfólio?" e fraco para distinguir
famílias de produto.

Armadilha encontrada nessa primeira execução: o casamento de categoria
precisa normalizar acento. O modelo escreve "biométrico" e o termo aceito no
dataset é "biometri" — sem `unicodedata.normalize`, três acertos contavam
como erro.

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
- `--etapas` aceita `roteador`, `rag`, `injecao`, `imagem` (padrão: as quatro).
- `--timeout-s` tem padrão de 180s, bem acima do `LOCAL_LLM_TIMEOUT_S` (30s)
  de produção: candidatos de 14B em Q5/Q8 numa GPU de 16GB levam muito mais
  tempo para carregar, e um timeout curto reprovaria o modelo por tempo de
  carga, não por qualidade.

**Dependências por etapa:** `roteador` e `imagem` só precisam do Ollama
(`imagem` usa fotos já versionadas em `docs/Manuais_fornecedor/`). `rag` e
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

**Ponto em aberto para a escolha final:** dessas 10 tags, só as duas de
Gemma-4-12B devem ter `vision` — as demais são variantes text-only, e as
multimodais das mesmas famílias são outras tags (`qwen2.5-vl`, `qwen3-vl`,
`llama3.2-vision`, `phi4-multimodal`). Confirmado pelo Ollama apenas para o
que está baixado; para o resto, é pela família. Se visão local for
requisito, a lista de candidatos é que precisa ser revista — o benchmark vai
reportar o fato, não escondê-lo.

Só `gemma4:12b-it-q4_K_M` está baixado nesta máquina. Sugestão para a
primeira rodada, se não quiser baixar tudo: os dois Gemma-4-12B, o Qwen3 8B
Q5_K_M, o Phi-4-mini e o Llama 3.1 8B — cobre as quatro famílias e os dois
extremos de tamanho. O `generate()` do `OllamaClient` já manda
`think=False`, então o Qwen3 roda sem *thinking* sem configuração extra.
