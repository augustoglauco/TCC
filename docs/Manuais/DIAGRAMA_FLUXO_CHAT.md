# Diagrama de Usabilidade, Fluxos e Conexões do Chat

Este documento apresenta a arquitetura visual completa do **Chat**, detalhando o ciclo de vida da requisição desde o envio dos payloads no frontend (texto, áudio, imagem de produto, imagem de documento e e-mail) até as decisões do orquestrador, integrações com microsserviços MCP, buscas vetoriais no Qdrant e eventos em tempo real via **Server-Sent Events (SSE)**.

---

## 1. Diagrama de Fluxo e Roteamento de Decisões

```mermaid
flowchart TD
    %% SUBGRAPHS DE FLUXO
    subgraph INP ["1. Entrada do Usuário (Frontend Chat Widget)"]
        A1["Mensagem de Texto<br/>(message)"]
        A2["Áudio Base64<br/>(audio)"]
        A3["Imagem de Produto<br/>(image + intent!=documento)"]
        A4["Imagem de Documento<br/>(image + intent==documento)"]
    end

    subgraph PRE ["2. Camada de Pré-Processamento (FastAPI /api/chat/messages)"]
        B1["Decodificar & Validar Base64 Payload"]
        B2["Serviço STT Whisper<br/>Transcrever Áudio"]
        B3["Serviço OCR PyTesseract<br/>Extrair Texto da Imagem"]
        B4["Montar Message Efetiva"]
    end

    subgraph DEC ["3. Decisão de Roteamento de Entrada"]
        C1{"Qual a natureza do payload?"}
    end

    subgraph IMG ["4. Fluxo de Identificação de Produto (Sem LLM Texto)"]
        D1["Gerar Vector Embedding<br/>(CLIP ViT-B/32)"]
        D2["Busca Vetorial no Qdrant<br/>('catalogo_imagens')"]
        D3{"Score >= Limiar Interno?"}
        D4["Modelo Multimodal Externa<br/>(OpenRouter Vision JSON)"]
        D5{"É do Portfólio & Confiança Alta?"}
        D6["Busca no RAG de Texto por Especificações"]
        D7["Produto Não Identificado"]
        D8["Montar Evento de Identificação"]
    end

    subgraph EML ["5. Fluxo de E-mail Único"]
        E1["Detectar Mensagem Apenas E-mail"]
        E2["Persistir E-mail no Perfil do Usuário"]
        E3["Resposta Estática Sem Consumo de LLM"]
    end

    subgraph ORQ ["6. Orquestrador de Atendimento (Pipeline Conversacional)"]
        F1["Carregar Histórico Recente & Resumo (Postgres)"]
        F2["Classificador de Intenção (Intent Router)"]
        F3{"Qual o Domínio?"}
        
        G1["Domínio: Agendamento<br/>(MCP Google Calendar - 8090)"]
        G2["Domínio: Vendas / Catálogo<br/>(MCP B2B - 8100 & RAG Qdrant)"]
        G3["Domínio: Pós-Venda<br/>(Consulta Pedidos & RAG)"]
        G4["Domínio: Atendimento / Geral<br/>(RAG de Texto 'docs_texto')"]
        
        H1["Estratégia de Roteamento de Complexidade"]
        H2{"Complexo, Sensível ou Escalonado?"}
        H3["LLM Local (Ollama - Qwen/Llama)"]
        H4["LLM Externa (OpenRouter - Claude/GPT)"]

        I1["Monitor de Tom & Sentimento"]
        I2{"Insatisfação / Confiança Baixa?"}
        I3["Disparar Escalonamento Humano<br/>(Background Async Task)"]
    end

    subgraph POS ["7. Memória Assíncrona & Métricas"]
        J1["Gravar Mensagem & Métricas no DB"]
        J2{"Atingiu Limiar de Resumo?"}
        J3["Background Task:<br/>Sintetizar Resumo da Conversa"]
    end

    subgraph OUT ["8. Transmission Stream SSE (Event Stream)"]
        K1["event: conversation"]
        K2["event: transcription"]
        K3["event: token (Chunks em tempo real)"]
        K4["event: identification (JSON produto)"]
        K5["event: escalonamento"]
        K6["event: done (Métricas e Perfil)"]
    end

    %% CONEXÕES DE LIGAÇÃO
    A1 --> B1
    A2 --> B2 --> B4
    A4 --> B3 --> B4
    A3 --> B1

    B1 --> C1
    B4 --> C1

    C1 -- "Imagem de Produto" --> D1
    C1 -- "Mensagem Apenas E-mail" --> E1 --> E2 --> E3 --> K3 & K6
    C1 -- "Texto / Transcrição / OCR" --> F1

    D1 --> D2 --> D3
    D3 -- "Sim (Alta Confiança)" --> D6 --> D8
    D3 -- "Não" --> D4 --> D5
    D5 -- "Sim" --> D6
    D5 -- "Não" --> D7 --> D8
    D8 --> K3 & K4 & K6

    F1 --> F2 --> F3
    F3 -- "agendamento" --> G1 --> H1
    F3 -- "vendas" --> G2 --> H1
    F3 -- "pos_venda" --> G3 --> H1
    F3 -- "atendimento/fora_escopo" --> G4 --> H1

    H1 --> H2
    H2 -- "Não (Simples)" --> H3
    H2 -- "Sim (Complexo)" --> H4

    H3 --> I1
    H4 --> I1

    I1 --> I2
    I2 -- "Sim" --> I3 --> K5
    I2 -- "Não" --> J1

    H3 -- "Tokens" --> K3
    H4 -- "Tokens" --> K3

    J1 --> J2
    J2 -- "Sim" --> J3
    J1 --> K6
```

