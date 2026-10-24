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

O conjunto é de **8 positivos + 1 negativo** (um comprovante de depósito
sintético, do próprio fluxo de comprovante do sistema). Sem negativo, um
modelo que responde `e_do_portfolio: true` para qualquer imagem marcaria
100% — a primeira versão deste dataset tinha esse furo.

`categoria` só é cobrada nos positivos. Num negativo a resposta certa é
"nenhum", e exigir que o modelo ainda descreva o que está na foto puniria
exatamente o comportamento desejado — além de ser informação que o fluxo
real descarta (`e_do_portfolio: false` já vira "não identificado" em
`identify_product_by_image`).

Medição de 2026-10-16 com `gemma4:12b-it-q4_K_M` e `--seed 42`: JSON válido
9/9, `e_do_portfolio` 9/9 (inclusive o negativo), categoria 6/8. Erra a
fonte de alimentação (`iDPower`, que chama de "controlador de acesso") e o
`REP iDClass` (relógio de ponto, que chama de "identificador biométrico") —
acerta todo o resto, inclusive a impressora e a catraca. Sinal útil: o
candidato é confiável para "é do nosso portfólio?" e erra ao distinguir
famílias quando o equipamento não é um leitor.

Duas armadilhas encontradas ao rodar pela primeira vez, ambas corrigidas:
o casamento de categoria precisa normalizar acento ("biometri" não casa com
"biométrico" — três acertos contavam como erro); e sem seed fixa as rodadas
não eram comparáveis entre si.

## Uso

A partir de `backend/`, com o Ollama no ar:

```bash
.venv/bin/python eval/model_benchmark/run_benchmark.py --listar
.venv/bin/python eval/model_benchmark/run_benchmark.py --etapas roteador
.venv/bin/python eval/model_benchmark/run_benchmark.py --modelos gemma4-12b-q4,phi4-mini-bf16
.venv/bin/python eval/model_benchmark/run_benchmark.py --forcar
```

- `--listar` mostra, por candidato, se o modelo está baixado e quais etapas
  já foram medidas. Não chama modelo nenhum.
- `--etapas` aceita `roteador`, `rag`, `injecao`, `imagem` (padrão: as quatro).
- `--timeout-s` tem padrão de 180s, bem acima do `LOCAL_LLM_TIMEOUT_S` (30s)
  de produção: candidatos de 14B em Q5/Q8 numa GPU de 16GB levam muito mais
  tempo para carregar, e um timeout curto reprovaria o modelo por tempo de
  carga, não por qualidade.
- `--seed` tem padrão **42**, enquanto produção roda sem seed
  (`LOCAL_LLM_SEED` vazio). Sem ela, duas execuções do mesmo modelo sobre o
  mesmo caso divergem: medido em 2026-10-16, a mesma foto de catraca saiu
  como "catraca", "torneira eletrônica", "lança de controle de acesso" e
  "extintor de incêndio" em quatro rodadas. Com 8 a 40 casos por etapa, esse
  ruído se confunde com a diferença entre candidatos. A seed não torna o
  número mais "verdadeiro" — torna a **comparação** reproduzível. `--seed 0`
  roda sem seed, como produção.

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

## Critério de corte da triagem (registrado em 2026-10-17, ANTES de rodar)

A triagem roda `--etapas roteador,imagem` nos 9 candidatos: ~8 min de GPU
cada, nenhuma chamada de juiz, custo zero. A rodada completa (as quatro
etapas, com juiz no tier `:free`) só roda nos sobreviventes. Este critério
está escrito aqui **antes** da primeira triagem de propósito: decidido
depois, seria escolha a posteriori, e o número que sobrevive sempre parece
razoável quando já se sabe quem ele elimina.

Todos os campos citados são os de `metricas` em `results/<id>.json`.

**Eliminatórios** (reprova em qualquer um, sai):

1. **Cabe na VRAM:** o candidato roda até o fim sem OOM e com
   `vram_bytes` ≤ 15 GB. A placa tem 16 GB e o Qdrant/embedder convivem na
   máquina.
