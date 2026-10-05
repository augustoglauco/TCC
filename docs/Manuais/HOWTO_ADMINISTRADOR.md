# ⚙️ Manual do Administrador do Sistema (How-To)

> **Público-Alvo**: Administradores de Sistema, Gestores de Produto e Líderes de Atendimento.  
> **Objetivo**: Orientar a gestão da base de conhecimento (RAG e PDFs), execução do web crawler, parâmetros de inteligência artificial em tempo de execução, catálogo de produtos, monitoramento de sessões e controle de atendimento humano.

---

## 📋 Sumário

1. [📌 Acesso e Visão Geral do Painel Admin](#-acesso-e-visão-geral-do-painel-admin)
2. [👥 Gestão de Usuários (`/admin/usuarios`)](#-gestão-de-usuários-adminusuarios)
3. [📄 Gestão da Base de Conhecimento e Ingestão (`/admin/ingestao`)](#-gestão-da-base-de-conhecimento-e-ingestão-adminingestao)
4. [🕸️ Parametrização e Disparo do Web Crawler](#️-parametrização-e-disparo-do-web-crawler)
5. [🤖 Gerenciamento e Parametrização da IA (`/admin/modelos`)](#-gerenciamento-e-parametrização-da-ia-adminmodelos)
6. [🛍️ Gestão do Catálogo B2B e Ferramentas MCP](#️-gestão-do-catálogo-b2b-e-ferramentas-mcp)
7. [📊 Monitor de Tom, Sessões e Atendimento Humano](#-monitor-de-tom-sessões-e-atendimento-humano)
8. [📉 Dashboards e Gráficos Dinâmicos via Chat (`/admin/dashboards`)](#-dashboards-e-gráficos-dinâmicos-via-chat-admindashboards)
9. [📈 Métricas de Tokens, Custos e Chats Encerrados (`/admin/metricas`)](#-métricas-de-tokens-custos-e-chats-encerrados-adminmetricas)

---

## 📌 Acesso e Visão Geral do Painel Admin

O painel de administração é acessível pelo menu do site (ícone de engrenagem
⚙️ no cabeçalho). **Desde 2026-09-29, esse menu só aparece para quem está
logado com um usuário de perfil `Admin`** (antes, qualquer visitante via os
links de administração) — faça login em `/conta/login` com um e-mail
`admin@example.com`/`admin@*` (senha mock `12345` ou `admin123`) para ver a
engrenagem. Isso restringe a **entrada** pelo menu; as páginas internas
(`/admin/ingestao`, `/admin/produtos`, `/admin/modelos`) continuam sem
checagem própria de sessão se acessadas pela URL direta (`# MVP`, ver
`docs/ARCHITECTURE.md` §5) — só `/admin/usuarios` e `/admin/agendamentos`
bloqueiam o acesso direto de quem não é Admin.

### Módulos Principais
1. **Gestão de Usuários (`/admin/usuarios`)**: cadastro e listagem de usuários, promoção a Administrador e consulta de pedidos por usuário.
2. **Ingestão de Documentos (`/admin/ingestao`)**: Upload de PDFs, textos de suporte e indexação automatizada de sites via crawler.
3. **Modelos e Parâmetros (`/admin/modelos`)**: Escolha do modelo de linguagem (LLM) local, ajuste de velocidade/criatividade e regras de transbordo.
4. **Gestão Operacional**: Monitoramento de conversas, perfilamento de clientes e filas de atendimento.

---

## 👥 Gestão de Usuários (`/admin/usuarios`)

Acessível pelo menu ⚙️ → "Gerenciar Usuários" (só visível para quem está logado como Admin).

* **Listagem e filtros**: todos os usuários cadastrados, com busca por nome/e-mail e filtro por perfil (Cliente/Lead/Esporádico/Admin); contadores de total de usuários, admins e clientes no topo.
* **Ver Pedidos de um usuário**: cada linha da tabela tem um link que abre `/pedidos/historico?email=...` já filtrado para aquele usuário, com um aviso visual roxo de "Modo de Consulta Administrativa" (você está vendo o histórico de outra pessoa, não o seu).
* **Criar Nova Conta** (menu ⚙️ → "Criar Nova Conta", `/conta/cadastro`): cadastra um novo usuário; só é possível marcar o novo usuário como Admin se quem está cadastrando já for Admin (ou for a conta demo `admin@example.com`) — caso contrário a API recusa (403).
* **Como virar Admin**: cadastre-se (ou peça para cadastrarem você) com um e-mail iniciado em `admin@` — por exemplo `admin@suaempresa.com` — ou use a conta demo `admin@example.com`. `# MVP`: é uma regra fixa por prefixo de e-mail, não uma tabela de permissões de verdade.

---

## 📅 Gestão de Agendamentos (`/admin/agendamentos`)

Acessível pelo menu ⚙️ (também restrito a Admin). Duas abas:

* **Agendamentos do Sistema**: lista os agendamentos feitos pelo chat ou manualmente pelo admin, com filtro por e-mail e status (confirmado/cancelado); cada um pode ser cancelado (some do Google Calendar também).
* **Agenda do Google (tempo real)**: consulta ao vivo da agenda corporativa via MCP — mas só mostra os eventos que o **próprio sistema** criou (marcados internamente como `[Sistema]`); um compromisso lançado manualmente direto no Google Calendar não aparece aqui e não conta como conflito de horário para um novo agendamento (`# MVP`, ver `docs/ARCHITECTURE.md` §5, decisão de 2026-09-29).
* **Agendamento manual**: modal com checagem de conflitos, data/hora de início e **duração em minutos** (padrão 60, incrementos de 15) — antes a duração era sempre fixa em 30 minutos.

---

## 📄 Gestão da Base de Conhecimento e Ingestão (`/admin/ingestao`)

O sistema utiliza a técnica de **RAG (Busca Aumentada por Recuperação)**. Isso significa que o assistente lê a documentação oficial da sua empresa para responder dúvidas de Suporte Técnico e Atendimento com precisão.

### Como Enviar Novos Documentos (PDFs / Manuais)
1. Acesse a rota `/admin/ingestao` no navegador.
2. Na seção **Upload de Documentos**, selecione um arquivo `.pdf` ou `.txt` (ex.: *Manual_de_Instalacao_Produto_X.pdf*).
3. Clique em **Enviar e Indexar**.
4. O sistema irá extrair os textos, quebrá-los em blocos lógicos e armazená-los na base vetorial. A partir desse momento, o assistente já saberá responder dúvidas baseadas nesse novo arquivo.

### Quem pode ver cada documento (campo "Finalidade")

Ao criar uma collection (base de documentos), você escolhe sua **Finalidade**:

* **Chat (pública)**: base que o site e o widget de chat público utilizam para responder aos visitantes.
* **Restrita ao MCP B2B (`mcp_b2b`)**: não aparece no chat público; é consultada exclusivamente pelos parceiros comerciais conectados via MCP B2B (ver Seção 6) **e também** pelo Admin logado.
* **Exclusiva do Admin (`admin`)**: visualizada estritamente pelo Administrador logado — nem o chat público, nem os parceiros do MCP B2B têm acesso a ela. Ideal para notas de custo, acordos contratuais e manuais confidenciais.

> **Ativação Independente por Finalidade**: O sistema mantém **uma collection ativa para cada finalidade**. Isso significa que você pode ter uma base ativa para o Chat, outra ativa para o MCP B2B e outra ativa para o Admin simultaneamente. Ao clicar em **Ativar** em uma collection, o sistema desativa apenas a collection anterior daquela mesma finalidade.

> **Download do documento original no chat (novo, 2026-10-05)**: a finalidade que você escolhe aqui também decide se o visitante pode baixar o arquivo original pelo card de download do chat (ver `docs/Manuais/HOWTO_USUARIO.md`). Documentos de collections **Chat (pública)** ficam disponíveis para download **sem login**, pois é o mesmo conteúdo que já aparece nas respostas do chat público. Documentos de collections **Restrita ao MCP B2B** ou **Exclusiva do Admin** nunca geram esse card — o assistente simplesmente não oferece o download nesses casos, mesmo para você logado como Admin.

### Organização e Navegação do Painel (`/admin/ingestao`)

- **Cards de Collections Ativas por Finalidade**: No topo da aba Configuração, três cards em destaque exibem instantaneamente qual collection está ativa para `Chat`, `MCP B2B` e `Admin`, com sua respectiva contagem de documentos.
- **Filtros Rápidos por Finalidade na Tabela**: A tabela de collections conta com abas para filtrar por `Todas`, `Chat`, `MCP B2B` ou `Admin`.
- **Ações Compactas com Ícones**: Os botões de ação foram modernizados com ícones compactos (Checkmark para ativar e Lixeira para excluir), evitando barras de rolagem horizontal.
- **Bubble Flutuante de Parâmetros Técnicos (Hover)**: Ao repousar o cursor sobre o card ou nome de qualquer collection, um portal inteligente exibe a quantidade exata de arquivos indexados e todos os parâmetros técnicos (modelo de embedding, dimensões, métrica, tamanho de chunk, overlap, HNSW, quantização e payload indexes).
- **Playground Comparativo Inteligente**: A ferramenta de teste e comparação de buscas do RAG restringe a comparação apenas entre collections de **mesma finalidade**, garantindo testes fidedignos ao cenário real de produção.
- **Filtros de Documentos Indexados**: A tabela de documentos indexados possui filtros avançados por **Nome do arquivo**, **Domínio**, **Collection** e **Intervalo de datas (Período)**.
- **Scroll Interno Responsivo**: As tabelas possuem rolagem interna independente (`overflow-y-auto`) com cabeçalhos fixos no topo (**sticky headers**), otimizando a navegação em telas de desktop e celulares (mobile).

### Pesquisando seus próprios documentos pelo chat (modo Admin)

Desde 2026-09-30, ao fazer login no site com um usuário Admin (`/conta/login`,
e-mail `admin@*`) e usar o **widget de chat normal** (não o playground de
`/admin/ingestao`), o assistente automaticamente passa a pesquisar em **todo**
o RAG — a collection `Chat` ativa, tudo que é `Restrita ao MCP B2B` e tudo
que é `Exclusiva do Admin` — em vez de só a collection pública. Não há botão
nem configuração extra: basta estar logado como Admin na mesma aba/sessão do
navegador. `# MVP`: a verificação usa o mesmo token mock de login do resto do
sistema (não é uma sessão criptográfica robusta) — ver `docs/ARCHITECTURE.md`
§6, decisão de 2026-09-30.

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

### 1. Seleção do Modelo Local (Ollama) & Características no Hover
O sistema roda em uma GPU própria de 16GB. Você pode escolher qual modelo atende seus clientes no momento:
* **Gemma 4 12B** (`gemma4:12b-it-q4_K_M`): Padrão de alta capacidade para conversação fluida, raciocínio de vendas e atendimento.
* **Llama 3.1 8B**: Recomendado para conversas formais, respostas diretas e rápida capacidade de síntese.
* **Qwen 2.5 7B**: Excelente para compreensão estruturada de tabelas, códigos de produtos e raciocínio lógico.

> **Painel de Características Técnicas no Hover**: Ao passar o cursor sobre qualquer card de modelo (local ou remoto do OpenRouter), um painel inteligente exibe instantaneamente a janela de contexto máxima (ex.: 128k tokens), modalidades suportadas (texto, imagem, áudio), provedores e precificação por milhão de tokens.

> **Como alterar**: Selecione o modelo desejado no menu suspenso e clique em **Ativar Modelo em Runtime**. A troca ocorre imediatamente sem derrubar o site.

---

### 2. Residência na VRAM & Otimização de Latência (Zero Cold Start)

Por padrão de fábrica, o Ollama descarrega modelos da memória de vídeo (VRAM) após **5 minutos** sem uso. Isso causava uma espera incômoda de 10 a 30 segundos para o visitante que enviasse uma mensagem após esse período de inatividade. O painel administrativo agora possui controle total de residência na GPU:

* **Tempo de Retenção na VRAM (`keep_alive`)**:
  * **Permanente / Indefinido (`-1`) — Padrão e Recomendado**: O modelo permanece fixo na GPU indefinidamente. Zero latência para qualquer mensagem, a qualquer momento.
  * **24 Horas (`24h`) / 1 Hora (`1h`) / 30 Minutos (`30m`) / 15 Minutos (`15m`)**: Mantém o modelo na memória durante o expediente e libera após o período ocioso.
  * **5 Minutos (`5m`)**: Padrão original do Ollama.
  * **Descarregar Imediatamente (`0`)**: Libera a VRAM logo após cada resposta (ideal apenas se precisar rodar outras cargas pesadas na GPU).
* **Pré-aquecimento Automático (*Warmup*)**:
  * Chave liga/desliga para carregar o modelo local na VRAM automaticamente durante a inicialização do backend em segundo plano, sem travar a subida do servidor.
* **Status da VRAM em Tempo Real & Ações Imediatas**:
  * **Badge de Status**: Exibe em tempo real se o modelo está carregado e o volume exato de memória de vídeo ocupado (ex.: `Modelo Carregado na VRAM (7.51 GB)`).
  * **Botão `⚡ Carregar na GPU`**: Força o carregamento imediato do modelo na memória de vídeo sem precisar esperar a primeira mensagem.
  * **Botão `🧹 Liberar VRAM`**: Força o descarregamento imediato do modelo da GPU, liberando a memória de vídeo para outras tarefas locais.
* **Persistência Permanente no Banco de Dados**:
  * Todas as alterações de temperatura, timeouts, limiares, provedores, `keep_alive` e `warmup` são gravadas permanentemente na tabela `app_settings` do PostgreSQL e restauradas automaticamente ao reiniciar o servidor.

---

### 3. Parametrização de Execução (Controles do Assistente)

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

#### 🔄 4. Fallback Automático de RAG (`RAG Domain Fallback`) — em `/admin/ingestao`
* **Onde fica**: movido do formulário de "Parâmetros de Execução" (`/admin/modelos`) para a seção "Regras de Busca & Isolamento de Domínios RAG" em `/admin/ingestao`, junto dos demais controles de RAG/crawler.
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

### Tabela de Produtos e Estoque por Centro de Distribuição (`/admin/produtos`)
* **Visualização de Estoque por CD**: A coluna de estoque exibe a quantidade total consolidada. Ao repousar o mouse sobre o valor, um tooltip detalhado apresenta a divisão física dos itens por filial ou centro de distribuição (ex.: CD-SP, CD-MG, CD-PR).
* **Agrupamento de Preços**: A tabela destaca visualmente o preço base do revendedor e o preço sugerido de venda ao consumidor final.
* **Fonte Única Autorizada no PostgreSQL**: Todos os dados do catálogo são mantidos e consultados diretamente no banco de dados relacional (`SalesCatalogClient`), sem duplicar ou poluir o RAG textual com arquivos sintéticos.

### Importação Inteligente de Catálogos (`/admin/produtos`)
* No botão de importação, **arraste** os arquivos para dentro da janela, **cole** com `Ctrl+V` (imagem copiada, arquivo copiado ou um texto copiado, que vira um `.txt`) ou use "Procurar Arquivos".
* Formatos aceitos: **PDF**, **imagens** (PNG, JPG, WEBP) e **texto** (TXT, MD, CSV). Pode misturar tipos e ir adicionando aos poucos; cada arquivo da lista tem um ✕ para remover. Outros formatos são recusados com aviso.
* Arquivos de texto são lidos em trechos pelo modelo local (sem fallback de visão, pois não há imagem); o intervalo de páginas só vale para PDFs.
* Os produtos extraídos sempre passam pela tela de conferência antes de serem gravados.

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

---

## 📉 Dashboards e Gráficos Dinâmicos via Chat (`/admin/dashboards`)

Exclusivo para quem está logado como Admin: além de responder perguntas, o
**próprio widget de chat** pode gerar gráficos analíticos sob demanda a
partir dos dados reais do catálogo (produtos, estoque, pedidos) no
PostgreSQL — sem precisar abrir nenhuma outra tela.

* **Como pedir um gráfico**: peça normalmente no chat, logado como Admin —
  ex.: *"Mostre um gráfico de barras com o estoque total por centro de
  distribuição"* ou *"Quais os 5 produtos mais caros? faça um gráfico de
  pizza"*. Se você não estiver logado como Admin, o assistente explica que
  esse recurso é exclusivo para administradores.
* **Como funciona**: o assistente monta uma consulta SQL de leitura
  (somente `SELECT`, nunca grava nem altera dados) a partir do seu pedido,
  executa contra o catálogo e devolve o resultado como um card de gráfico
  interativo (barras, linha, pizza, área ou rosca) diretamente na
  conversa.
* **Persistência Automática**: todo gráfico gerado é salvo permanentemente
  e aparece na tela `/admin/dashboards` (menu ⚙️ → "Dashboards"), onde você
  pode revisitar, fixar ou remover gráficos anteriores sem precisar pedir
  de novo pelo chat.

---

## 📈 Métricas de Tokens, Custos e Chats Encerrados (`/admin/metricas`)

Acessível pelo menu de administração (ícone ⚙️ no topo → "Métricas & Custos IA") para usuários com perfil `Admin`.

### 1. Painel de Indicadores (KPIs)
O dashboard consolida em tempo real:
* **Tokens Internos (GPU Local)**: Volume total de tokens de prompt e resposta processados no servidor com Ollama. Apresenta o badge de custo zero (**R$ 0,00**), demonstrando a economia de infraestrutura própria.
* **Tokens Externos (OpenRouter)**: Volume total de tokens processados na nuvem.
* **Custo Total Acumulado (USD)**: Gasto financeiro real acumulado no período selecionado.
* **Custo de Entrada (Prompt USD)**: Valor segregado gasto no envio de contexto, perguntas e dados do RAG para a nuvem.
* **Custo de Saída (Resposta USD)**: Valor segregado gasto na geração de texto pelos modelos externos.
* **Chats Encerrados**: Quantidade de sessões finalizadas com sucesso.

### 2. Filtros de Período e Seleção de Data
Selecione o horizonte temporal desejado no topo:
* **Hoje**: Atendimentos encerrados desde 00:00 UTC do dia corrente.
* **7 Dias**: Atendimentos dos últimos 7 dias.
* **30 Dias**: Atendimentos dos últimos 30 dias.
* **Tudo**: Histórico acumulado completo.
* **📅 Por Dia**: Abre um calendário visual nativo para você escolher qualquer data específica do passado ou presente. Os cartões de indicadores e a tabela diária passam a exibir exclusivamente os dados consolidados do dia escolhido.
* **🔄 Botão Atualizar**: Força a sincronização imediata dos dados com o backend com proteção anti-cache, exibindo feedback tátil animado, notificação toast e o horário exato da última atualização.

### 3. Tabela de Detalhamento Diário
Apresenta o agrupamento dia a dia ordenado por data de encerramento (`date(encerrada_em)`), com o número de chats finalizados, contagem segregada de tokens locais e remotos (entrada/saída) e os custos monetários correspondentes.

### 4. Ciclo de Vida do Atendimento e Encerramento
* **Encerramento Manual**: O visitante pode encerrar o atendimento a qualquer momento clicando no botão 🏁 **Encerrar atendimento** no topo do widget de chat. A sessão é marcada como `encerrada` com motivo `manual_usuario` e contabilizada nos relatórios.
* **Encerramento Automático por Inatividade**: O servidor executa um serviço em segundo plano (`inactivity_closure_worker`) que identifica conversas abertas sem nenhuma interação nos últimos 30 minutos e as encerra automaticamente com motivo `inatividade`.
