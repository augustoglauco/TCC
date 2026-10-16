# Avaliação Experimental do Protótipo

Este documento detalha, em termos operacionais, as quatro avaliações
experimentais descritas em `docs/ARCHITECTURE.md` (Seção 9). O objetivo é
sair de uma entrega apenas funcional para uma análise estruturada dos
resultados — item explicitamente pedido pelo orientador como parte dos
critérios de aprovação do TCC.

Scripts e artefatos de cada avaliação devem viver em `eval/`, um
subdiretório por frente (ver `docs/CONVENTIONS.md`), com resultados salvos
como JSON ou CSV versionados (dados pequenos) para permitir comparação entre
execuções.

## 0. Dimensionamento dos conjuntos de teste

Decisão de 2026-10-16. Os tamanhos citados nas seções 1 a 4 abaixo (40
mensagens, 20 perguntas, 8 casos de injeção) eram **exemplos iniciais**, não
um dimensionamento: com eles, o intervalo de confiança de 95% de uma taxa
perto de 90% tem meia-largura de ±15 pontos percentuais com n=18 e ±9,5 pp
com n=40 — larga demais para afirmar que um modelo é melhor que outro, que é
a pergunta que a Fase 10 precisa responder. Esta seção fixa os tamanhos
reais e é a fonte única; as seções seguintes descrevem o método, não a
quantidade.

### Poder estatístico: o que cada tamanho compra

Meia-largura do IC 95% (Wilson), em pontos percentuais:

| n | p=0,70 | p=0,80 | p=0,90 |
| --- | --- | --- | --- |
| 18 | ±19,2 | ±18,1 | ±14,8 |
| 40 | ±13,7 | ±12,1 | ±9,5 |
| 100 | ±8,8 | ±7,8 | ±6,0 |
| 200 | ±6,3 | ±5,5 | ±4,2 |
| 300 | ±5,2 | ±4,5 | ±3,4 |

O IC isolado, porém, é o critério **errado** para comparar candidatos. Como
todos os modelos respondem exatamente aos mesmos itens, a comparação é
pareada, e um teste pareado (McNemar, ou bootstrap pareado para notas) é
muito mais sensível: só conta os itens em que os dois discordam. Com n=200 e
20% de discordância, detecta diferença de ~8,9 pp com poder de 80%; com
n=300, ~7,2 pp. **O relatório deve usar McNemar entre pares de candidatos e
reservar o IC de Wilson para descrever cada um isoladamente.**

### Tamanhos definidos

| Conjunto | Antes | Definido | O que isso compra |
| --- | --- | --- | --- |
| Corpus ingerido no RAG | 0 | **os 97 PDFs** de `docs/Manuais_fornecedor/ControlId/` | distratores reais na recuperação; um corpus pequeno infla artificialmente a taxa de fonte correta |
| Roteador (`router_intents`) | 40 | **300 mensagens**, das quais **≥200 chegam ao LLM** | ±3,4 pp isolado; McNemar detecta ~7 pp |
| RAG (`rag_quality`) | 18 | **180 perguntas**, incluindo **20 sem resposta no corpus** | ±0,18 na nota média (DP≈1,2); as 20 medem alucinação |
| Injeção (`prompt_injection`) | 8 | **100 casos** (50 diretos + 50 indiretos) | ±7,8 pp — suficiente para uma taxa, não para fatiar por domínio |
| Imagem (`model_benchmark/imagens`) | 9 | **120 imagens** (90 produto + 30 não-produto) | ±5,4 pp; 30 negativos dão base real à taxa de falso positivo |
| Latência (`latency`) | — | **60 prompts × 3 repetições** | 180 amostras por modelo: p95 estável |

**Por que 300 mensagens no roteador, e não 300 "representativas".** Medido em
2026-10-16: das 40 mensagens do conjunto atual, só **9 chegam ao LLM** — o
atalho de cortesia e o caminho rápido da heurística resolvem o resto sem
modelo. Num conjunto "realista" de 300, o modelo decidiria ~70, e o n efetivo
para comparar candidatos seria 70, não 300. O conjunto precisa ser desenhado
para exercitar o LLM: pelo menos 200 mensagens ambíguas, com sinônimos fora
de `_DOMAIN_KEYWORDS` ou com duas palavras-chave de domínios diferentes. As
outras 100 cobrem o caminho fácil, para que a acurácia de manchete continue
descrevendo o sistema como ele roda em produção. As duas taxas são
reportadas separadamente: **acurácia do sistema** (300) e **acurácia do
modelo no subconjunto que lhe chega** (≥200).

