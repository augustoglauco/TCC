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
busca vetorial (Qdrant), **conector de leitura a banco de dados relacional**
(item mais recente, concluído hoje) e endpoint de upload de documentos.
Falta só o crawler de páginas fixas.

**Fase 7 e 8 — Frontend (site + widget de chat)**
Projeto Next.js criado; chat widget funcionando (texto, streaming, indicador
de domínio/origem do modelo, persistência de conversa, tratamento de erro).
Páginas institucionais, produtos, pedidos e agendamento ainda **parciais**
(marcadas `[~]` no roadmap — esqueleto existe, falta refinar).

## 🎁 Extras construídos fora do escopo original do MVP

Pedidos explícitos seus, registrados como "fora do MVP" no roadmap para não
confundir com o escopo formal do TCC:

1. **Configuração de ingestão do RAG** (`/admin/ingestao`) — registro/exclusão
   de documentos, múltiplas "collections" com parâmetros próprios (tamanho de
   chunk, modelo de embedding, métrica de distância, HNSW, quantização,
   payload indexing), playground de busca comparativa entre collections, e
   promoção de uma collection para "ativa" no chat real.
2. **Gerenciador de modelos locais** (`/admin/modelos`) — listar modelos
   baixados no Ollama, trocar o modelo ativo do chat em runtime, e baixar um
   modelo novo (biblioteca do Ollama ou GGUF do Hugging Face) sem bloquear o
   backend.

## ⏳ Ainda não iniciado

- **Fase 3** — RAG multimodal (imagem/OCR/CLIP) e separação de prompts por domínio
- **Fase 4** — Agendamento via MCP do Google Calendar + monitor de tom
- **Fase 5** — MCP B2B provido pela empresa (catálogo/estoque/ferramentas)
- **Fase 6** — Memória de conversa e classificação de usuário (Cliente/Lead)
- **Fase 9** — Testes de integração ponta a ponta e robustez
- **Fase 10** — Avaliação experimental (benchmark de modelo, RAG, latência)
- **Fase 11** — Preparação final da entrega

## Como continuar

Peça **"próximo passo"** a qualquer momento — eu leio o roadmap, escolho o
próximo item pendente, confirmo com você, valido o escopo e implemento com
testes, um item de cada vez.
