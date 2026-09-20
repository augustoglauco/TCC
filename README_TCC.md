# Assistente Virtual Multimodal com Roteador Inteligente e Arquitetura Dual MCP

#### Aluno: [Augusto Quintino](https://github.com/augustoglauco)
#### Orientadora: Profª. Manoela Kohler ([prof.manoela@ica.ele.puc-rio.br](mailto:prof.manoela@ica.ele.puc-rio.br))

---

Trabalho apresentado ao curso [GenAI e LLM MASTER](https://ica.ele.puc-rio.br/cursos/ia-generativa-large-language-models/) como pré-requisito para conclusão de curso e obtenção de crédito na disciplina "Projetos de Sistemas Inteligentes de Apoio à Decisão".

- [Link para o código](https://github.com/augustoglauco/TCC)

---

### Resumo

Este projeto apresenta um **Assistente Virtual Multimodal** desenvolvido como Trabalho de Conclusão de Curso (TCC) para automação de atendimento ao cliente em quatro domínios empresariais: Vendas, Suporte Técnico, Atendimento ao Usuário e Agendamento de Visita. A solução combina inferência de LLM executada localmente em GPU com 16GB de VRAM via **Ollama**, RAG (Busca Aumentada por Recuperação) multimodal híbrido com **PostgreSQL** e **Qdrant**, pré-processamento de áudio (STT via **Whisper**) e imagem (OCR via **Tesseract** e busca por similaridade visual via **CLIP**), além de monitoramento contínuo de tom da conversa para escalada humana. A arquitetura adota o protocolo **MCP (Model Context Protocol)** em formato Dual (consumindo o Google Calendar para agendamentos e provendo um servidor próprio B2B com catálogo, estoque e cotações). O roteamento inteligente avalia a intenção e complexidade das mensagens, decidindo autonomamente entre o modelo local, busca vetorial, ferramentas MCP ou transbordo para modelo em nuvem via **OpenRouter API**.

### Abstract

This project presents a **Multimodal Virtual Assistant** developed as a Capstone Project (TCC) to automate customer service across four corporate domains: Sales, Technical Support, Customer Service, and Visit Scheduling. The solution integrates local LLM inference running on a 16GB VRAM GPU via **Ollama**, a hybrid multimodal RAG system leveraging **PostgreSQL** and **Qdrant**, audio preprocessing (STT via **Whisper**), and image analysis (OCR via **Tesseract** and visual similarity via **CLIP**), alongside continuous conversation tone monitoring for human escalation. The system adopts a Dual **MCP (Model Context Protocol)** architecture (consuming Google Calendar for appointment booking while hosting a proprietary B2B MCP server exposing product catalogs, inventory, and quotation tools). An intelligent router analyzes user intent and query complexity, autonomously delegating execution between local models, vector retrieval, MCP tools, or cloud fallback via **OpenRouter API**.

---

### 1. Introdução

A automação de atendimento ao cliente em ambientes corporativos exige equilibrar a privacidade de dados e custos operacionais com respostas precisas e integração a sistemas legados. Modelos de linguagem baseados exclusivamente em nuvem impõem altos custos recorrentes e riscos de privacidade, enquanto soluções puramente locais podem falhar em tarefas de alta complexidade ou integração transacional.

Este trabalho aborda esse desafio propondo uma arquitetura agêntica que prioriza o processamento local em GPU de 16GB (NVIDIA RTX 4080 / A4000) servida por Ollama, combinada com:
1. **Entrada Multimodal Nativa**: Capacidade de receber texto, mensagens de áudio gravadas pelo cliente e imagens (comprovantes para leitura OCR ou fotos de produtos para busca visual no catálogo).
2. **RAG Multimodal Híbrido**: Recuperação vetorial e relacional sobre PDFs, manuais técnicos, FAQ e banco de imagens.
3. **Roteador Inteligente de Intenção**: Orquestrador responsável por classificar o domínio e direcionar a execução para a ferramenta adequada.
4. **Arquitetura Dual MCP**: Integração padronizada com ferramentas externas (Google Calendar) e exposição do catálogo/estoque da empresa através de ferramentas transacionais B2B.
5. **Monitor de Tom e Escalada Humana**: Avaliação de sentimento e urgência com transbordo automático quando insatisfações são identificadas.

---

### 2. Modelagem

A arquitetura do sistema segue o modelo de orquestração agêntica dividida em camadas funcionais:

```text
Entrada Multimodal (Texto / Áudio / Imagem)
                    │
                    ▼
      Pré-processamento (STT / OCR)
                    │
                    ▼
    Roteador / Orquestrador  ──── (paralelo) ──── Monitor de Tom
            │                                          │
            ├──► RAG Híbrido (PostgreSQL, PDFs, CLIP) └──► Atendente Humano
            ├──► Modelo Local (Ollama - GPU 16GB)            (Transferência)
            ├──► Modelo Externo (OpenRouter API)
            ├──► Cliente MCP (Google Calendar — Agendamento)
            └──► Servidor MCP B2B (Catálogo, Estoque, Pedidos)
            │
            ▼
       Resposta ao Usuário (Streaming SSE / Cards Ricos)
```

#### Componentes da Modelagem:
* **Pré-processamento Multimodal**: 
  - *Áudio*: Processado via OpenAI Whisper (`base`) para conversão Speech-to-Text (STT).
  - *Imagem*: OCR dirigido via Tesseract para extração de texto em comprovantes e embeddings visual CLIP (`ViT-B/32`) para busca no catálogo.
* **Roteador / Orquestrador**: Classifica o contexto (analisando as últimas 1 a 3 mensagens) em um dos 4 domínios de atendimento (Vendas, Suporte, Atendimento Geral, Agendamento) e determina o caminho de execução.
* **Inferência Local e Fallback**: O modelo local quantizado (Llama 3.1 8B ou Qwen 2.5 7B) responde às requisições padrão. Caso exceda o limite de tempo ou complexidade, o roteador aciona o modelo externo via OpenRouter API.
* **Dual MCP (Model Context Protocol)**:
  - *Cliente MCP*: Integração OAuth2 com Google Calendar para criação automatizada de eventos de visita.
  - *Provedor MCP B2B*: Servidor próprio que expõe ferramentas de verificação de compatibilidade, cálculo de frete, cotação por volume e reserva de estoque.
* **Interface Frontend (Next.js)**: Widget de chat flutuante adaptável com suporte a *Server-Sent Events (SSE)* para respostas em streaming e renderização de *Cards Ricos* de produtos, cotações e agendamentos.

---

### 3. Resultados

Os resultados quantitativos e qualitativos da plataforma serão consolidados ao término das baterias de testes e avaliações experimentais detalhadas em `docs/EVALUATION.md`, que abrangem:
1. **Acurácia do Roteador de Intenções**: Avaliação do alinhamento da matriz de confusão nos 4 domínios de atendimento.
2. **Qualidade e Relevância do RAG Multimodal**: Medição de métricas de recuperação (Hit Rate, MRR) na busca por documentos técnicos e similaridade de imagens via CLIP.
3. **Desempenho e Latência de Inferência**: Tempo de resposta (First Token Latency e Tokens por Segundo) na GPU local de 16GB frente ao fallback externo em nuvem.

---

### 4. Conclusões

As conclusões finais sobre o impacto arquitetural da utilização de RAG Multimodal, inferência local em GPU e integração Dual MCP serão consolidadas após a finalização da fase de avaliação experimental e validação em ambiente de execução.

---

### 5. Referências

1. **VASWANI, A. et al.** Attention Is All You Need. *Advances in Neural Information Processing Systems (NeurIPS)*, 2017.
2. **LEWIS, P. et al.** Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. *Advances in Neural Information Processing Systems (NeurIPS)*, 2020.
3. **RADFORD, A. et al.** Robust Speech Recognition via Large-Scale Weak Supervision (Whisper). *OpenAI Technical Report*, 2022.
4. **RADFORD, A. et al.** Learning Transferable Visual Models From Natural Language Supervision (CLIP). *International Conference on Machine Learning (ICML)*, 2021.
5. **MODEL CONTEXT PROTOCOL (MCP).** Specification and SDKs for Model Context Protocol. Anthropic Open Standard, 2024. Disponível em: <https://modelcontextprotocol.io/>.
6. **OLLAMA.** Get up and running with Llama 3.1, Qwen2.5, and other large language models locally. 2024. Disponível em: <https://ollama.com/>.

---

### 6. Instalação

A aplicação é implantada e executada em ambiente de servidor local GPU e disponibilizada publicamente através do endereço:

🌐 **URL de Acesso Público**: [https://augustoglauco.duckdns.org:3001](https://augustoglauco.duckdns.org:3001)

#### Resumo da Infraestrutura Local:
* **Banco Relacional & Vetorial**: PostgreSQL 15+ e Qdrant Vector DB containerizados via Docker (`docker-compose up -d`).
* **Inferência Local**: Serviço Ollama rodando localmente com suporte a GPU NVIDIA 16GB VRAM (CUDA 11.8+).
* **Backend**: FastAPI (Python 3.11) executando na porta `8000` (documentação Swagger em `/docs`).
* **Frontend**: Next.js 14+ / Node.js 18+ executando na porta `3000` e publicado publicamente via proxy reverso HTTPS em `https://augustoglauco.duckdns.org:3001`.

*Para o guia completo de provisionamento de infraestrutura, consulte o manual:* [HOWTO_IMPLANTACAO_INFRA.md](docs/HOWTO_IMPLANTACAO_INFRA.md).

---

### 7. Como executar

Para interagir com o sistema e explorar todas as suas funcionalidades:

1. Acesse o endereço público da aplicação: **[https://augustoglauco.duckdns.org:3001](https://augustoglauco.duckdns.org:3001)**.
2. **Navegação no Website**:
   - Explore o catálogo de produtos em `/produtos` e veja especificações detalhadas em `/produtos/[id]`.
   - Consulte o histórico de pedidos e carrinho em `/pedidos`.
   - Acesse os agendamentos realizados em `/agendamentos` e a FAQ/Suporte em `/suporte`.
3. **Utilizando o Assistente Virtual (Widget de Chat)**:
   - Abra o assistente clicando no ícone de balão de conversa flutuante no canto inferior direito.
   - **Mensagens de Texto**: Pergunte sobre produtos, preços, frete, manuais ou solicitações de agendamento.
   - **Mensagens de Voz (Áudio)**: Clique no ícone de microfone, fale sua pergunta e envie (transcrição automática via Whisper STT).
   - **Fotos e Imagens**: Anexe fotos de comprovantes (OCR) ou imagens de produtos para busca por similaridade visual no catálogo (CLIP).
   - **Cards Interativos**: Interaja diretamente com os cards ricos de produtos, cotações B2B e confirmações de agendamento no Google Calendar.

*Para o manual de instrução do usuário final, consulte:* [HOWTO_USUARIO.md](docs/HOWTO_USUARIO.md).  
*Para o manual do administrador (ingestão RAG, crawler e parametrização da IA), consulte:* [HOWTO_ADMINISTRADOR.md](docs/HOWTO_ADMINISTRADOR.md).

---

Matrícula: 123.456.789

Pontifícia Universidade Católica do Rio de Janeiro

Curso de Pós Graduação *Inteligência Artificial Generativa & Large Language Models*