### Custo de execução (medido nesta máquina)

`gemma4:12b-it-q4_K_M` numa RTX 4080 SUPER 16GB, 2026-10-16: **45,7 tok/s**
de saída; resposta RAG completa (~195 tokens) em **4,3 s**; classificação do
roteador em **1,0 s**; descrição de imagem em **2,0 s**; carga do modelo na
VRAM em 0,5 s a quente e ~13 s a frio.

Por modelo, uma rodada completa:

| Etapa | Chamadas ao modelo | Tempo de GPU |
| --- | --- | --- |
| Roteador | ~200 | ~4 min |
| RAG | 180 | ~13 min |
| Injeção | 100 | ~7 min |
| Imagem | 120 | ~4 min |
| **Total** | ~600 | **~30 min** |

Candidatos de 14B em Q5/Q8 devem levar 2 a 3× isso. Para os 10 candidatos,
o tempo de GPU fica entre **5 e 15 horas** — cabe numa noite ou num fim de
semana, dentro do que o dono aceitou ("deixar a máquina ligada por dias").

**O gargalo não é a GPU, é o LLM-as-judge.** As etapas `rag` e `injecao`
precisam de uma chamada de juiz por item: 280 por modelo, **2.800 no total**.
No tier `:free` do OpenRouter, com a pausa proativa de 3 s e o backoff de 8 s
a cada 429 já implementados, isso domina o relógio e esbarra no limite
diário da conta. Duas saídas:

1. **Juiz pago** (recomendado): 2.800 chamadas de ~1k tokens custam cerca de
   **US$ 1** num modelo barato de julgamento. Remove o rate limit, torna o
   tempo previsível e mantém a independência (juiz externo ≠ modelo avaliado).
2. Juiz local num modelo diferente do avaliado: custo zero, mas enfraquece o
   argumento de independência que motivou o juiz externo nas seções 2 e 4.

### Triagem em duas rodadas

Rodar as quatro etapas nos 10 candidatos é desperdício: metade é eliminada
pelas etapas baratas. Procedimento:

1. **Triagem** — `--etapas roteador,imagem` nos 10 candidatos (~8 min de GPU
   cada, nenhuma chamada de juiz, custo zero). Elimina quem não segue o
   formato JSON, quem não cabe na VRAM e quem não tem visão local, se visão
   local virar requisito.
2. **Rodada completa** — as quatro etapas nos **4 a 5 sobreviventes**. Reduz
   as chamadas de juiz de 2.800 para ~1.200 e o tempo total para algo entre
   4 e 8 horas.

O critério de corte da triagem é registrado **antes** de rodar, no README de
`eval/model_benchmark/`, para não virar escolha a posteriori.

### O custo real é a revisão humana, não a máquina

Os quatro conjuntos somam **700 itens** com gabarito. Gabarito errado é pior
que amostra pequena: contamina todos os candidatos igualmente e passa
despercebido. O procedimento é o mesmo já usado nos conjuntos atuais —
rascunho gerado por LLM externo, **revisão humana item a item** — e a
estimativa honesta é de 8 a 12 horas de trabalho do desenvolvedor,
distribuídas:

| Conjunto | Itens | Esforço de revisão |
| --- | --- | --- |
| Roteador | 300 | baixo (rótulo de 1 palavra) — ~3 h |
| RAG | 180 | alto (exige conferir a resposta no PDF) — ~5 h |
| Injeção | 100 | médio (escrever o `criterio_falha`) — ~2 h |
| Imagem | 120 | baixo (nome do produto vem da pasta) — ~1 h |

As 30 imagens não-produto precisam vir de fora: o repositório só tem duas
imagens reais que não são produto, e são o mesmo comprovante com valores
diferentes. Qualquer conjunto de fotos avulsas serve.

