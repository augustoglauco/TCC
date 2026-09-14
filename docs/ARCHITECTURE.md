# Arquitetura — Assistente Virtual Multimodal com Roteador Inteligente

> Fonte: adaptado do documento de proposta ao orientador (TCC). Este documento
> é a referência técnica única de arquitetura e escopo — mantenha-o
> atualizado conforme decisões mudam durante o desenvolvimento. `CLAUDE.md` e
> `.agents/rules/project.md` apontam para cá; não duplique decisões neles.

## 1. Objetivo do projeto

Assistente virtual multimodal (texto, imagem e áudio) capaz de atender
clientes em quatro domínios: Vendas, Suporte Técnico, Atendimento ao Usuário e
Agendamento de Visita. O sistema combina um modelo de IA executado localmente
em GPU (16GB) com a possibilidade de acionar modelos externos quando
necessário, apoiado por um Roteador/Orquestrador que interpreta a intenção do
usuário e decide o caminho mais adequado — incluindo busca aumentada por
recuperação (RAG) em bases de dados, documentos, sites e imagens, e o
acionamento de MCPs (Model Context Protocol) em duas direções:

- **Como cliente** de um MCP externo, para marcar visitas diretamente no
  Google Calendar.
- **Como provedor** de um MCP próprio, que expõe catálogo de produtos,
  estoque, preços e manuais, além de ferramentas de validação de
  compatibilidade, frete, cotação e reserva/pedido — tanto para o próprio chat
  quanto para IAs de parceiros integradores.

Além da conversa em si, o sistema reconhece o perfil do usuário (cliente,
lead ou contato esporádico), mantém memória entre interações e monitora o
tom da conversa para acionar um atendente humano quando necessário.

## 2. Visão geral da arquitetura

Fluxo macro: entrada multimodal → pré-processamento (STT para áudio, OCR para
imagem) → Roteador/Orquestrador (intenção + perfil do usuário) → módulos de
domínio (RAG, modelo local, modelo externo, monitor de tom, classificação de
usuário) → MCPs (Google Calendar consumido; MCP B2B provido) → resposta ao
usuário.

```
Entrada multimodal (texto / áudio / imagem)
        │
        ▼
Pré-processamento (STT / OCR)
        │
        ▼
Roteador / Orquestrador  ──── (paralelo) ──── Monitor de tom
        │                                          │
        ├──► RAG (BD, PDFs, sites, imagens)        ├──► Atendente humano
        ├──► Modelo local (GPU 16GB)                    (transferência)
        ├──► Modelo externo
        ├──► MCP Google Calendar (agendamento)
        └──► MCP B2B (catálogo, estoque, preços — provido)
        │
        ▼
   Resposta ao usuário
```

Este diagrama cobre a arquitetura de IA/backend. A interface que o usuário
efetivamente usa (site institucional, produtos, pedidos e o widget de chat
que expõe esse fluxo) é documentada separadamente em `docs/FRONTEND.md`.

## 3. Requisitos funcionais

| # | Requisito |
| --- | --- |
| R1 | Modelo de IA rodando localmente em GPU de 16GB, sem depender de nuvem para as tarefas essenciais. |
| R2 | Entrada de chat multimodal: aceitar texto, imagem e áudio. |
| R3 | Roteador/Orquestrador que identifica a intenção do usuário e decide entre modelo interno ou externo. |
| R4 | RAG capaz de buscar em banco de dados, textos, PDFs, sites e banco de imagens. |
| R5 | Conversão de áudio em texto (STT) antes da análise e contextualização no chat. |
| R6 | Tratamento de imagem: uso dirigido (ex.: comprovante solicitado) ou uso espontâneo (busca de produto interno, com fallback para busca externa) — via OCR e identificação de imagem. |
| R7 | Domínios de atendimento: Vendas, Suporte Técnico, Atendimento ao Usuário e Agendamento de Visita, com identificação de intenção pelo orquestrador. |
| R8 | Monitoramento contínuo do tom da conversa, com transferência para atendente humano em casos de urgência ou insatisfação. |
| R9 | Armazenamento da conversa com identificação única, permitindo retomar com um resumo do histórico recente. |
| R10 | Classificação do usuário ao longo da conversa como Cliente, Lead ou Cliente Esporádico. |
| R11 | Módulo de agendamento de visita, reconhecido como intenção própria pelo roteador, que aciona um MCP — preferencialmente o do Google Calendar — para criar o evento. |
| R12 | Exposição de um MCP próprio pela empresa (servidor/provedor), disponibilizando catálogo, estoque, preços e documentação técnica, além de ferramentas de validação de compatibilidade, frete, cotação e reserva/pedido, para uso por IAs de parceiros integradores e, internamente, pelo próprio Roteador/Orquestrador. |

