# Avaliação 2 — Qualidade das Respostas do RAG (R4, Fase 10)

> **Conjunto invalidado em 2026-10-17.** O dono definiu
> `docs/Manuais_fornecedor/ControlId/` como o corpus da avaliação, e todo
> gabarito passa a sair dele. As 18 perguntas de `dataset.json` e a bateria
> de `bateria_perguntas_rag.md` foram montadas sobre outros documentos
> (`docs/Manuais_fornecedor/` em geral, incluindo material Intelbras), então
> **os resultados abaixo não descrevem mais o sistema avaliado** — valem como
> histórico do instrumento de medição e das lições sobre ele (fonte correta ×
> nota, rate limit do juiz, nome de arquivo com espaço duplo). O conjunto
> novo (180 perguntas, ponderadas por volume de texto) está dimensionado em
> `docs/EVALUATION.md` Seção 0; a escolha de parâmetros de ingestão migrou
> para `eval/rag_ingestion/`.

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

## Experimento complementar: busca por bisseção do `chunk_size`

A pedido explícito do desenvolvedor, depois de ver a nota baixa acima:
`chunk_size_search.py` testa outros valores de `chunk_size` (mantendo
`chunk_overlap` em 12,5% dele, mesma proporção do baseline) por bisseção —
começa nos extremos de uma sequência comum de duplicação (200/1600
caracteres), compara contra o baseline de produção (800, já medido acima,
não remedido) e segue dividindo o range pela metade que melhorou. Cada
candidato cria uma collection **temporária** (só com os 11 PDFs reais do
domínio Suporte, já que a busca filtra por `domain="suporte"`), mede, e
**sempre apaga a collection ao final** — nunca toca na collection de
produção. Ver docstring de `chunk_size_search.py` para o porquê de bisseção
em vez de grade completa (custo).

### Resultado (2026-10-01, 7 pontos medidos em 5 rodadas)

| `chunk_size` | `chunk_overlap` | Nota média | Fonte correta |
| --- | --- | --- | --- |
| 200 | 25 | 2,94 | 72% |
| 287 | 36 | 3,28 | 78% |
| **375** | **47** | **3,61** | 72% |
| 550 | 69 | 2,94 | 83% |
| **800 (produção)** | **100** | **2,78** | 78% |
| 900 | 112 | 2,56 | 61% |
| 1600 | 200 | 2,72 | 83% |

**Melhor ponto encontrado: `chunk_size=375`** (nota 3,61, +0,83 sobre os
800 atuais — ~30% de melhora relativa).

### Ressalva importante: o "vencedor" não tem a melhor recuperação

O ponto 375 tem a MELHOR nota, mas sua taxa de fonte correta (72%) é PIOR
que a de 800 (78%), 550 (83%) e 1600 (83%). Ou seja, o ganho de qualidade
em 375 não vem de recuperar melhor — vem de o modelo gerar uma resposta
melhor a partir de um contexto mais enxuto, mesmo quando a fonte
"oficialmente esperada" não é a recuperada (nota do LLM-judge mede
qualidade da resposta, não fidelidade estrita à fonte do gabarito). A
trajetória também não é monótona (800→900 cai, 900→550 sobe de novo) — com
18 perguntas e uma única rodada por ponto (nota de LLM-judge com ruído),
isso é esperado; o resultado aponta uma **região razoável** (algo entre 300
e 550), não um ótimo matematicamente provado. Repetir cada ponto algumas
vezes e tirar a média reduziria esse ruído, a um custo de tempo/API
proporcional — não feito aqui por escopo (ver `docs/EVALUATION.md`, que
pede "relatório curto", não uma busca de hiperparâmetros exaustiva).

### Reproduzir

```bash
cd backend
.venv/bin/python eval/rag_quality/chunk_size_search.py
```

Mesmos pré-requisitos do `run_eval.py` acima. Demora mais (ingestão real de
11 PDFs + 18 perguntas por candidato, várias rodadas).

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

## Gerar o rascunho das 180 perguntas (`gerar_dataset.py`, 2026-10-17)

O conjunto de 18 perguntas descrito acima foi **invalidado** (montado sobre
outros documentos, não sobre o corpus `docs/Manuais_fornecedor/ControlId/` —
ver `docs/EVALUATION.md` Seção 0). O conjunto válido são 180 perguntas: 160
respondíveis + 20 sem resposta no corpus. O rascunho sai daqui:

```bash
cd backend
.venv/bin/python eval/rag_quality/gerar_dataset.py                 # 160 + 20
.venv/bin/python eval/rag_quality/gerar_dataset.py --limite-docs 2 --total 3 --sem-resposta 2
```

Exige só `EXTERNAL_MODEL_API_KEY` — nada de Qdrant, Postgres ou Ollama no ar.
É retomável por documento e grava o arquivo a cada documento, porque no tier
`:free` uma rodada interrompida custa relógio (pausa de 3 s entre chamadas e
backoff base de 8 s a cada 429). Pela tela: tarefa "Gerar rascunho: 180
perguntas de RAG" em `/admin/datasets`.

Três decisões que valem registro:

1. **O texto vem de `app.rag.pdf_extract`, o mesmo extrator da ingestão.** Um
   extrator diferente aqui geraria perguntas que dependem de texto que o RAG
   nunca indexou, e o sistema erraria por um motivo que não é o que se quer
   medir.
2. **Os documentos elegíveis são os 86 `util` de `auditoria_corpus.json`.**
   Isso exclui os 11 degenerados e, com eles, os 8 PDFs de imagem pura que
   ficaram com 0 chunks na ingestão — perguntar sobre documento invisível à
   busca contaminaria a medida de alucinação, que precisa vir só das 20
   deliberadas.
3. **`trecho_origem` é conferido contra o texto do PDF.** Quando o modelo
   parafraseia em vez de copiar, o caso fica com `trecho_confere: false` em
   vez de ser descartado em silêncio: o campo existe para a revisão ser
   leitura lado a lado, e um trecho reescrito faria o revisor comparar a
   pergunta com um texto que não é o do documento.

Todo item nasce `revisao.status = "pendente"`: o gabarito só vale depois da
revisão humana em `/admin/datasets` (~2 h para este conjunto). As 20 sem
resposta são as que mais precisam de conferência — o modelo pode propor um
tema que, na verdade, está no corpus.

### O que a 1ª rodada completa ensinou (2026-10-17, descartada)

A primeira rodada produziu 182 casos e foi jogada fora depois da medição:
**90 das 162 perguntas respondíveis (56%) não diziam de qual produto
falavam**. Num acervo de 37 linhas de produto, "qual a capacidade máxima de
usuários que podem ser cadastrados?" — que apareceu em três documentos
diferentes — não tem resposta única: o assistente recebe a pergunta sem
contexto nenhum e a pontuação de fonte reprovaria duas das três por
construção. A causa era a própria regra do prompt (`Não cite o nome do
arquivo na pergunta`), que o modelo generalizou para omitir também o produto.
O prompt passou a exigir o produto no enunciado e a proibir pergunta sobre o
documento (data de revisão, página, versão do PDF).

Dois efeitos colaterais daquela rodada viraram campo no conjunto:

- **`arquivo_origem` e `origem_ambigua`.** `changelog_pt-br.pdf` existe em
  `iDAccess Pro/` e em `iDFace/`, e os dois estão em `rag_documents` com o
  mesmo `filename` (42 e 56 chunks). Como `run_eval._fonte_e_correta`
  compara pelo nome do arquivo, um acerto na fonte errada contaria como
  acerto. `documento_origem` continua sendo o nome (é o que o RAG guarda),
  mas `arquivo_origem` guarda o caminho relativo, que é inequívoco. A
  retomada do gerador também passou a ser por caminho: antes, dois arquivos
  de mesmo nome eram tratados como um só.
- **`duplicada_de`.** Aponta para o primeiro caso com a mesma pergunta. Numa
  fila que mostra um item por vez, a repetição passaria batida.

A dificuldade saiu sem estratificação: 152 `facil`, 10 `media`, 0 `dificil` na
1ª rodada e **160 `facil`** na 2ª, depois que o prompt passou a pedir honestidade
no rótulo. Isso é limite do modelo free de 2.6B, não do instrumento. **O campo
`dificuldade` não serve para quebrar o resultado por estrato** — o relatório não
deve prometer essa análise, a menos que o revisor re-rotule à mão durante a
revisão (a tela permite, é um campo editável como os outros).

**Pendência conhecida:** `run_eval.py` ainda não sabe pontuar os casos
`sem_resposta`. Ele compara a fonte recuperada com `documento_origem` (vazio
nesses casos) e manda a resposta ao juiz como se houvesse gabarito factual.
Enquanto estiver assim, as 20 perguntas de alucinação não medem nada.
