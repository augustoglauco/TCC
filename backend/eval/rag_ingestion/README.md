# Otimização dos parâmetros de ingestão do RAG (R4, Fase 10)

Ver `docs/EVALUATION.md` Seção 2.1 para o desenho completo (as sete etapas,
métricas e custos) e `docs/ARCHITECTURE.md` (decisões de 2026-10-17) para o
"porquê" das duas mudanças que mexem em código de produção.

**Corpus:** `docs/Manuais_fornecedor/ControlId/` — decisão do dono de
2026-10-17. Todo gabarito (documento, imagem e banco) sai dele. Os conjuntos
anteriores de `eval/rag_quality/` (18 perguntas) e `eval/router_intents/`
(40 mensagens) foram montados sobre outros documentos e **não valem mais**.

Esta pasta é complementar a `eval/rag_quality/`, não a substitui:
`rag_quality/` mede a **qualidade da resposta** de uma configuração (com
LLM-as-judge); aqui se **escolhe** a configuração, medindo só
**recuperação** — determinístico, offline e sem nenhuma chamada de API.

## Por que uma pasta nova em vez de estender `rag_quality/`

`chunk_size_search.py` (em `rag_quality/`, 2026-10-01; removido depois) acopla recuperação e
geração: cada configuração candidata custa 18 chamadas de LLM-as-judge, o
que esbarrou em rate limit (429) do OpenRouter e limitou o experimento a 7
pontos por bisseção, em vez de uma grade. Como as 180 perguntas da
Estratégia A (`docs/EVALUATION.md` Seção 0) trazem **PDF de origem +
trecho** no gabarito, `Recall@k` / `nDCG@10` / `MRR` podem ser calculados
sem gerar resposta nenhuma — ~30 s por configuração contra ~15 min. É isso
que torna a grade de 15 pontos da Etapa 3 viável.

O LLM-as-judge volta **uma vez só**, na Etapa 7, para confirmar que o ganho
de recuperação virou ganho de resposta.

## Scripts

- `preparar_corpus.py` — executa as três decisões de 2026-10-17 sobre o
  corpus: converte as 4 imagens rejeitadas para JPEG, converte o `.html`
  para `.md` e deixa os 11 PDFs degenerados de fora (nenhuma ação). **Não
  apaga os originais.** Idempotente; `--dry-run` mostra o plano.
  **Rodar este script é obrigatório numa máquina nova:** o corpus inteiro é
  `gitignored` (`.gitignore:21`, `docs/Manuais_fornecedor/`), então os
  arquivos convertidos **não** vêm no clone. Sem ele, a pergunta `q12` do
  conjunto mínimo falha, porque o `.md` do doc de API não existe.
- `run_etapa1.py` — **Etapa 1**. Cria uma collection temporária com os
  parâmetros dados, ingere, roda as perguntas e devolve `Recall@k`,
  `nDCG@10`, `MRR` e taxa de vazio. Exige Qdrant e Postgres no ar. Apaga a
  collection no `finally`, sempre.
- `run_etapa2.py` — **Etapa 2**. Compara os 4 candidatos de embedding
  (`paraphrase-multilingual-MiniLM-L12-v2`, `google/embeddinggemma-300m`,
  `intfloat/multilingual-e5-large-instruct` e `BAAI/bge-m3`) respeitando a
  janela de tokens de cada modelo e aplicando os prefixos de tarefa
  assimétricos (`query_prefix` vs `document_prefix`). Retomável por
  candidato; grava `resultados_etapa2.json`.
- `run_etapa3.py` — **Etapa 3**. Varre a grade 5×3 de `chunk_size` ∈ {128,
  256, 512, 768, 1024} tokens × `overlap` ∈ {10%, 15%, 20%} com o corte
  recursivo (`\n\n` → `\n` → `. ` → `" "`) e contagem por tokenizer em
  `app.rag.chunking.chunk_text`. Retomável por ponto; grava
  `resultados_etapa3.json`.