**Assimetria intencional entre domínios:** Vendas e Agendamento de Visita
contam, desde o MVP, com ferramentas de ação (o MCP B2B da Seção 6 e o MCP do
Google Calendar, respectivamente). Suporte Técnico e Atendimento ao Usuário
são resolvidos, no protótipo, pela combinação de LLM e RAG (textos, PDFs,
manuais, crawler do site), sem uma camada de ação dedicada — abrir/acompanhar
chamados via ticketing é evolução futura (ver Seção 6 e `docs/ROADMAP.md`).

## 4. Fluxos de decisão: imagem e monitoramento de tom

**(a) Tratamento de imagem:** imagem recebida → foi solicitada pelo sistema
(ex.: comprovante)? → **sim:** OCR + validação (uso dirigido). → **não**
(espontânea): busca interna de produto via embeddings (CLIP) → encontrou no
catálogo interno? → **sim:** retorna produto correspondente. → **não:**
fallback para busca externa de imagem.

**(b) Monitoramento de tom:** nova mensagem no chat → classificador de
sentimento/urgência → ultrapassou o limiar de urgência/insatisfação? →
**não:** fluxo normal continua. → **sim:** alerta e transferência para
atendente humano.

## 5. Escopo do MVP e evolução futura

Três decisões de escopo:

1. Integração com CRM está **fora do escopo** do projeto.
2. Agendamento de visita é uma nova intenção do roteador que aciona um MCP
   **externo** (preferencialmente Google Calendar), em vez de um módulo de
   agenda construído internamente.
3. O MCP de integração B2B (R12) nasce como **servidor interno**, consumido
   primeiro pelo próprio chat, e só evolui para exposição real a parceiros
   externos depois (ver Seção 6).

R4 estabelece que o RAG deve buscar em BD, textos, PDFs, sites e banco de
imagens — por isso, conector a BD relacional, crawler de sites e RAG
multimodal sobre imagens são **obrigatórios no MVP**, não itens adiáveis, mas
entram em versões simplificadas frente a uma versão de produção: o conector
ao BD é somente leitura, sem sincronização incremental; o crawler cobre um
conjunto restrito de páginas pré-definidas, sem agendamento; o catálogo de
imagens do RAG multimodal é ampliado, mas ainda não completo, com reranking
básico dos resultados.

**Decisão registrada (Fase 2, resolve divergência entre o comentário original
de `orchestrator.py` e o spec de design da Fase 1):** ao trocar o
`NullRAGClient` pela busca vetorial real no Qdrant, o conteúdo dos documentos
recuperados passa a ser **injetado no prompt do LLM** (a resposta fica
fundamentada no que está nos PDFs/textos indexados), não só usado como sinal
binário (vazio/não-vazio) para a decisão local x externo — esse sinal
continua existindo (ainda decide o roteamento), mas deixa de ser o único
efeito da busca. Sem isso, ter RAG de verdade não mudaria a qualidade da
resposta, só a decisão de roteamento.

### Tabela de escopo por requisito