2. **Respeita o formato:** `json_invalido_taxa` ≤ 0,10 na etapa roteador. Um
   candidato que quebra o JSON cai na heurística do `_classify_with_llm`, e aí
   o que está sendo medido não é mais ele — é o fallback.
3. **Serve ao produto:** `latencia_p95_s` ≤ 30 s. É o `LOCAL_LLM_TIMEOUT_S` de
   produção: acima disso o chat corta a resposta de qualquer forma.

**Comparativo** (entre os que passaram nos três):

4. **Fica quem está dentro de 10 pp de `roteador_acuracia` do melhor.** Não é
   corte absoluto: com 300 mensagens o IC 95% de Wilson a p=0,70 é ±5,2 pp,
   então 10 pp é cerca de dois intervalos e evita eliminar candidato por
   ruído de amostra. McNemar pareado, que é o teste do relatório final, entra
   só na rodada completa.
5. **Teto de 5 sobreviventes.** Se mais de 5 passarem, ficam os 5 de maior
   `roteador_acuracia`. Empate se resolve primeiro por `visao_local: true`
   (resolve imagem de cliente em casa, sem terceirizar para a visão externa)
   e depois por menor `latencia_p95_s`.

**`visao_local: false` não elimina.** A produção já trata visão local como
opcional: `OllamaClient.describe_image` usa o mesmo `LOCAL_MODEL_NAME`, e
candidato sem a capability manda a imagem do cliente para a visão externa —
caminho documentado, não defeito. Exigir visão local cortaria 2 dos 9
candidatos (DeepSeek-R1-Distill e Phi-4-mini) por um requisito que o sistema não impõe. Fica como atributo
medido e critério de desempate; se o vencedor não tiver visão local, o
relatório precisa dizer que toda imagem de cliente passa a depender do modelo
externo.

### Resultado da triagem (2026-10-24)

Sobreviventes confirmados pelo dono: **gemma4-12b-q4, gemma4-e4b-q8,
qwen25-vl-3b e qwen25-vl-7b**. Eliminados: gemma3-gaia-4b (72,9%, 12,3 pp do
melhor), qwen35-9b, phi4-mini, deepseek-r1 e qwen35-9b-defiant (JSON inválido
> 10%); o llama32-11b-vision foi descartado do pool (não carregava: `mllama` ausente no Ollama 0.30.6).
Tabela completa, aplicação do critério, análise e limites em
`docs/EVALUATION.md`, seção "Resultado da triagem dos candidatos".

## Candidatos

`modelos.json` lista os candidatos de `docs/ARCHITECTURE.md` (tabela de
escopo, linha "Modelo local"). São **9 configurações** (o Llama 3.2 11B Vision foi descartado em 2026-10-24: não carrega no Ollama 0.30.6): Qwen2.5-VL 7B Instruct; Qwen2.5-VL 3B Instruct; Qwen3.5 9B Q4_K_M;
DeepSeek-R1-Distill-Llama-8B Q8_0; Qwen3.5 9B Defiant Fable MTP; Phi-4-mini-instruct BF16; Gemma-3-Gaia-PT-BR 4B F16; Gemma-4-12B 4-bit; Gemma-4-E4B-it UD-Q8_K_XL.

**Ponto em aberto para a escolha final:** dessas 9 tags, Gemma-3-Gaia 4B F16, Gemma-4-12B 4-bit, Gemma-4-E4B-it, Qwen2.5-VL 7B Instruct, Qwen2.5-VL 3B Instruct, Qwen3.5 9B Q4_K_M e Qwen3.5 9B Defiant Fable MTP têm `vision` (7 dos 9 candidatos com visão local nativa) — só DeepSeek-R1-Distill-Llama-8B e Phi-4-mini são text-only. Confirmado pelo Ollama (`/api/show`, capabilities) em 2026-10-18. Se visão local for
requisito, a lista de candidatos é que precisa ser revista — o benchmark vai
reportar o fato, não escondê-lo.

Atualmente, **todos os 9 modelos candidatos já estão baixados** nesta máquina via Ollama/HuggingFace Hub. O `generate()` do `OllamaClient` já manda
`think=False`, então os modelos da família Qwen3.5 rodam sem *thinking* sem configuração extra.