- `dataset.py` — **carregador único do gabarito** (2026-10-18). Lê o conjunto
  canônico `eval/rag_quality/dataset.json` (o mesmo que `/admin/datasets`
  revisa) e entrega aos runners das Etapas 1–5 `{dominio, _pastas, perguntas}`.
  Só passam itens `aprovado`/`corrigido`; `descartado`, duplicada,
  `trecho_confere=false` e `origem_ambigua` ficam de fora (cada corte é contado
  e impresso); `sem_resposta` vira caso **negativo** (`fontes_aceitas` vazia);
  `_pastas` é o corpus inteiro da auditoria. `--incluir-pendentes` (em todos os
  runners) permite um **ensaio** antes da revisão, gravado com o rótulo
  `dataset.json+pendentes` — não vale como decisão. O antigo
  `dataset_minimo.json` (n=15) foi removido: os `resultados_etapa*.json`
  existentes são dele, ficam como histórico e são recalculados na próxima
  rodada.
- `metricas.py` — as métricas como funções **puras**, testadas em
  `backend/tests/test_rag_ingestion_eval.py` sem nenhuma infraestrutura.
- `varrer_threshold.py` — **Etapa 4**. Varre `score_threshold` × `top_k`
  **offline**, sobre o JSON da Etapa 1 ou da Etapa 3 (`--entrada`, `--saida`,
  `--ponto-id`), sem reingerir nem consultar o Qdrant. Exige que a rodada-base
  tenha usado `--score-threshold 0.0`, recusa rodar sobre uma base já cortada
  e calcula a recomendação de corte (`recomendar_threshold`) no ponto médio
  quando há separabilidade.
- `run_etapa5.py` — **Etapa 5**. Compara as 3 métricas de distância
  (`cosine`, `dot`, `euclid`) e mede o impacto de latência (`media_ms`,
  `p50_ms`, `p95_ms`) do payload index `keyword` em `domain` (`sem_indice` vs
  `indice_domain_keyword`). Grava `resultados_etapa5.json`.
- `auditar_corpus.py` — **Etapa 0**. Audita as três mídias do corpus contra
  as restrições **reais de produção**: PDFs via
  `app.rag.pdf_extract.extract_text_from_pdf` (o extrator de produção, com
  detecção de 2 colunas, não `pdfplumber` cru), imagens via
  `app.ocr.image_processor.detect_image_format` e `MAX_IMAGE_BYTES` (o que
  de fato barra um upload). Cruza as duas por pasta de produto, que é a
  unidade canônica do gabarito. Não exige GPU, Qdrant, Postgres nem rede.
  Saída: `auditoria_corpus.json`.

## Resultado da Etapa 0 (2026-10-17)

| PDFs (97) | | Imagens (77) | |
| --- | --- | --- | --- |
| `util` (≥ 200 chars/pág) | **86** | `valida` | **73** |
| `degenerado` (1–199) | **11** | `formato_rejeitado` (`.tif`) | 3 |
| `sem_texto` | 0 | `acima_do_teto` (> 10 MB) | 1 |

**667.559 caracteres extraíveis** (667.291 nos 86 úteis). Chunks por tamanho
candidato da Etapa 3: 128 tokens → ~1.210 · 256 → ~605 · 512 → ~302 ·
768 → ~202 · 1024 → ~151.

### O que cada uma das 37 pastas sustenta como gabarito

| Capacidade | Pastas |
| --- | --- |
| documento + imagem | **27** |
| só documento | 8 — `Leitor QR Code`, `REP iDClass Facial`, `RHiD`, `Suporte`, `Torniquetes`, `iDBlockBio`, `iDSecure Cloud`, `iDdLock` |
| só imagem | 1 — `iDClass Portaria 373` (2 imagens, único PDF degenerado) |
| nada | 1 — `iDflexpro` (único PDF degenerado, nenhuma imagem) |

O texto é de cauda longa: `iDFace` (110.874 chars), `iDAccess Pro` (75.535) e
`REP iDClass` (69.819) concentram **38% do corpus**, e seis pastas têm menos
de 3.000 chars (`Tags` tem 933). Por isso as 180 perguntas de documento são
ponderadas por volume, não distribuídas 5 por pasta — ver `EVALUATION.md`
Seção 0.

## Três descartes silenciosos

Nenhum dos três levanta erro. É a razão de a Etapa 0 existir.

### 1. Os 11 PDFs em imagem

Todos datasheets ou guias ControlId. Oito rendem **1 caractere em 2 páginas**:

