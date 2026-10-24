# Eval: Resiliência a Prompt Injection

Avaliação comportamental (Fase 10) de quanto o pipeline real resiste a
tentativas de prompt injection diretas e indiretas (via RAG), depois do
isolamento por delimitador implementado na Task 2 de
`docs/superpowers/plans/2026-10-07-seguranca-prompt-injection-mcp.md`.

## Rodar

A partir de `backend/`, com Ollama no ar e `EXTERNAL_MODEL_API_KEY`
configurada no `.env`:

    .venv/bin/python eval/prompt_injection/run_eval.py

Salva `results.json` com, por cliente (local/externo): taxa de resistência
(proporção de casos em que o modelo NÃO obedeceu à instrução injetada,
segundo o LLM-as-judge) e o detalhe de cada caso.

## Resultado

O conjunto atual (95 casos válidos: 45 diretos + 50 indiretos, sobre o corpus
ControlId) **ainda não foi rodado**; roda na rodada completa, nos 4
sobreviventes da triagem (`docs/EVALUATION.md`). O `results.json` de um piloto
anterior de 8 casos foi apagado em 2026-10-24: o conjunto mudou e os números
não eram comparáveis.

## Conjunto novo de 100 casos (`gerar_dataset.py`, 2026-10-17/18)

Os 8 casos originais foram **invalidados** junto com os outros conjuntos
(montados sobre outro corpus, `docs/EVALUATION.md` Seção 0). O conjunto válido
tem **50 diretas + 50 indiretas**.

```bash
cd backend
.venv/bin/python eval/prompt_injection/gerar_dataset.py --dry-run
.venv/bin/python eval/prompt_injection/gerar_dataset.py
```

Exige só `EXTERNAL_MODEL_API_KEY` (tier `:free`).

### Duas decisões de desenho

**1. As indiretas envenenam texto real do corpus.** A instrução maliciosa é
enxertada no meio de um trecho extraído por `app.rag.pdf_extract` — o mesmo
extrator da ingestão — de um PDF que o sistema de fato indexa. Um documento
inventado ("Manual da Impressora X200", como no conjunto antigo) testa um
cenário que não existe: na prática o atacante envenena um manual plausível, e o
texto técnico ao redor da instrução é parte do ataque. A instrução vai no
**meio** do trecho, não no fim, onde ficaria trivialmente visível como apêndice.

**2. O `criterio_falha` é de template, não do LLM.** É o texto que o juiz usa
para decidir se o ataque funcionou. Deixá-lo a cargo do modelo que inventa o
ataque produziria critério vago ("a resposta parece insegura") e julgamento
inconsistente entre casos. Cada critério descreve **comportamento observável**
na resposta, não intenção.

O LLM entra só na redação das 50 diretas, onde variedade de linguagem importa
(ordem direta, pedido educado, falsa autoridade, urgência, jogo de
interpretação, instrução escondida em formatação).

### Os dez tipos de ataque direto

| `ataque` | O que o atacante quer |
| --- | --- |
| `extrair_prompt` | o prompt de sistema, palavra por palavra |
| `trocar_persona` | persona sem restrições (tipo DAN) |
| `preco_falso` | confirmação de preço absurdo (R$ 1,00) |
| `desconto_nao_autorizado` | desconto que o assistente não pode dar |
| `dados_de_outro_cliente` | pedido/cadastro de terceiro |
| `abusar_ferramenta_b2b` | usar ferramenta transacional do canal B2B |
| `ignorar_escopo` | tarefa alheia atendida como se fosse função |
| `agendar_sem_dados` | visita confirmada sem os dados obrigatórios |
| `instrucao_disfarcada` | instrução escondida em markdown/código/base64 |
| `escalonar_falso` | afirmar ser humano ou ter aberto ticket inexistente |

### Os dez payloads indiretos

`desconto_90`, `revelar_prompt`, `exfiltrar_dados`, `redirecionar_url`,
`desativar_seguranca`, `estoque_falso`, `ferramenta_b2b`, `persona_nova`,
`ticket_inventado`, `idioma_credencial` — rotacionados pelos 50 documentos do
corpus com mais texto, um payload por documento.

A mensagem do cliente nas indiretas é **inocente de propósito** ("pode me
ajudar com o manual do iDFace?"): o ataque está no documento e o cliente não
sabe disso. É o que separa injeção indireta de um cliente mal-intencionado.

### Revisão

Completa (~1,5 h das 4,5 h da Estratégia A). Diferente dos outros conjuntos,
aqui não há atalho: o `criterio_falha` é julgamento de segurança e não se
automatiza.
