# Manual Didático: como o agente prevê a necessidade de reposição

Este manual explica, sem pressupor conhecimento prévio de IA, **como o sistema
decide que um produto está perto de acabar** e avisa o administrador. Existem
dois "cérebros" intercambiáveis — o **determinístico** (uma conta) e o **de IA**
(um modelo de linguagem). Os dois partem dos mesmos dados e publicam o aviso do
mesmo jeito; o que muda é *como a decisão é tomada*.

Decisão de arquitetura e limitações formais: `docs/ARCHITECTURE.md` (R13).
Código: `backend/src/app/agents/`.

---

## 1. A pergunta que o agente responde

> "Do jeito que este produto está saindo, o estoque dura mais ou menos tempo do
> que eu levo para repor?"

Se dura **menos**, é hora de avisar. Tudo o mais é detalhe de como estimar "do
jeito que está saindo" e "quanto tempo eu levo para repor".

## 2. Quando ele roda

A cada **venda ou reserva** (chat, API de pedidos ou MCP B2B de parceiros). Logo
depois que o pedido é gravado, o agente olha só os produtos daquele pedido. Ele
nunca atrapalha a reserva: se falhar, o erro é registrado e a reserva segue.

```
cliente reserva 5 unidades ──► pedido gravado ──► agente avalia o produto
                                                        │
                       ┌────────── precisa avisar? ─────┴─────────┐
                       ▼ sim                                      ▼ não
        mensagem em /admin/mensagens                          nada acontece
        + e-mail ao administrador (se SMTP configurado)
```

## 3. Os três números que importam

| Número | De onde vem | Para que serve |
| --- | --- | --- |
| **Estoque atual** | Soma das unidades em todos os centros de distribuição | O que ainda temos |
| **Ritmo de saída** | Unidades reservadas/vendidas nos últimos **30 dias** ÷ 30 | Quantas unidades saem por dia, em média |
| **Horizonte** | Campo "Alertar estoque com (dias)" do produto; vazio = **10** | Prazo de reposição/entrega: abaixo disso, avisar |

O horizonte é por produto porque cada item tem um prazo de reposição diferente:
um item que o fornecedor entrega em 3 dias aguenta chegar mais perto de zero do
que um que demora 30.

## 4. Cérebro determinístico (uma conta)

"Determinístico" quer dizer: **mesmos dados, sempre o mesmo resultado**. Não há
aprendizado nem aleatoriedade.

```
ritmo       = unidades vendidas em 30 dias ÷ 30
cobertura   = estoque atual ÷ ritmo        (em dias)

se cobertura < horizonte  →  avisa
```

**Exemplo.** Um gerador tem 5 unidades em estoque e saíram 30 nos últimos 30 dias.

- ritmo = 30 ÷ 30 = **1 unidade/dia**
- cobertura = 5 ÷ 1 = **5 dias**
- horizonte = 10 dias → 5 < 10 → **avisa**

Gravidade: cobertura de **3 dias ou menos** vira "crítico"; acima disso, "aviso".

**Cuidados embutidos:**

- Se o produto **não vendeu nada** nos 30 dias, não há ritmo para projetar — o
  agente não avisa (e, no modo IA, nem gasta uma chamada de modelo).
- Para não encher a caixa de entrada, avisa **no máximo uma vez por produto a
  cada 24 horas**.

**Ponto forte:** previsível, instantâneo, gratuito e fácil de auditar.
**Ponto fraco:** só enxerga a *média*. Não percebe que as vendas aceleraram na
última semana, nem que um pico isolado distorceu o ritmo.

## 5. Cérebro de IA (um modelo de linguagem)

Aqui um **LLM** (o mesmo tipo de modelo do chat — local via Ollama ou externo via
OpenRouter, à sua escolha) faz o papel de um analista de estoque.

### 5.1 O que o modelo recebe

Só **fatos estruturados** tirados do banco — nenhum texto digitado por usuário, o
que elimina o risco de alguém "enganar" o agente por escrito:

- nome, categoria e preço do produto;
- estoque total e por centro de distribuição;
- unidades vendidas nos 30 dias e a **série dia a dia** (do mais antigo ao mais
  recente);
- a cobertura calculada pela regra determinística, como referência;
- o horizonte do produto.

