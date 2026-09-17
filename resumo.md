# Resumo do que já foi desenvolvido

> Projeto: assistente virtual multimodal (texto/imagem/áudio) com roteador
> inteligente entre modelo local e externo, RAG e MCPs. TCC de especialização
> em IA generativa. Visão completa: `docs/ARCHITECTURE.md`. Progresso
> detalhado, item a item: `docs/ROADMAP.md`.

## ✅ Pronto

**Fase 0 — Infraestrutura**
Repositório, ambiente com GPU, `.env`, logging estruturado, lint/testes — tudo configurado.

**Fase 1 — Modelo local e roteador**
Modelo local via **Ollama** + modelo externo via **OpenRouter**. Classificador de
intenção (regras + LLM) decide entre os quatro domínios de atendimento,
considerando as últimas mensagens da conversa, com log das decisões.

**Fase 2 — Entrada multimodal e RAG textual**
Chat aceita texto e áudio (STT). RAG funcionando: ingestão de PDFs/textos com
busca vetorial (Qdrant), **conector de leitura a banco de dados relacional**,
endpoint de upload de documentos, e **extração de PDF de qualidade** —
detecção de layout em 2 colunas (`pdfplumber`), corrige catálogos de produto
que antes saíam com título/bullets embaralhados entre produtos vizinhos.
Falta só o crawler de páginas fixas.

**Fase 7 e 8 — Frontend (site + widget de chat)**
Projeto Next.js criado; chat migrou de painel fixo para **modal central**
(`ChatModal`, acessível pelo botão "Chat / Agente" no cabeçalho e CTAs nas
páginas) — texto, áudio, indicador de domínio/origem do modelo, persistência
de conversa, tratamento de erro. Páginas institucionais, produtos, pedidos e
agendamento ainda **parciais** (marcadas `[~]` no roadmap — esqueleto existe,
falta refinar).

## 🎁 Extras construídos fora do escopo original do MVP

Pedidos explícitos seus, registrados como "fora do MVP" no roadmap para não
confundir com o escopo formal do TCC:

1. **Configuração de ingestão do RAG** (`/admin/ingestao`) — registro/exclusão
   de documentos, múltiplas "collections" com parâmetros próprios (tamanho de
   chunk, modelo de embedding, métrica de distância, HNSW, quantização,
   payload indexing), playground de busca comparativa entre collections,
   promoção de uma collection para "ativa" no chat real, e **preview do
   documento original** (PDF/CSV/texto) direto na tabela de ingestão.
2. **Gerenciador de modelos locais** (`/admin/modelos`) — listar modelos
   baixados no Ollama, trocar o modelo ativo do chat em runtime, e baixar um
   modelo novo (biblioteca do Ollama ou GGUF do Hugging Face) sem bloquear o
   backend.
3. **Telemetria de inferência no chat** — cada resposta do assistente vem com
   modelo usado, tokens, latência, TTFT, TPS, custo estimado e métricas de
   RAG (tempo/qtd./score da busca); o `ChatModal` mostra um painel com essas
   métricas e exporta a conversa em CSV/JSON — pensado para alimentar a
   avaliação experimental da Fase 10, não como feature de produto.

## ⏳ Ainda não iniciado

- **Fase 3** — RAG multimodal (imagem/OCR/CLIP) e separação de prompts por domínio
- **Fase 4** — Agendamento via MCP do Google Calendar + monitor de tom
- **Fase 5** — MCP B2B provido pela empresa (catálogo/estoque/ferramentas)
- **Fase 6** — Memória de conversa e classificação de usuário (Cliente/Lead)
- **Fase 9** — Testes de integração ponta a ponta e robustez
- **Fase 10** — Avaliação experimental (benchmark de modelo, RAG, latência)
- **Fase 11** — Preparação final da entrega

## 🔧 Correções recentes de qualidade/robustez

Além de features novas, esta rodada também corrigiu problemas reais
encontrados numa auditoria do código (parte dele escrito em paralelo por
outro agente, o Antigravity, que também trabalha neste repositório):

- **Vazamento de domínio no RAG** — uma busca sem resultado no domínio certo
  chegou a "vazar" pra outros domínios (ex.: pergunta de vendas trazendo
  conteúdo de suporte), o que também corrompia o sinal que decide se o
  roteador escala pro modelo externo. Corrigido; o comportamento antigo
  existe só como flag opt-in (`RAG_SEARCH_DOMAIN_FALLBACK`, desligada por
  padrão) para quem quiser comparar.
- **TTFT/TPS calculados errado** na telemetria (usava tempo de carregar o
  modelo, não tempo de gerar o primeiro token) — corrigido antes de virar
  dado ruim no dataset da Fase 10.
- Bug no parser de CSV do preview de documento (cortava em espaço em branco
  além do delimitador), `ChatPanel.tsx` órfão removido, CORS hardcoded
  revertido para usar a configuração de `.env`, e lint 100% limpo no
  frontend (0 erros, 0 avisos).

## Como continuar

Peça **"próximo passo"** a qualquer momento — eu leio o roadmap, escolho o
próximo item pendente, confirmo com você, valido o escopo e implemento com
testes, um item de cada vez.
