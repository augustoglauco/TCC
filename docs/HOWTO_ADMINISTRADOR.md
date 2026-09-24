# ⚙️ Manual do Administrador do Sistema (How-To)

> **Público-Alvo**: Administradores de Sistema, Gestores de Produto e Líderes de Atendimento.  
> **Objetivo**: Orientar a gestão da base de conhecimento (RAG e PDFs), execução do web crawler, parâmetros de inteligência artificial em tempo de execução, catálogo de produtos, monitoramento de sessões e controle de atendimento humano.

---

## 📋 Sumário

1. [📌 Acesso e Visão Geral do Painel Admin](#-acesso-e-visão-geral-do-painel-admin)
2. [📄 Gestão da Base de Conhecimento e Ingestão (`/admin/ingestao`)](#-gestão-da-base-de-conhecimento-e-ingestão-adminingestao)
3. [🕸️ Parametrização e Disparo do Web Crawler](#️-parametrização-e-disparo-do-web-crawler)
4. [🤖 Gerenciamento e Parametrização da IA (`/admin/modelos`)](#-gerenciamento-e-parametrização-da-ia-adminmodelos)
5. [🛍️ Gestão do Catálogo B2B e Ferramentas MCP](#️-gestão-do-catálogo-b2b-e-ferramentas-mcp)
6. [📊 Monitor de Tom, Sessões e Atendimento Humano](#-monitor-de-tom-sessões-e-atendimento-humano)

---

## 📌 Acesso e Visão Geral do Painel Admin

O painel de administração é acessível diretamente pelo menu do site (ícone de engrenagem ⚙️ no cabeçalho ou links no rodapé).

### Módulos Principais
1. **Ingestão de Documentos (`/admin/ingestao`)**: Upload de PDFs, textos de suporte e indexação automatizada de sites via crawler.
2. **Modelos e Parâmetros (`/admin/modelos`)**: Escolha do modelo de linguagem (LLM) local, ajuste de velocidade/criatividade e regras de transbordo.
3. **Gestão Operacional**: Monitoramento de conversas, perfilamento de clientes e filas de atendimento.

---

## 📄 Gestão da Base de Conhecimento e Ingestão (`/admin/ingestao`)

O sistema utiliza a técnica de **RAG (Busca Aumentada por Recuperação)**. Isso significa que o assistente lê a documentação oficial da sua empresa para responder dúvidas de Suporte Técnico e Atendimento com precisão.

### Como Enviar Novos Documentos (PDFs / Manuais)
1. Acesse a rota `/admin/ingestao` no navegador.
2. Na seção **Upload de Documentos**, selecione um arquivo `.pdf` ou `.txt` (ex.: *Manual_de_Instalacao_Produto_X.pdf*).
3. Clique em **Enviar e Indexar**.
4. O sistema irá extrair os textos, quebrá-los em blocos lógicos e armazená-los na base vetorial. A partir desse momento, o assistente já saberá responder dúvidas baseadas nesse novo arquivo.

---

## 🕸️ Parametrização e Disparo do Web Crawler

O **Web Crawler** é um robô de busca que navega em páginas web (como sua Central de Ajuda ou FAQ) e importa todo o conteúdo diretamente para a memória do assistente virtual.

### Como Parametrizar o Crawler (Explicação Simplificada)

Ao acessar a seção **Web Crawler** em `/admin/ingestao`, você encontrará os seguintes campos de configuração:

| Parâmetro | Nome na Tela | O que significa na prática? | Exemplo Recomendado |
|---|---|---|---|
| **URL Semente** | *Endereço Inicial (URL)* | A página exata por onde o robô deve começar a leitura. | `https://suaempresa.com.br/suporte` |
| **Profundidade** | *Nível de Cliques (Profundidade)* | Quantos "cliques" de distância o robô pode navegar a partir da página inicial. <br>• **1**: Lê apenas a página informada.<br>• **2**: Lê a página informada + links diretos dela.<br>• **3**: Navega até 3 níveis de links internos. | **2** *(Evita navegar em todo o site desnecessariamente)* |
| **Limite de Páginas** | *Teto Máximo de Páginas* | O número máximo de páginas que o robô pode salvar em uma única execução. Garante que a leitura seja rápida e não sobrecarregue seu servidor. | **50** páginas |

### Executando o Crawler
1. Preencha a **URL Semente**, **Profundidade** e **Limite de Páginas**.
2. Clique no botão **Iniciar Varredura Web**.
3. Acompanhe a barra de progresso. Ao finalizar, o sistema confirmará o total de páginas lidas e indexadas com sucesso.

---

## 🤖 Gerenciamento e Parametrização da IA (`/admin/modelos`)

Nesta tela, o administrador controla como o "cérebro" do assistente se comporta. Você pode mudar qual modelo de IA está ativo na GPU local e ajustar o estilo de resposta.

---

### 1. Seleção do Modelo Local (Ollama)
O sistema roda em uma GPU própria de 16GB. Você pode escolher qual modelo atende seus clientes no momento:
* **Llama 3.1 8B**: Recomendado para conversas formais, respostas diretas e rápida capacidade de síntese.
* **Qwen 2.5 7B**: Excelente para compreensão estruturada de tabelas, códigos de produtos e raciocínio lógico.

> **Como alterar**: Selecione o modelo desejado no menu suspenso e clique em **Ativar Modelo em Runtime**. A troca ocorre imediatamente sem derrubar o site.

---

### 2. Parametrização de Execução (Controles do Assistente)

Na seção **Parâmetros de Execução**, você pode ajustar o comportamento do assistente. Veja a explicação de cada parâmetro em termos práticos:

#### 🌡️ 1. Temperatura do Modelo Local (`Temperature`)
* **O que faz**: Controla o nível de "criatividade" ou "previsibilidade" da IA.
* **Escala**: De `0.0` a `1.0`.
  * **Valores Baixos (`0.1` a `0.3`) — Recomendado**: A IA responde estritamente baseada nos dados exatos, sem inventar. Ideal para consulta de preços, estoque e especificações técnicas.
  * **Valores Médios (`0.4` a `0.7`)**: Respostas mais fluidas e simpáticas, mantendo o bom senso.
  * **Valores Altos (`0.8` a `1.0`)**: Maior variabilidade de palavras, porém aumenta o risco do assistente fugir do assunto.

#### ⏱️ 2. Tempo Limite do Modelo Local (`Timeout Local`)
* **O que faz**: Determina quantos segundos o sistema deve esperar pela resposta da GPU local antes de decidir tomar uma atitude de contingência.
* **Valor Recomendado**: `15` a `30` segundos.
* **Uso prático**: Se o servidor local estiver muito sobrecarregado e ultrapassar esse tempo, o sistema aciona automaticamente o transbordo para o modelo externo (OpenRouter) para não deixar o cliente esperando.

#### 🌐 3. Tempo Limite do Modelo Externo (`Timeout Externo`)
* **O que faz**: Quantos segundos esperar caso a requisição precise recorrer à IA em nuvem externa.
* **Valor Recomendado**: `20` segundos.

#### 🔄 4. Fallback Automático de RAG (`RAG Domain Fallback`)
* **O que faz**: Chave de Liga/Desliga (`Sim` / `Não`).
* **Uso prático**: Quando ativado (`Sim`), se um cliente fizer uma pergunta de Suporte Técnico enquanto estiver navegando na página de Vendas, o assistente é autorizado a buscar nos manuais técnicos para responder ao cliente, sem bloqueá-lo.

#### 🧭 5. Roteador de Intenção (`Provedor do Classificador`) — novo em 2026-09-23
* **O que faz**: Escolhe qual motor decide o domínio de cada mensagem do cliente (Vendas/Suporte/Atendimento/Agendamento/Fora de escopo) — duas opções:
  * **Heurística + LLM Local (Ollama)** — padrão. Palavras-chave locais, com fallback para o modelo Ollama configurado quando necessário. Não depende de internet.
  * **TypeSafe Jev (OpenRouter)** — um modelo externo de decisão estruturada, mais rápido/barato que um LLM de chat para essa tarefa específica.
* **Uso prático**: Pense nisso como um experimento A/B de classificação — trocar aqui não muda o resto do atendimento, só QUEM decide o domínio da mensagem. Se o Jev falhar (rede, indisponibilidade), o sistema volta sozinho pra heurística local, sem interromper o cliente — você vê qual dos dois realmente respondeu no painel de métricas do chat (ícone ⚙️ ao lado do domínio, em cada resposta).
* **Por que trocar**: útil para comparar acurácia/latência/custo entre os dois provedores (ver `docs/EVALUATION.md`) — não há um "certo" fixo, é uma opção de avaliação.

#### 🚨 6. Monitor de Tom (`Habilitar` / `Provedor`) — novo em 2026-09-23
* **O que faz**: Liga/desliga o Monitor de Tom (R8) e, quando ligado, escolhe qual motor decide o fallback ambíguo (quando a heurística de palavras-chave não encontra um sinal forte de urgência/insatisfação) — mesmas duas opções do Roteador de Intenção acima: **Heurística + LLM Local (Ollama)** (padrão) ou **TypeSafe Jev (OpenRouter)**.
* **Uso prático**: Desligar (`Não`) remove qualquer custo extra por mensagem — nem a heurística roda. Ligado (padrão), toda mensagem passa pela checagem; ao detectar um sinal forte, o assistente continua respondendo normalmente E registra o caso para acompanhamento (ver seção "Monitor de Tom e Escalada" abaixo) — a resposta ao cliente nunca é interrompida por isso.
* **Onde ver os casos escalonados**: por ora só via API (`GET /api/admin/tom/escalonamentos`), sem painel visual dedicado nesta entrega.

---

## 🛍️ Gestão do Catálogo B2B e Ferramentas MCP

O sistema expõe um servidor MCP próprio que alimenta o chat com 4 ferramentas automáticas:

1. **Ferramenta de Compatibilidade**: Verifica se peças ou produtos são compatíveis entre si.
2. **Ferramenta de Cálculo de Frete**: Calcula prazos e valores com base no CEP e peso do produto.
3. **Ferramenta de Cotação B2B**: Aplica descontos por volume e gera orçamentos prévios.
4. **Ferramenta de Reserva/Pedido**: Bloqueia itens em estoque temporariamente durante o checkout.

### Atualizando Dados de Produtos
* Os preços, fotos e quantidades em estoque são sincronizados com o banco de dados PostgreSQL.
* Ao alterar a foto de um produto no catálogo, o assistente atualiza automaticamente os vetores visuais (CLIP), permitindo que clientes encontrem esse produto enviando fotos no chat.

---

## 📊 Monitor de Tom, Sessões e Atendimento Humano

### 1. Classificação Dinâmica do Usuário
O sistema analisa o comportamento da conversa e categoriza o cliente automaticamente em 3 perfis:
* **Cliente**: Usuário logado com histórico de compras anteriores.
* **Lead**: Usuário solicitando cotações, dados de frete ou tirando dúvidas frequentes de compra.
* **Contato Esporádico**: Visitante casual tirando dúvidas gerais.

### 2. Monitor de Tom e Escalada para Atendente Humano (R8)
O assistente monitora continuamente o tom da mensagem do cliente (insatisfação, irritação ou urgência elevada).

* **Limiar de Alerta**: Se o cliente demonstrar forte insatisfação (ex.: *"Ninguém me ajuda, preciso falar com um atendente agora!"*), o monitor de tom aciona um alerta automático.
* **Comportamento no Chat**: O assistente exibe um banner de transferência ("Conectando você a um atendente humano...") e envia a notificação para o painel da equipe de suporte com o resumo completo do histórico recente.