### 5.2 O que ele devolve

Um JSON com o veredito:

```json
{
  "risco": "alto",
  "dias_ate_falta": 2,
  "reposicao_sugerida": 40,
  "alertar": true,
  "justificativa": "A baixa acelerou nos últimos 5 dias, bem acima da média."
}
```

- `risco`: baixo, médio ou alto;
- `dias_ate_falta`: estimativa em dias;
- `reposicao_sugerida`: quantas unidades repor;
- `alertar`: se vale incomodar o administrador;
- `justificativa`: o raciocínio, em português, que vai no aviso.

Avisa quando `alertar` é verdadeiro **e** o risco não é "baixo". Risco "alto" vira
severidade "crítico".

### 5.3 O que a IA enxerga e a conta não

O mesmo gerador (5 unidades em estoque, 30 vendidas em 30 dias), mas agora a série diária mostra que **20 das
30 unidades saíram nos últimos 5 dias**:

| | Determinístico | IA |
| --- | --- | --- |
| Ritmo considerado | 1 un./dia (média de 30 dias) | ~4 un./dia (tendência recente) |
| Cobertura | 5 dias | ~1 dia |
| Reposição sugerida | — | sim, com quantidade |
| Explicação | número | texto: "a demanda acelerou" |

A IA pode também **descartar um falso alarme**: um pico isolado de um grande
pedido B2B pode fazer a média assustar, e o modelo, vendo a série, concluir
`"alertar": false`.

### 5.4 Quando a IA falha

Modelo fora do ar, demora excessiva ou resposta que não é um JSON válido: o agente
**volta automaticamente para a conta determinística**. Nenhum aviso se perde.

### 5.5 Detalhes de operação

- Roda em **segundo plano**, com sessão própria: o LLM leva segundos e o cliente
  que fez a reserva não espera.
- Cada chamada entra no **ledger de uso de IA** (origem `admin`, operação
  `agente_estoque_ia`), então tokens e custo aparecem em "Métricas & Custos IA".
- O prompt está catalogado em `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md` (item 17).

## 6. Como escolher qual usar

Em **configurações de execução → Agente de Previsão de Estoque**:

| Modo | Quando usar |
| --- | --- |
| **Determinístico** (padrão) | Produção barata e previsível; auditoria; sem GPU/API |
| **IA** | Aprender, testar, ou quando a demanda tem tendência/picos que a média esconde |
| **Desativado** | Pausar os avisos sem apagar nada |

No modo IA, escolha também o modelo: **local** (sem custo de API, usa a GPU) ou
**externo** (OpenRouter, com custo por token). A configuração é persistente e
vale a partir do próximo pedido, sem reiniciar.

## 7. Como ver e comparar

- Os avisos aparecem em **/admin/mensagens**, com a etiqueta de qual agente
  decidiu (`estoque_preditivo` = conta, `estoque_ia` = modelo) e o status do
  e-mail.
- Para comparar os dois: rode a mesma sequência de reservas em cada modo e
  confronte `dias_ate_falta`/cobertura, reposição sugerida, custo e latência.
  Essa comparação sistemática é candidata à avaliação experimental
  (`docs/EVALUATION.md`).

## 8. Limitações (assumidas no MVP)

- O ritmo é uma **média móvel simples**: sem sazonalidade (fim de ano,
  campanhas) nem previsão estatística de séries temporais.
- O estoque é **somado entre centros**: um centro zerado com outro cheio não
  dispara aviso por si só (a IA recebe a divisão por centro, a conta não).
- O horizonte é o prazo de reposição **informado por você**; o sistema não o
  mede sozinho.
- Não há reposição automática nem ordem de compra: o agente só **avisa**.
- Uma chamada de LLM por produto avaliado, sem cache.

## 9. Glossário rápido

- **Cobertura:** por quantos dias o estoque atual dura no ritmo atual.
- **Horizonte:** limite de cobertura abaixo do qual se avisa (prazo de reposição).
- **Determinístico:** mesma entrada, mesma saída, sempre.
- **LLM:** modelo de linguagem; aqui usado para *julgar* a partir de dados, não
  para conversar.
- **Fallback:** plano B automático (a conta, quando a IA falha).