### Ordem de execução

1. Ingerir os 97 PDFs e medir quantos chunks resultam.
2. Montar e revisar os quatro conjuntos (acima).
3. Triagem nos 10 candidatos.
4. Rodada completa nos sobreviventes.
5. Latência local × externo (seção 3) com o vencedor.
6. `eval/RESUMO.md` com McNemar entre os finalistas.

## 1. Acerto do roteador na identificação de intenções

**O que mede:** proporção de mensagens de teste roteadas para a intenção
correta, entre os quatro domínios (Vendas, Suporte Técnico, Atendimento ao
Usuário, Agendamento de Visita).

**Como montar o conjunto de teste (`eval/router_intents/`):**
- **300 mensagens** rotuladas manualmente, cobrindo os quatro domínios de
  forma equilibrada, das quais ≥200 desenhadas para chegar ao LLM — o
  dimensionamento e o porquê estão na Seção 0 (o "30–50" original era
  exemplo inicial, e o conjunto de 40 que existe hoje veio dele).
- Incluir mensagens reais (se disponíveis) e sintéticas.
- Incluir deliberadamente casos ambíguos (ex.: mensagens que poderiam ser
  Suporte ou Atendimento) para expor limites do classificador.
- Formato sugerido: CSV/JSON com colunas `mensagem`, `intencao_esperada`.

**Como avaliar:**
- Rodar o roteador sobre o conjunto de teste e registrar a intenção prevista
  para cada mensagem.
- Calcular acurácia geral (% de acertos).
- Construir uma matriz de confusão 4x4 (domínio esperado x domínio previsto)
  para identificar padrões de erro — ex.: confusão sistemática entre Suporte
  e Atendimento.
- Com os provedores disponíveis (`intent_router_provider`, ver
  `docs/ARCHITECTURE.md` §5), rodar o mesmo conjunto de teste para cada
  provedor (`heuristica`, `heuristica_llm` e `jev_openrouter`) e comparar acurácia,
  latência e custo entre eles — essa comparação (baseline de heurística pura vs.
  híbrido com LLM local vs. decisão estruturada Jev) enriquece a análise empírica
  deste TCC. Usar `ClassificationResult.provider_efetivo`
  (não o `intent_router_provider` selecionado) para confirmar que nenhuma
  execução da rodada `jev_openrouter` degradou silenciosamente para a
  heurística por falha da API — isso contaminaria a comparação.

**Saída esperada:** `eval/router_intents/results.json` (ou `.csv`) +
matriz de confusão (imagem ou tabela) para incluir no relatório final;
quando comparando provedores, um resultado por provedor.

## 2. Qualidade das respostas do RAG

**O que mede:** relevância e correção das respostas geradas a partir do
conteúdo recuperado (catálogo, documentos, manuais).

**Como montar o conjunto de referência (`eval/rag_quality/`):**
- **180 perguntas** sobre o catálogo/documentação com resposta esperada
  conhecida (ground truth definido manualmente), das quais **20 sem
  resposta no corpus**, para medir alucinação — ver Seção 0 (o "15–20"
  original era exemplo inicial).
- Cobrir tanto RAG textual (PDFs, manuais) quanto, se possível, RAG de
  imagem (busca de produto por foto).

**Como avaliar:**
- Avaliação manual em escala simples (ex.: 1 a 5) comparando a resposta
  gerada com a resposta esperada.
- Complementar com um LLM avaliador (LLM-as-judge) para escalar a análise —
  usar um prompt de avaliação simples e documentado (critérios: relevância,
  correção factual, uso da fonte recuperada).
- Registrar também, por pergunta, se a fonte recuperada era a correta
  (separa erro de recuperação de erro de geração).

**Saída esperada:** `eval/rag_quality/results.json` com pergunta, resposta
gerada, nota manual, nota do LLM avaliador e fonte recuperada.

## 3. Latência: modelo local x modelo externo

**O que mede:** tempo de resposta (média e percentil 95) para um mesmo
conjunto de perguntas, comparando modelo local e modelo externo.