| Requisito | MVP (protótipo) | Evolução futura |
| --- | --- | --- |
| Modelo local (RTX40780 GPU 16GB) | Servido via **Ollama** (decisão fechada — simplicidade de setup/gestão de modelos e instrumentação de latência pronta via `eval_count`/`eval_duration`, ver `docs/TECHNOLOGY_STACK.md`). Avaliação comparativa ampliada entre **9 configurações**: Llama 3.1 8B; Qwen2.5 7B; Qwen3 14B (Q4_K_M e Q5_K_M); Qwen3 8B (Q5_K_M e Q8_0); Phi-4-mini/Phi-4 (3.8B–7B); Gemma-4-12B (4-bit e 8-bit) — ver riscos de VRAM na Seção 7 | Fine-tuning de domínio, otimização de latência em produção |
| Entrada multimodal | Texto e áudio (STT) funcionando, com suporte a mais de um formato de áudio (ex.: wav e mp3); imagem com fluxo básico. STT via **faster-whisper rodando na mesma GPU local** (decisão fechada — consistente com a estratégia "local-first" do resto do projeto, sem custo por chamada; ver risco de contenção de VRAM na Seção 7), modelo `small` ou `medium` conforme resultado da Seção 7 | Robustez para áudio ruidoso, formatos adicionais, streaming |
| Roteador/Orquestrador | Classificador de intenção simples (regras + LLM) para local x externo x RAG, com log básico de decisões (custo/latência). Modelo externo acessado via **OpenRouter** (uma chave cobrindo múltiplos provedores). Domínios Vendas/Suporte/Atendimento tentam local+RAG primeiro e só escalam para externo se: fora de escopo, RAG sem resultado relevante, ou complexidade alta; Agendamento é sempre local. Classificador considera as últimas 1–3 mensagens da conversa (não só a mensagem isolada), necessário para resolver confirmações curtas a ofertas feitas pelo próprio assistente (ex.: aceite de agendamento proposto) | Roteador adaptativo com aprendizado contínuo e métricas de custo/qualidade em produção |
| RAG — textos, PDFs, BD e sites (obrigatório) | Ingestão de PDFs/textos + busca vetorial; conector básico de leitura a um BD relacional; crawler ampliado, cobrindo até 5 sites/páginas pré-definidas | Conector com escrita/sincronização incremental, crawler amplo e agendado, múltiplas fontes web |
| RAG sobre imagens / tratamento de imagem (obrigatório) | Busca multimodal via embeddings (ex.: CLIP) em catálogo ampliado, com reranking básico + OCR para imagens dirigidas | Catálogo completo, embeddings mais robustos, busca externa refinada |
| Domínios (Vendas/Suporte/Atendimento) | Separação lógica de fluxo e prompts por domínio, com playbooks iniciais para Suporte Técnico e Atendimento ao Usuário. Playbook de Vendas inclui a oferta proativa de agendamento de visita quando a conversa indica intenção de compra e o portfólio de produtos é compatível (o roteador só reclassifica como `agendamento` na resposta seguinte do cliente, usando o contexto curto de conversa citado na linha "Roteador/Orquestrador") | Playbooks completos por domínio, integração com sistema de ticketing |
| Agendamento de visita (MCP consumido) | Nova intenção reconhecida pelo roteador; coleta data/hora e dados básicos; chama o MCP do Google Calendar e envia confirmação automática por e-mail | Reagendamento/cancelamento, checagem de disponibilidade em múltiplas agendas, confirmação também por SMS |
| MCP de integração B2B (MCP provido) | Servidor MCP de uso interno, reaproveitando a base do catálogo/estoque/preços do RAG; recursos de leitura + as quatro ferramentas já implementadas; sem autenticação por parceiro nem exposição pública | Exposição a integradores externos reais, autenticação por parceiro (API key/OAuth), auditoria de ações transacionais e limites de uso |
| Monitor de tom | Classificador de sentimento/urgência (heurística + LLM leve) com alerta, transferência simulada e log dos casos escalonados | Integração real com fila de atendentes humanos, escalonamento por SLA |
| Memória da conversa | Persistência por ID + resumo automático periódico (não só ao final) | Perfil de cliente enriquecido a partir do histórico de conversas |
| Classificação do usuário | Heurística inicial (histórico de compras/perguntas) — Cliente/Lead/Esporádico, com revisão dos critérios a partir dos primeiros dados coletados | Modelo preditivo, score de propensão, enriquecimento de dados externos |

## 6. MCP de integração com parceiros B2B (recursos e ferramentas)

Enquanto R11 usa o assistente como **cliente** de um MCP externo (Google
Calendar), R12 propõe o caminho inverso: a própria empresa atua como
**servidor/provedor** de MCP, expondo de forma padronizada dados e ações que
hoje ficam presos em sistemas internos, para que IAs de terceiros (sistemas
de revendedores, marketplaces, integradores de projetos) consultem
informações e executem ações transacionais diretamente.

**Recursos (dados, somente leitura):**
- Catálogo de produtos: especificações técnicas, dimensões e pesos.
- Estoque em tempo real: quantidade disponível por centro de distribuição.
- Tabelas de preços: custos atualizados, descontos por volume e campanhas.
- Manuais e documentação: instalação, esquemas elétricos, termos de garantia.

**Ferramentas (ações e automações transacionais):**
- Validação de compatibilidade entre peça/acessório e equipamento principal.
- Consulta de frete e prazos para o CEP do cliente final.
- Cotação automática com base nas exigências do projeto.
- Reserva ou pedido: criar ordens de compra ou pré-reservas de estoque.

**Relação com a arquitetura existente:** os quatro recursos são as mesmas
fontes já usadas internamente pelo RAG (R4) e pela área de produtos/pedidos
do site. Implemente **um único backend** desses dados e exponha duas
frentes sobre ele — RAG/chat consultando internamente, servidor MCP expondo a
mesma base a integradores externos — em vez de duplicar lógica. O próprio
Roteador/Orquestrador deve ser tratado como "mais um integrador" desse MCP
para intenções de Vendas (cotação, compatibilidade, estoque).

**Governança e segurança (relevante para a evolução futura, não para o
MVP):** autenticação por parceiro (API key/OAuth), permissões granulares por
recurso/ferramenta, rate limiting, trilha de auditoria para ações que alterem
estoque ou gerem pedido, tratamento de concorrência em reservas/pedidos.

