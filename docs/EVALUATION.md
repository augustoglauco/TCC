# Avaliação Experimental do Protótipo

Este documento detalha, em termos operacionais, as três avaliações
experimentais descritas em `docs/ARCHITECTURE.md` (Seção 9). O objetivo é
sair de uma entrega apenas funcional para uma análise estruturada dos
resultados — item explicitamente pedido pelo orientador como parte dos
critérios de aprovação do TCC.

Scripts e artefatos de cada avaliação devem viver em `eval/`, um
subdiretório por frente (ver `docs/CONVENTIONS.md`), com resultados salvos
como JSON ou CSV versionados (dados pequenos) para permitir comparação entre
execuções.

## 1. Acerto do roteador na identificação de intenções

**O que mede:** proporção de mensagens de teste roteadas para a intenção
correta, entre os quatro domínios (Vendas, Suporte Técnico, Atendimento ao
Usuário, Agendamento de Visita).

**Como montar o conjunto de teste (`eval/router_intents/`):**
- 30–50 mensagens rotuladas manualmente, cobrindo os quatro domínios de
  forma equilibrada.
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
- Com o provedor alternativo TypeSafe Jev (`intent_router_provider`, ver
  `docs/ARCHITECTURE.md` §5), rodar o mesmo conjunto de teste uma vez por
  provedor (`heuristica_llm` e `jev_openrouter`) e comparar acurácia,
  latência e custo entre os dois — essa comparação é o motivo direto da
  existência do provedor alternativo. Usar `ClassificationResult.provider_efetivo`
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
- 15–20 perguntas sobre o catálogo/documentação com resposta esperada
  conhecida (ground truth definido manualmente).
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

## Consolidação

Ao final das três avaliações, gerar um resumo curto (pode ser um novo
arquivo `eval/RESUMO.md` ou uma seção no relatório final do TCC) com:
- Acurácia do roteador + principais padrões de erro da matriz de confusão.
- Nota média de qualidade do RAG (manual e LLM-as-judge) + taxa de
  recuperação correta.
- Latência média/p95 local x externo + recomendação de uso (quando preferir
  cada um).

Esse resumo é o insumo direto para a Seção 9 do documento de proposta
(`Documento_Projeto_Assistente_Multimodal_com_avaliacao.docx`) e para a
apresentação final ao orientador.