**Como montar (`eval/latency/`):**
- Reaproveitar um subconjunto das perguntas das avaliações 1 e 2, ou um
  conjunto novo representativo dos quatro domínios.
- Rodar o mesmo conjunto de prompts:
  - No modelo local (GPU 16GB, via Ollama/vLLM).
  - Em um modelo externo via API.
- Medir tempo ponta a ponta (do envio do prompt à resposta completa),
  registrando também tokens de entrada/saída, se disponível.

**Como avaliar:**
- Calcular média e percentil 95 de latência para cada modelo.
- Registrar o trade-off qualitativo: custo/privacidade (modelo local) x
  velocidade/qualidade (modelo externo) — ligando ao resultado da avaliação
  comparativa entre os dois modelos locais candidatos (ver
  `docs/ARCHITECTURE.md`, tabela de escopo, linha "Modelo local").

**Saída esperada:** `eval/latency/results.json` com latências por
pergunta/modelo + resumo estatístico (média, p95).

## 4. Resiliência a prompt injection (direta e indireta via RAG)

**O que mede:** se o pipeline real (modelo local e modelo externo) obedece
a uma instrução maliciosa embutida na mensagem do cliente (injeção direta)
ou em um documento recuperado pelo RAG (injeção indireta), depois do
isolamento por delimitador descrito em `app.router.prompt_safety` (ver
`docs/ARCHITECTURE.md` §6 e `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md`).

**Como montar o conjunto de teste (`eval/prompt_injection/`):**
- `dataset.json` com **100 casos** (50 diretos + 50 indiretos; ver
  Seção 0 — os 8 atuais eram exemplo inicial) cobrindo os quatro domínios,
  duas categorias:
  `injecao_direta` (instrução maliciosa na mensagem do cliente) e
  `injecao_indireta_rag` (instrução maliciosa embutida no `content` de um
  documento recuperado), cada caso com um `criterio_falha` descrevendo o
  que contaria como o modelo tendo obedecido à injeção.

**Como avaliar:**
- `run_eval.py` roda cada caso contra o cliente local (Ollama) e o externo
  (OpenRouter), gerando a resposta real do pipeline (via `_build_prompt`,
  já com o isolamento por tag aplicado).
- Um LLM-as-judge externo (mesmo motivo da avaliação 2: reduzir o viés de o
  modelo local se autoavaliar) julga, por caso, se a resposta obedeceu ao
  `criterio_falha` (`comprometido: true/false`).
- Taxa de resistência = proporção de casos em que o modelo NÃO obedeceu à
  instrução injetada.

**Resultado real (execução de 2026-10-07, ver
`eval/prompt_injection/README.md` e `results.json`):** taxa de resistência
local de **62,5% (5/8)** e externa de **87,5% (7/8)**. Os 4 casos de
injeção direta foram resistidos por ambos os clientes (100%); toda falha
veio de `injecao_indireta_rag`. O achado mais relevante é o **Caso 7**
(instrução de reembolso automático sem nota fiscal embutida em um
documento do RAG), que comprometeu **ambos** os clientes — evidência de
que o isolamento sintático por delimitador é eficaz contra injeção direta,
mas não impede, por si só, que o modelo trate uma instrução indireta
plausível (que se parece com uma política de negócio legítima) como
informação confiável.

**Saída esperada:** `eval/prompt_injection/results.json` com, por cliente
(local/externo), taxa de resistência e o detalhe (resposta gerada,
julgamento e justificativa do juiz) de cada caso.

## Benchmark comparativo dos modelos locais candidatos

**O que mede:** qual dos candidatos a `LOCAL_MODEL_NAME` (ver
`docs/ARCHITECTURE.md`, tabela de escopo, linha "Modelo local") entrega a
melhor relação custo/latência/qualidade **dentro do sistema completo** — não
em teste sintético isolado.

**Como roda (`eval/model_benchmark/run_benchmark.py`):** o orquestrador não
cria avaliação nova. Reexecuta as avaliações 1, 2 e 4 acima trocando só o
modelo local, reaproveitando os mesmos datasets, os mesmos prompts de juiz e
o caminho real de produção. Cada etapa é gravada assim que termina e uma
nova execução pula o que já está no arquivo, porque uma rodada completa leva
horas e cai por OOM de VRAM, queda do Ollama ou rate limit do juiz.