**Escopo no protótipo (MVP):** versão interna — recursos de leitura sobre uma
base pequena e as quatro ferramentas já implementadas, mas **sem
autenticação por parceiro nem exposição pública**.

## 7. Riscos e limitações conhecidos

- Escopo ambicioso para um único protótipo: conector de BD, crawler, RAG
  multimodal e as quatro ferramentas do MCP B2B são obrigatórios já no MVP;
  pode ser necessário priorizar as frentes mais custosas — RAG multimodal e
  monitor de tom — caso o escopo completo não seja viável de uma só vez.
- Restrição de hardware: 16GB de VRAM limita os modelos locais candidatos a
  versões quantizadas; candidatos maiores (ex.: Qwen3 14B, Gemma-4-12B) só
  entram na avaliação comparativa em quantizações que deixem margem para o
  KV cache — evitar variantes acima de ~12–14B mesmo quantizadas, pelo risco
  de OOM. "Gemma-4-12B" ainda não foi verificado como disponível no registro
  do Ollama; confirmar (`ollama pull` ou `ollama.com/library`) antes de
  incluir nos resultados finais.
- STT (faster-whisper) roda na mesma GPU que o modelo local de chat —
  contenção de VRAM entre os dois é um risco real. `# MVP: default fechado
  em small (STT_MODEL_SIZE, ~1-2GB de VRAM), sem lógica automática de troca
  de tamanho por VRAM disponível em runtime — ajuste manual para medium/CPU/
  API externa fica para depois do MVP, se necessário`.
- Formato do áudio recebido em `POST /api/chat/messages`: `# MVP: detectado
  a partir do conteúdo (magic bytes, via ffmpeg/faster-whisper), sem campo
  explícito novo no schema (payload.audio continua só base64) — mantém o
  contrato de docs/FRONTEND.md §4 estável`.
- RAG multimodal é a parte mais custosa tecnicamente; o protótipo cobre um
  catálogo ampliado, mas não completo, com embeddings prontos (ex.: CLIP),
  sem treinar modelo próprio.
- Conector a BD e crawler terão escopo restrito (leitura simples, até 5
  páginas fixas) — não são solução genérica de produção.
- Monitor de tom: classificadores leves tendem a mais falsos
  positivos/negativos; tratar como heurística, não decisão final automatizada.
- Atendimento humano real (fila, transferência de contexto) não será
  implementado de ponta a ponta neste protótipo — é simulado.
- Classificação de cliente/lead/esporádico depende de poucos sinais iniciais;
  tratar como hipótese a validar com mais dados.
- Dependência do MCP do Google Calendar: falhas de conexão/permissão
  precisam de tratamento de erro claro (ex.: tentar novamente, transferir
  para atendente).
- MCP B2B sem autenticação por parceiro/auditoria: ferramentas transacionais
  (reserva, pedido) ficam restritas a uso interno no protótipo.
- Escopo do MVP relativamente amplo (4 ferramentas do MCP B2B, playbooks
  iniciais, crawler/catálogo maiores) aumenta a superfície de testes dentro
  do próprio protótipo.

## 8. Próximos passos após o protótipo

- Avaliar qualidade do roteador com casos reais e ajustar critérios de
  decisão local x externo.
- Amadurecer o RAG: mais fontes de BD/sites, crawler agendado e mais
  abrangente, catálogo de imagens completo, embeddings mais robustos.
- Aprimorar o monitor de tom com modelo dedicado e regras validadas com a
  área de atendimento.
- Planejar integração real com sistema de ticketing (playbooks de Suporte e
  Atendimento) e com o MCP do Google Calendar em produção (autenticação,
  conflitos de agenda, reagendamento/cancelamento).
- Evoluir o MCP B2B do uso interno para exposição real a parceiros:
  autenticação por integrador, permissões granulares, auditoria, limites de
  uso, testes com parceiros piloto.

## 9. Avaliação experimental

Ver `docs/EVALUATION.md` para o detalhamento operacional. Resumo das três
frentes: acerto do roteador na identificação de intenções, qualidade das
respostas do RAG, e comparação de latência entre modelo local e externo.

## 10. Considerações finais

O desenho atende aos doze requisitos de forma modular, permitindo que o
protótipo entregue um fluxo ponta a ponta funcional, com escopo robusto —
incluindo as quatro ferramentas do MCP B2B, playbooks iniciais por domínio e
catálogo de imagens ampliado — servindo de base para as próximas etapas do
trabalho, entre elas a evolução do MCP interno para integração real com
parceiros B2B. A avaliação experimental complementa a entrega com evidências
quantitativas sobre roteador, RAG e latência, dando mais robustez à análise
dos resultados.
