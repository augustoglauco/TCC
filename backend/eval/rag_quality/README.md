# Avaliação 2 — Qualidade das Respostas do RAG (R4, Fase 10)

Ver `docs/EVALUATION.md` Seção 2 para o desenho completo desta avaliação.

**Corpus:** `docs/Manuais_fornecedor/ControlId/` (decisão do dono de
2026-10-17). Os conjuntos e resultados anteriores, montados sobre outros
documentos, foram apagados; as rodadas oficiais ainda não foram executadas, e
por isso este diretório não tem `results.json`.

## Arquivos

- `dataset.json` — depois da revisão: 107 respondíveis aprovadas/corrigidas
  (todas `facil`) + 20 `sem_resposta`, **123 respondíveis novas `pendentes`**
  (reforço de 2026-10-25: 70 `media` e 44 `dificil` + 9 `facil`, escritas à mão
  a partir dos PDFs, com `origem = "reforco-2026-10-25"`) e 53 descartadas
  (13 da primeira revisão, 12 defeituosas e 28 `facil` redundantes, com
  `motivo_descarte`; ver `docs/EVALUATION.md`). Os avaliadores ignoram
  descartadas e pendentes. Aprovar as 123 em `/admin/datasets` leva o conjunto
  a 230 respondíveis (116 `facil`, 70 `media`, 44 `dificil`).
- `gerar_dataset.py` — gera o rascunho (ver abaixo).
- `run_eval.py` — reproduz o caminho real de produção para o domínio
  "suporte" (busca RAG + prompt + geração pelo modelo local), sem passar pelo
  classificador de intenção (avaliado em `eval/router_intents/`), e usa um
  LLM-as-judge (modelo externo, diferente do gerador) para notar cada
  resposta — prompt documentado em `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md`.
  Nas `sem_resposta` usa um prompt de juiz próprio (binário: `recusou` e
  `alucinou`) e um segundo sinal determinístico por marcadores de recusa.
  Tenta de novo com backoff exponencial (até 4 tentativas) quando o
  OpenRouter devolve 429.

## Comparar ingestões do mesmo conteúdo (PDF x `.md`)

A comparação de fonte (`fonte_correta` e as métricas de `eval/rag_ingestion/`)
ignora a extensão (`.pdf`, `.md`, `.txt`) e maiúsculas: um documento tratado e
ingerido como `idtouch-manual.md` acerta o gabarito `idtouch-manual.pdf`. Os
nomes só precisam coincidir até a extensão; se o tratamento renomear ou fundir
arquivos, mapeie os novos nomes em `documentos_aceitos`. Rode as duas coleções
com as mesmas perguntas (`--collection <nome>`) e compare com McNemar/Wilcoxon
pareados, como na Etapa 7.

## Reproduzir

```bash
cd backend
.venv/bin/python eval/rag_quality/run_eval.py
```

Exige Ollama, Qdrant e Postgres reais no ar (collection de texto ativa,
populada com o corpus) e `EXTERNAL_MODEL_API_KEY` no `.env` (LLM-as-judge via
OpenRouter). A comparação de fonte usa `arquivo_origem` (caminho relativo),
porque o basename repete no corpus.

## Gerar o rascunho das 180 perguntas (`gerar_dataset.py`, 2026-10-17)

O rascunho sai daqui: 180 perguntas geradas (160 respondíveis + 20 sem
resposta no corpus). Depois da revisão do dono (2026-10-24) restam **167
válidas: 147 com resposta + 20 sem resposta** (13 descartadas, 4 corrigidas).

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
revisão humana em `/admin/datasets` (feita). As 20 sem
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