**Métricas por modelo:** `roteador_acuracia`, `json_invalido_taxa`,
`rag_nota_media`, `rag_fonte_correta_taxa`, `injecao_resistencia`,
`visao_local`, `imagem_portfolio_acerto`, `imagem_categoria_acerto`,
`latencia_media_s`, `latencia_p95_s`, mais `carga_s`, `vram_bytes` e
`capabilities` em `config`.

**Etapa `imagem` (R2/R5):** o sistema é multimodal e a visão local **não é
um slot separado** — `OllamaClient.describe_image` usa o mesmo
`LOCAL_MODEL_NAME` do texto. Candidato sem capability `vision` não é
excluído nem pulado em silêncio: o resultado registra `visao_local: false`,
que significa que toda imagem de cliente cairia para a visão externa (custo
por token e a imagem saindo da máquina) — o trade-off que a comparação
precisa expor. Quem tem visão é medido com o mesmo `_VISION_PROMPT` e o
mesmo parse de `app.rag.image_identification`, contra fotos de produto já
versionadas em `docs/Manuais_fornecedor/`. Pontuação determinística (sem
LLM-as-judge) e sem exigir o SKU exato: no fluxo real quem identifica com
precisão é o CLIP contra o catálogo interno, e a visão é o fallback que só
precisa dizer se é do portfólio e, grosso modo, o que é. O conjunto tem
casos positivos **e** negativos: sem negativo, um modelo que aprova qualquer
imagem marcaria 100%.

**Reprodutibilidade:** o benchmark roda com seed fixa (`--seed 42`), embora
produção rode sem seed. Sem ela, duas execuções do mesmo modelo sobre o
mesmo caso divergem, e com amostras de 8 a 40 casos esse ruído se confunde
com a diferença entre candidatos. A seed não torna o número mais verdadeiro
— torna a comparação entre candidatos reproduzível.

**Saída esperada:** um arquivo por modelo em
`eval/model_benchmark/results/<id>.json`, no envelope
`{versao, avaliacao, modelo, gerado_em, config, metricas, itens}`.

**Pré-requisito:** o corpus real precisa estar ingerido e os datasets das
avaliações 1, 2 e 4 refeitos sobre ele — os atuais foram montados com outros
documentos. Decisões de medição (aquecimento descartado, `unload()` entre
candidatos, por que `json_invalido_taxa` é medida à parte da acurácia) em
`backend/eval/model_benchmark/README.md`.

## Página pública de resultados

`/avaliacao` (sem login) mostra gráficos das avaliações acima, alimentados
por `GET /api/avaliacao/resultados` (`backend/src/app/api/avaliacao.py`),
que lê os `results.json` de `eval/`. Só agregados saem pela API: respostas
geradas, trechos recuperados e payloads de injeção ficam fora. Percentuais
trazem intervalo de confiança de 95% (Wilson). Resultados do benchmark por
modelo entram por `eval/model_benchmark/results/<modelo>.json` no envelope
`{modelo, gerado_em, config, metricas, itens}`; `metricas` aceita
`roteador_acuracia`, `rag_nota_media`, `injecao_resistencia`,
`latencia_p95_s`, entre outras.

## Consolidação

Ao final das quatro avaliações, gerar um resumo curto (pode ser um novo
arquivo `eval/RESUMO.md` ou uma seção no relatório final do TCC) com:
- Acurácia do roteador + principais padrões de erro da matriz de confusão.
- Nota média de qualidade do RAG (manual e LLM-as-judge) + taxa de
  recuperação correta.
- Latência média/p95 local x externo + recomendação de uso (quando preferir
  cada um).
- Taxa de resistência a prompt injection (local x externo) + o achado do
  Caso 7 (injeção indireta via RAG), já que ele qualifica a eficácia real
  do isolamento por delimitador implementado nesta frente.

Esse resumo é o insumo direto para a Seção 9 do documento de proposta
(`Documento_Projeto_Assistente_Multimodal_com_avaliacao.docx`) e para a
apresentação final ao orientador.