---

## 2. Diagrama de Componentes e Integrações do Sistema

O diagrama abaixo ilustra o relacionamento lógico entre as camadas de **Frontend**, **Backend FastAPI**, **Bancos de Dados/Vetores** e **Servidores MCP externos**.

```mermaid
graph LR
    subgraph FE ["Frontend App (Next.js - 3001)"]
        UI["Chat Widget UI"]
    end

    subgraph BE ["Backend Services (FastAPI - 8000)"]
        API["/api/chat/messages"]
        ORCH["Orquestrador de Intenções"]
        CLIP["CLIP Embedder (ViT-B/32)"]
        OCR_ENG["PyTesseract OCR"]
        STT_ENG["Whisper STT"]
    end

    subgraph DB ["Armazenamento & Vetores"]
        PG[("Postgres DB (5433)<br/>Histórico, Perfil e Métricas")]
        QDR[("Qdrant Vector DB (6333)<br/>'catalogo_imagens' & 'docs_texto'")]
    end

    subgraph MCP ["Servidores de Protocolo MCP"]
        CAL_MCP["Calendar MCP Server (8090)<br/>Google Calendar API"]
        B2B_MCP["B2B MCP Server (8100)<br/>Catálogo & Estoque B2B"]
    end

    subgraph EXT ["Provedores LLM & Visão"]
        OLLAMA["Ollama Local (11434)<br/>Modelos Rápidos/Locais"]
        OPENROUTER["OpenRouter API (HTTPS)<br/>Modelos Avançados & Visão"]
    end

    %% Ligações do Frontend
    UI -- "POST SSE /api/chat/messages" --> API

    %% Ligações Internas do Backend
    API --> STT_ENG
    API --> OCR_ENG
    API --> CLIP
    API --> ORCH

    %% Ligações com DB & Vetores
    ORCH -- "Carregar/Gravar Memória" --> PG
    ORCH -- "Busca de Conhecimento" --> QDR
    CLIP -- "Busca por Imagem Similar" --> QDR

    %% Ligações MCP
    ORCH -- "Agendamentos" --> CAL_MCP
    ORCH -- "Estoque & Preços B2B" --> B2B_MCP

    %% Ligações LLM
    ORCH -- "Roteamento Simples" --> OLLAMA
    ORCH -- "Roteamento Complexo / Visão" --> OPENROUTER
```

---

## 3. Matriz de Mapeamento: Entradas vs. Redirecionamentos

| Tipo de Entrada | Condição / Payload | Pré-processador | Rota de Execução | Componentes / Integrações Envolvidos | Formato da Resposta SSE |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Texto Puro** | `message` preenchido | N/A | Pipeline Conversacional Completo | Intent Router $\rightarrow$ RAG / MCP $\rightarrow$ LLM (Ollama/OpenRouter) | `conversation`, `token`, `done` |
| **Áudio** | `audio` (Base64) | Whisper STT (`SttClient`) | Transcrição $\rightarrow$ Pipeline Conversacional | Whisper $\rightarrow$ Intent Router $\rightarrow$ LLM | `conversation`, `transcription`, `token`, `done` |
| **Imagem de Produto** | `image` (Base64) & `intent != "documento"` | Validação de Imagem (PNG/JPG/WEBP) | Identificação por CLIP + Visão + RAG Texto | `ClipEmbedder` $\rightarrow$ Qdrant (`catalogo_imagens`) $\rightarrow$ OpenRouter Vision $\rightarrow$ RAG | `conversation`, `identification`, `token`, `done` |
| **Imagem de Documento** | `image` (Base64) & `intent == "documento"` | PyTesseract OCR (`extract_text_from_base64`) | Extração de Texto $\rightarrow$ Pipeline Conversacional | PyTesseract $\rightarrow$ Anexa texto extraído $\rightarrow$ LLM | `conversation`, `token`, `done` |
| **Apenas E-mail** | `message` é um e-mail válido | Regex de Extração de E-mail | Registro no Perfil + Resposta Fixa | Postgres (`registrar_email`) $\rightarrow$ Resposta Estática | `conversation`, `token`, `done` |

---

## 4. Referências no Código Fonte

- **Endpoint Principal do Chat:** [`src/app/api/chat.py`](file:///home/augusto/Projetos/TCC/backend/src/app/api/chat.py#L300)
- **Identificação por Imagem (CLIP + Visão + RAG):** [`src/app/rag/image_identification.py`](file:///home/augusto/Projetos/TCC/backend/src/app/rag/image_identification.py#L101)
- **Orquestrador de Atendimento e Intenções:** [`src/app/router/orchestrator.py`](file:///home/augusto/Projetos/TCC/backend/src/app/router/orchestrator.py)
- **Motor de OCR:** [`src/app/ocr/image_processor.py`](file:///home/augusto/Projetos/TCC/backend/src/app/ocr/image_processor.py)
- **Gerenciador de Memória e Sessão:** [`src/app/memory/store.py`](file:///home/augusto/Projetos/TCC/backend/src/app/memory/store.py)
