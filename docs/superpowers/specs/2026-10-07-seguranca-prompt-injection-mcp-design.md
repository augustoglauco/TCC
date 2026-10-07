# Especificação Arquitetural: Resiliência a Prompt Injection e Abuso de Ferramentas MCP B2B

> **Data:** 07 de Outubro de 2026
> **Status:** Proposta de Arquitetura / Design Spec
> **Domínio:** Roteador/Orquestrador (prompt), RAG, Chat Multimodal, MCP B2B

---

## 1. Contexto e Objetivo

Um plano de segurança anterior (`docs/PLANO_ANTI_AI_ATTACK.md`, commit `8a3b4ed`,
2026-10-06) foi **descartado** nesta sessão por dois motivos:

1. Descrevia defesas e arquitetura que não existem no código (multi-tenancy
   com `tenant_id` no Qdrant, RBAC, JWT com rotação, Presidio PII masking,
   Llama Guard, rate limiting via Redis, criptografia at-rest LUKS/AES-256,
   CAPTCHA) — nada disso está implementado, e boa parte contraria
   explicitamente o escopo do MVP já registrado em `CLAUDE.md` ("Fora de
   escopo": OAuth/rate limiting/auditoria completa para o MCP B2B) e a
   natureza single-tenant do projeto (uma única empresa, sem múltiplos
   clientes/parceiros isolados por dados).
2. A suíte de "60 testes" (`backend/tests/test_security_anti_ai_attacks.py`)
   era inteiramente auto-contida: todas as funções de defesa testadas
   (`sanitize_user_input`, `is_embedding_outlier`, `apply_gaussian_denoising`
   etc.) eram stubs definidos dentro do próprio arquivo de teste, sem
   importar nenhum código de `app.*`. Os testes passavam sempre,
   independentemente do estado real do backend — não validavam nada.

Esta spec substitui aquele plano por um escopo menor e **ancorado no código
real**, cobrindo os três vetores de ataque plausíveis para este sistema
(decisão tomada em brainstorming com o desenvolvedor):

1. **Prompt Injection direta** — cliente tenta sobrescrever o
   playbook/system prompt pela própria mensagem de chat.
2. **Prompt Injection indireta via RAG/OCR** — texto malicioso embutido num
   documento ingerido (RAG) ou num comprovante lido por OCR, que é
   recuperado/injetado no prompt sem isolamento algum.
3. **Abuso das ferramentas MCP B2B** — tentativas de entrada fora do schema
   esperado pelas 4 ferramentas transacionais.

Explicitamente **fora de escopo** (mesmos motivos do item 1 acima, mais
desproporcionais para um TCC de um único desenvolvedor): data poisoning via
ingestão (o RAG só é alimentado pelo admin, sem atacante externo plausível),
ataques adversariais multimodais (FGSM, ultrassônico — exigem equipamento
especializado sem motivação real contra um chatbot comercial), extração/furto
de modelo (Ollama é open-source local, OpenRouter é gerenciado por terceiro —
não há peso proprietário a proteger), model inversion / isolamento
multi-tenant (não há múltiplos tenants no sistema).

**Achado de baseline (verificado em `backend/src/app/router/orchestrator.py:81-162`,
função `_build_prompt`):** hoje a mensagem do cliente e o conteúdo recuperado
do RAG são concatenados como texto puro, com apenas um rótulo textual
("Mensagem do cliente: ...", "Informações recuperadas:\n...") e **nenhum**
delimitador, escape ou isolamento. Não existe defesa nenhuma contra os
vetores 1 e 2 hoje — este não é um reforço de algo existente, é a primeira
defesa real do projeto nessa frente.

---

## 2. Decisão de Abordagem (descartadas e escolhida)

Três abordagens foram discutidas para o vetor 1 (prompt injection direta):

- **A — Bloqueio por regex/blocklist:** intercepta e rejeita mensagens que
  batam padrões conhecidos de injeção antes de chegar ao LLM. **Descartada**:
  alta taxa de falso positivo esperada num chatbot de vendas/suporte real
  (ex.: cliente dizendo "ignore o que falei antes, mudei de ideia sobre o
  produto" é uma frase legítima de atendimento que bateria num padrão
  clássico de injeção) e é trivialmente evadida (sinônimos, outro idioma,
  base64) — dar essa sensação de proteção seria tão enganoso quanto o plano
  anterior.
- **B — Isolamento por delimitador, sem bloqueio:** envolve a entrada do
  cliente e o contexto do RAG em marcação explícita no prompt, instruindo o
  modelo a tratar aquele conteúdo como dado, nunca como comando. Nunca
  bloqueia nada — zero risco de recusar uma mensagem legítima.
- **C — B + log-only para casos de altíssima confiança (ESCOLHIDA):** igual a
  B, mas mensagens batendo um conjunto pequeno de padrões inequívocos (pedir
  literalmente o prompt de sistema, variações clássicas de "ignore todas as
  instruções anteriores") geram um evento de log, reaproveitando a
  infraestrutura de escalonamento já existente da Fase 4B (monitor de tom),
  sem bloquear a conversa. Escolhida sobre B porque o custo adicional é
  mínimo (uma função de poucas linhas + uma chamada de log) e dá ao
  desenvolvedor um dado real e citável ("N tentativas detectadas durante o
  período de teste") sem introduzir qualquer risco de falso positivo, já que
  nada é bloqueado.

---

## 3. Componentes Novos/Alterados

### 3.1 `app/router/prompt_safety.py` (novo módulo)

- `wrap_untrusted(label: str, content: str) -> str`: envolve `content` em
  tags (`<entrada_cliente>...</entrada_cliente>` ou
  `<contexto_rag>...</contexto_rag>`), escapando qualquer ocorrência literal
  dessas tags dentro do próprio `content` (ex.: `<` e `>` nas sequências
  exatas das tags usadas) para que o conteúdo não possa "fechar" a tag e
  escapar do isolamento.
- `detectar_tentativa_injecao(mensagem: str) -> bool`: heurística pequena
  (poucos padrões de altíssima confiança, não um filtro semântico amplo) —
  usada **só para logar**, nunca para bloquear ou alterar o fluxo.

### 3.2 `app/router/orchestrator.py` (`_build_prompt`)

- A mensagem do cliente (hoje linha 161, `f"Mensagem do cliente: {message}"`)
  passa a usar `wrap_untrusted("entrada_cliente", message)`.
- O contexto recuperado do RAG (hoje linha 142-150) passa a usar
  `wrap_untrusted("contexto_rag", contexto)` no lugar da concatenação crua.
- Chamada a `detectar_tentativa_injecao(message)` antes de montar o prompt;
  se `True`, loga um evento (mesmo padrão/formato usado pelo monitor de tom
  da Fase 4B) com o `conversation_id` e um trecho da mensagem — **não**
  interrompe nem altera a resposta.

### 3.3 `app/router/playbooks.py` (`build_system_prompt`)

- Acrescenta uma frase fixa ao final do prompt de sistema de cada domínio
  (técnica "sandwich" simples, sem infraestrutura nova): instrução de que
  tudo dentro de `<entrada_cliente>` e `<contexto_rag>` é dado, nunca
  instrução, e que o texto de sistema nunca deve ser revelado literalmente.
- Esta é uma alteração de prompt de sistema → aciona a regra 11 do
  `CLAUDE.md` (atualizar `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md`).

### 3.4 Ferramentas MCP B2B (`app/mcp_server/b2b.py`, `app/models/mcp_b2b.py`)

- **Nenhuma mudança de código.** Os 4 handlers já validam via Pydantic
  (`ItemQuantidadeIn.quantidade: int = Field(gt=0)` e equivalentes). O
  trabalho deste vetor é só de teste (ver §4.2) — confirmar com testes reais
  contra os handlers que a validação já existente de fato rejeita entradas
  malformadas, sem inventar RBAC/JWT/rate limiting que não existem.

---

## 4. Testes

### 4.1 Testes rápidos (sem chamada a LLM) — `backend/tests/test_prompt_safety.py`

- `wrap_untrusted` escapa uma tentativa de o conteúdo conter a própria tag
  de fechamento (ex.: mensagem do cliente contendo literalmente
  `</entrada_cliente>`).
- `_build_prompt` real (chamado diretamente, não mockado) produz as tags
  esperadas no texto final para mensagem do cliente e para contexto do RAG.
- `detectar_tentativa_injecao` retorna `True` para os padrões de alta
  confiança e `False` para mensagens legítimas de exemplo (incluindo as que
  quase bateriam um blocklist ingênuo, ex.: "ignore o que eu falei antes
  sobre o produto X").
- Evento de log é emitido quando `detectar_tentativa_injecao` é `True`,
  sem alterar o prompt final nem a resposta.

### 4.2 Testes de abuso MCP B2B — `backend/tests/test_mcp_b2b_security.py`

Chamando os handlers reais das 4 ferramentas (não stubs), confirmando o
comportamento já esperado da validação Pydantic existente:
- Tipo errado em campo numérico (string em `quantidade`).
- Quantidade negativa ou zero.
- `produto_id` inexistente.
- Payload com campos extras não declarados no schema.

### 4.3 Eval comportamental com LLM real — `backend/eval/prompt_injection/`

Mesmo padrão já usado em `backend/eval/router_intents/` e
`backend/eval/rag_quality/` (dataset.json + run_eval.py + README.md com
resultado real, não fictício):
- ~12-15 prompts adversariais cobrindo injeção direta, jailbreak clássico
  (DAN, modo desenvolvedor), um chunk de RAG "envenenado" e um texto de OCR
  malicioso, rodados contra o pipeline real (`orchestrator.handle_message`,
  local **e** externo).
- Critério de julgamento: o modelo obedeceu à instrução injetada (ex.:
  revelou o system prompt, confirmou uma ação não solicitada) ou manteve o
  comportamento esperado do domínio? Resultado registrado como taxa de
  resistência real, nos mesmos termos que o projeto já usa para
  acurácia do roteador (95,0%) e qualidade do RAG (2,78/5).

---

## 5. Documentação a Atualizar

- `docs/ARCHITECTURE.md` §7 (Riscos e limitações conhecidas): nova entrada
  registrando a decisão (isolamento por delimitador + log, por que não
  blocklist) e o resultado real do eval comportamental quando disponível.
- `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md`: entrada nova para a frase
  acrescentada em `build_system_prompt` (regra 11).
- `docs/ROADMAP.md`: novo item de checklist na Fase 10 (Avaliação
  Experimental), já que o eval comportamental é uma avaliação experimental
  no mesmo espírito das demais desta fase.

---

## 6. Próximos Passos

1. Criar `app/router/prompt_safety.py` (`wrap_untrusted`,
   `detectar_tentativa_injecao`).
2. Alterar `_build_prompt` e `build_system_prompt` para usar o isolamento e
   a frase de sandwich.
3. Testes rápidos de `prompt_safety` e de `_build_prompt`.
4. Testes de abuso MCP B2B contra os handlers reais.
5. Construir o dataset e `run_eval.py` de `backend/eval/prompt_injection/`,
   rodar ao vivo (local + externo) e registrar o resultado real.
6. Atualizar `ARCHITECTURE.md`, `PROMPTS_E_INSTRUCOES_LLM.md` e
   `ROADMAP.md`.