| chars | páginas | arquivo |
| --- | --- | --- |
| 1 | 2 | `IDFit/idfit.pdf` |
| 1 | 2 | `REP iDClass/rep-idclass-1510.pdf` |
| 1 | 2 | `iDAccess/idaccess.pdf` |
| 1 | 2 | `iDBlockBio/idlock-bio-datasheet.pdf` |
| 1 | 2 | `iDBox/idbox-datasheet.pdf` |
| 1 | 2 | `iDClass Portaria 373/idclass373.pdf` |
| 1 | 2 | `iDFlexLite/idflexlite.pdf` |
| 1 | 2 | `iDflexpro/idflexpro.pdf` |
| 59 | 2 | `iDProx/idprox-datasheet.pdf` |
| 59 | 2 | `iDProx/idprox-slim-datasheet.pdf` |
| 142 | 2 | `iDFace Max/idface-max-userguide.pdf` |

**O caminho de OCR já existe — mas só para o banco.** `catalog_extractor`
manda a página ao modelo de visão externo quando ela tem menos de 30 chars
(`extractor.py:502` e `:517`), com conferência humana antes de gravar: esses
11 PDFs alimentam `produtos.especificacoes_tecnicas` normalmente. O caminho
do RAG textual (`app.rag.ingest`) **não tem** esse fallback. Logo uma
pergunta sobre o `iDBox` teria resposta no banco e nenhum documento
recuperável.

**Só 2 produtos perdem de fato a fonte.** Dos 10 diretórios com PDF
degenerado (o `iDProx` tem dois), **8 têm outro PDF legível** e seguem
cobertos:

| Situação | Pastas |
| --- | --- |
| perdem a única fonte | `iDClass Portaria 373`, `iDflexpro` |
| têm outro PDF útil | `IDFit` (16.345 chars), `REP iDClass` (69.819), `iDAccess` (7.767), `iDBlockBio` (37.337), `iDBox` (16.618), `iDFace Max` (9.839), `iDFlexLite` (7.360), `iDProx` (15.307) |

Nos 8, o datasheet em imagem é redundante — OCR ali adiciona uma segunda
fonte a algo já coberto, ganho marginal.

**Decisão pendente do dono:** OCR nos 11, OCR só nos 2, ou deixar os 11 de
fora. Recomendado **deixar de fora**: os 8 não perdem nada, e `iDflexpro` e
`iDClass Portaria 373` rendem 2 casos negativos legítimos. São **2**, não 20
— as outras 18 perguntas sem resposta vêm de produtos ausentes do corpus e
de especificações que nenhum datasheet traz (ver `EVALUATION.md` Seção 0).

### 2. Quatro imagens de produto rejeitadas

`detect_image_format` só reconhece JPEG/PNG/WEBP por magic bytes, e
`MAX_IMAGE_BYTES` é 10 MB:

| classificação | tamanho | arquivo |
| --- | --- | --- |
| `formato_rejeitado` | 78,8 MB | `iDFace Max/iDFace-Max.tif` |
| `formato_rejeitado` | 54,7 MB | `IDBlock Facial/iDBlock-Facial-Preta.tif` |
| `formato_rejeitado` | 50,8 MB | `IDBlock Facial/iDBlock-Facial-Inox.tif` |
| `acima_do_teto` | 10,1 MB | `IDBlock Facial/iDBlock-Next-Facial.png` |

Converter para JPEG resolve formato e tamanho de uma vez, e levaria o
conjunto de imagens de 73 para 77. É **decisão do dono**, porque altera o
corpus.

### 3. O `.html` com 55 mil caracteres

`REP iDClass/api_idclass_latest.html` tem **55.519 chars de texto limpo** —
volume de um dos maiores PDFs do corpus, e é a documentação da API do REP
iDClass, material direto dos domínios Suporte e MCP B2B.
`SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}` (`app.rag.ingest:36`) não
inclui `.html`, e `ingest_directory` pula o que não reconhece com um
`continue` silencioso (`ingest.py:196`). Converter para `.md` antes de
ingerir resolve sem mexer em código.

## Consequência nos tamanhos dos conjuntos

