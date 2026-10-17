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

`chunk_size_search.py` (em `rag_quality/`, 2026-10-01) acopla recuperação e
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
- `metricas.py` — as métricas como funções **puras**, testadas em
  `backend/tests/test_rag_ingestion_eval.py` sem nenhuma infraestrutura.
- `varrer_threshold.py` — **Etapa 4**. Varre `score_threshold` × `top_k`
  **offline**, sobre o JSON da Etapa 1, sem reingerir nem consultar o
  Qdrant. Exige que a rodada-base tenha usado `--score-threshold 0.0`, e
  recusa rodar sobre uma base já cortada.
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

## Reproduzir

```bash
cd backend

# Etapa 0 — auditoria (não exige nada no ar)
.venv/bin/python eval/rag_ingestion/auditar_corpus.py

# Preparação do corpus (idempotente; --dry-run mostra o plano)
.venv/bin/python eval/rag_ingestion/preparar_corpus.py

# Etapa 1 — exige Qdrant e Postgres no ar
.venv/bin/python eval/rag_ingestion/run_etapa1.py --score-threshold 0.0 --top-k 10

# Etapa 4 — varredura offline, sobre o JSON da Etapa 1
.venv/bin/python eval/rag_ingestion/varrer_threshold.py

# Testes (sem Qdrant/Postgres)
.venv/bin/python -m pytest tests/test_rag_ingestion_eval.py -q
```

A Etapa 1 lê `auditoria_corpus.json` para saber o que ingerir e falha se a
Etapa 0 não tiver rodado — em vez de medir silenciosamente um corpus
diferente do auditado. A Etapa 7 exigirá também `EXTERNAL_MODEL_API_KEY`.