O corpus limitou dois conjuntos da Estratégia A (ver `EVALUATION.md` Seção
0): o de **imagem caiu de 120 para 103** itens (73 de produto + 30
não-produto), porque as 90 imagens de produto que o plano pedia não existem;
e o corpus de banco passou a **29 produtos** (37 pastas menos 8 que são
software, serviço ou categoria de acessório), contra os 28 estimados antes.

## Resultado da Etapa 1 — baseline de produção (2026-10-17)

Primeira rodada do harness, sobre as 3 pastas do conjunto mínimo
(`iDFace`, `iDAccess Pro`, `REP iDClass` — 9 arquivos ingeridos, 15
perguntas) com a **configuração de produção atual**:
`paraphrase-multilingual-MiniLM-L12-v2`, 384 dims, cosine,
`chunk_size=800`, `chunk_overlap=100`.

| Métrica | Valor |
| --- | --- |
| Recall@1 | **0,250** |
| Recall@3 / @5 / @10 | **0,500** |
| nDCG@10 | **0,386** |
| MRR | **0,347** |
| Taxa de vazio (positivas) | 0,000 |
| Acerto nas negativas | **0,000** (0 de 3) |

Metade das perguntas positivas não recupera a fonte certa, e **nenhuma das
três negativas** é recusada — com `score_threshold=0,35` nada fica abaixo do
corte, nunca. O harness está validado: `q12` passou, o que prova que o `.md`
convertido do `.html` foi ingerido e é recuperável (era o canário da decisão
3).

### O achado: nenhum `score_threshold` resolve

A varredura offline (`varrer_threshold.py`) sobre a mesma rodada:

| `score_threshold` | Recall@5 | nDCG@10 | Vazio (pos.) | Acerto (neg.) |
| --- | --- | --- | --- | --- |
| 0,00 – 0,45 | 0,500 | 0,386 | 0,000 | 0,000 |
| 0,50 | 0,417 | 0,303 | 0,167 | 0,000 |
| 0,55 – 0,58 | 0,250 | 0,178 | 0,333–0,500 | 0,000 |
| 0,60 | 0,250 | 0,178 | 0,500 | 0,667 |
| 0,62 | 0,167 | 0,094 | 0,667 | **1,000** |
| 0,70 | 0,000 | 0,000 | 0,917 | 1,000 |

As distribuições de score se sobrepõem por completo:

```
menor score máximo entre as POSITIVAS : 0,4553
maior score máximo entre as NEGATIVAS : 0,6098
-> 8 das 12 positivas pontuam ABAIXO da pior negativa
```

Só se acerta todas as negativas a partir de 0,62, onde o Recall@5 já caiu
para 0,167. **Não existe corte que atenda aos dois lados** — o que significa
que isto não é um problema de calibração da Etapa 4, e sim do modelo de
embedding (Etapa 2). É evidência medida, no corpus do próprio TCC, para a
troca que o MTEB-BR já sugeria pelo ranking (93º de 93, Mean22 0,248).

`top_k` ∈ {3, 5, 10} não muda nada na tabela: depois de deduplicar por
documento, quase nenhuma pergunta devolve mais de 3 fontes distintas.

### O que este conjunto NÃO é

15 perguntas servem para **validar o harness**, não para escolher
parâmetros: a meia-largura do IC 95% em p=0,5 com n=12 é de ±27 pp. A
escolha das Etapas 2–5 usa as 180 perguntas da Estratégia A, que ainda não
existem. Os números acima valem como baseline de referência e como prova de
que o instrumento funciona de ponta a ponta.

## Resultado da Etapa 2 — comparação dos 4 candidatos no conjunto mínimo (2026-10-17)

Rodada de `run_etapa2.py` sobre o mesmo conjunto mínimo (9 arquivos, 15
perguntas), com cada modelo medido dentro da sua própria janela de tokens e
com prefixos de tarefa assimétricos aplicados em `app.rag.embeddings`:

| # | Candidato | Dims | Janela | Chunk | Recall@5 | nDCG@10 | MRR | Separável? | Pos mín | Neg máx |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `google/embeddinggemma-300m` | 768 | 2048 | 800/100 | **1,000** | 0,938 | 0,917 | **SIM** | **0,5670** | **0,4999** |
| 2 | `BAAI/bge-m3` | 1024 | 8192 | 800/100 | **1,000** | **0,969** | **0,958** | NÃO | 0,5638 | 0,6092 |
| 3 | `intfloat/multilingual-e5-large-instruct` | 1024 | 514 | 800/100 | 0,750 | 0,513 | 0,431 | NÃO | 0,8506 | 0,8730 |
| 4 | `paraphrase-multilingual-MiniLM-L12-v2` | 384 | 128 | 400/50 | 0,500 | 0,346 | 0,292 | NÃO | 0,5175 | 0,6584 |

1. **Corrigir o truncamento do `MiniLM-L12-v2` (`chunk_size=400` chars ≈ 114 tokens) não salvou o modelo:** o `Recall@5` continuou em `0,500` e as negativas continuaram pontuando acima das positivas (`0,6584` vs `0,5175`).
2. **`embeddinggemma-300m` e `bge-m3` empatam em `Recall@5 = 1,000` (12/12 positivas recuperadas)**, mas **`embeddinggemma-300m` é o único modelo separável** (`menor positiva = 0,5670 > maior negativa = 0,4999`): qualquer `score_threshold ∈ [0,50, 0,56]` entrega simultaneamente `Recall@5 = 1,000` e `acerto_negativas = 1,000` (3/3 negativas recusadas), além de ocupar metade do tamanho (308M vs 568M parâmetros, 768 vs 1024 dims).
3. Mesma ressalva metodológica da Etapa 1: os números em `n=15` validam o pipeline de ponta a ponta e antecipam o comportamento de separabilidade; a confirmação estatística pareada requer o conjunto de 180 perguntas da Estratégia A.

## Resultado da Etapa 3 — grade 5×3 de chunking em tokens (2026-10-17)

Rodada dos 15 pontos (`chunk_size` ∈ {128, 256, 512, 768, 1024} tokens ×
`overlap` ∈ {10%, 15%, 20%}) sobre `google/embeddinggemma-300m`, com
`app.rag.chunking.chunk_text` contando tokens pelo tokenizer do modelo e
cortando recursivamente (`\n\n` → `\n` → `. ` → `" "`):

| # | Ponto | `chunk_size` (tok) | `overlap` (tok / %) | Recall@5 | nDCG@10 | MRR | Separável? | Pos mín | Neg máx |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **`cs512_ov10`** | **512** | **51 (10%)** | **1,000** | **1,000** | **1,000** | **SIM** | **0,5750** | **0,5208** |
| 2–13 | `cs{256,512,768,1024}_ov{10,15,20}` | 256–1024 | 10%–20% | **1,000** | 0,969 | 0,958 | **SIM** | 0,5625–0,5860 | 0,5017–0,5454 |
| 14 | `cs128_ov15` | 128 | 19 (15%) | 1,000 | 0,938 | 0,917 | NÃO | 0,5703 | 0,5869 |
| 15 | `cs128_ov20` | 128 | 26 (20%) | 0,917 | 0,824 | 0,792 | SIM | 0,5728 | 0,5469 |

1. **`cs512_ov10` (`512` tokens, `overlap = 51` tokens) atinge `1,000` em `Recall@1`, `Recall@5`, `nDCG@10` e `MRR`** (todas as 12 positivas trazem a fonte correta no 1º lugar) mantendo separabilidade (`0,5750 > 0,5208`).
2. **Todos os 12 pontos entre 256 e 1024 tokens têm `Recall@5 = 1,000`, `nDCG@10 >= 0,969` e `separável = True`.** A única faixa que degrada (`cs128_ov15` perde separabilidade e `cs128_ov20` cai para `Recall@5 = 0,917`) é exatamente **`128` tokens** — o teto da janela do `MiniLM-L12-v2` antigo.

## Resultado da Etapa 4 — recalibração de `score_threshold` e `top_k` no conjunto mínimo (2026-10-17)

`varrer_threshold.py` foi estendido para aceitar o envelope de saída da Etapa 3
(`--entrada resultados_etapa3.json --saida varredura_threshold_etapa4.json`,
selecionando automaticamente o ponto `vencedor` ou `--ponto-id`) e calcular a
recomendação pelo ponto médio do intervalo separável (`recomendar_threshold`).

Sobre `cs512_ov10` (`google/embeddinggemma-300m`, `512` tokens, `overlap=51`):

- **Intervalo separável:** `menor_score_maximo_positivas = 0,5750` e
  `maior_score_maximo_negativas = 0,5208` → ponto médio `0,5479`.
- **Corte recomendado na grade:** `score_threshold = 0,55` com `top_k = 5`,
  entregando simultaneamente `Recall@5 = 1,000`, `nDCG@10 = 1,000`,
  `MRR = 1,000`, `taxa_vazio_positivas = 0,000` e `acerto_negativas = 1,000`.
- **Ressalva:** rodada executada sobre `dataset_minimo.json` (`n=15`); a
  calibração definitiva depende do conjunto de 180 perguntas da Estratégia A.

## Resultado da Etapa 5 — métrica de distância e payload index em `domain` (2026-10-17)

Implementado `run_etapa5.py` com duas baterias sobre `cs512_ov10`
(`google/embeddinggemma-300m`, `512` tokens, `overlap=51`):

1. **Métricas de distância (`cosine`, `dot`, `euclid`):** na primeira execução
   sobre `dataset_minimo.json` (`resultados_etapa5.json`), `cosine` e `dot`
   produziram rankings e scores idênticos (`Recall@5 = 1,000`, `nDCG@10 = 1,000`,
   `MRR = 1,000`, `pos_min = 0,5750`, `neg_max = 0,5208`). `euclid` retornou
   vazio nessa primeira rodada porque o Qdrant interpreta `score_threshold` como
   limite **superior** (`distancia <= thr`) para métricas de distância
   (`Order::SmallBetter`), então `score_threshold=0.0` descartou todos os pontos
   com distância `> 0`. O script `run_etapa5.py` foi corrigido para usar
   `thr_sem_corte = 10.0` em `euclid`/`manhattan` (não reexecutado até o fim).
2. **Payload index `keyword` em `domain` (`sem_indice` vs
   `indice_domain_keyword`):** medido em `n=75` consultas filtradas puras no
   Qdrant (`query_points` com vetores pré-calculados, isolando o Qdrant da GPU):
   - `sem_indice`: `media = 4,912 ms`, `p50 = 4,778 ms`, `p95 = 5,384 ms`.
   - `indice_domain_keyword`: `media = 4,908 ms`, `p50 = 4,738 ms`,
     `p95 = 5,960 ms`.
   No volume do conjunto mínimo (e do corpus de ~302 chunks, abaixo do
   `full_scan_threshold`), a diferença de latência é sub-milissegundo.

## Reproduzir

```bash
cd backend

# Etapa 0 — auditoria (não exige nada no ar)
.venv/bin/python eval/rag_ingestion/auditar_corpus.py

# Preparação do corpus (idempotente; --dry-run mostra o plano)
.venv/bin/python eval/rag_ingestion/preparar_corpus.py

# Etapa 1 — exige Qdrant e Postgres no ar
.venv/bin/python eval/rag_ingestion/run_etapa1.py --score-threshold 0.0 --top-k 10

# Etapa 2 — compara os 4 modelos candidatos (retomável por candidato)
.venv/bin/python eval/rag_ingestion/run_etapa2.py

# Etapa 3 — grade 5x3 de chunking em tokens (retomável por ponto)
.venv/bin/python eval/rag_ingestion/run_etapa3.py

# Etapa 4 — varredura offline, sobre o JSON da Etapa 1 ou da Etapa 3
.venv/bin/python eval/rag_ingestion/varrer_threshold.py
.venv/bin/python eval/rag_ingestion/varrer_threshold.py --entrada eval/rag_ingestion/resultados_etapa3.json --saida eval/rag_ingestion/varredura_threshold_etapa4.json

# Etapa 5 — métrica de distância e payload index em domain
.venv/bin/python eval/rag_ingestion/run_etapa5.py

# Testes (sem Qdrant/Postgres)
.venv/bin/python -m pytest tests/test_rag_ingestion_eval.py -q
```

A Etapa 1 lê `auditoria_corpus.json` para saber o que ingerir e falha se a
Etapa 0 não tiver rodado — em vez de medir silenciosamente um corpus
diferente do auditado. A Etapa 7 exigirá também `EXTERNAL_MODEL_API_KEY`.
