# 👤 Manual do Usuário e Cliente (How-To)

> **Público-Alvo**: Clientes, Visitantes e Usuários Finais do Website.  
> **Objetivo**: Apresentar de forma clara e prática todas as funcionalidades disponíveis no site e os recursos do **Assistente Virtual Multimodal** (chat por texto, áudio, imagens e cards interativos).

---

## 📋 Sumário

1. [🌐 O que você pode fazer no Website](#-o-que-você-pode-fazer-no-website)
2. [💬 Como usar o Assistente Virtual (Widget de Chat)](#-como-usar-o-assistente-virtual-widget-de-chat)
3. [🎨 Recursos Multimodais no Chat (Texto, Áudio e Imagem)](#-recursos-multimodais-no-chat-texto-áudio-e-imagem)
4. [🎯 O que você pode pedir ao Chat (Por Área de Atendimento)](#-o-que-você-pode-pedir-ao-chat-por-área-de-atendimento)
5. [📦 Interação com Cards Ricos no Chat](#-interação-com-cards-ricos-no-chat)
6. [🙋‍♂️ Atendimento Humano e Suporte Especializado](#-atendimento-humano-e-suporte-especializado)

---

## 🌐 O que você pode fazer no Website

A nossa plataforma foi projetada para oferecer uma experiência completa de compras, suporte e atendimento. Veja abaixo todos os recursos que você pode explorar diretamente pelo menu de navegação do site:

### 🛍️ 1. Catálogo e Busca de Produtos (`/produtos`)
* **Navegar pelo Catálogo**: Visualize todos os produtos disponíveis em uma grade responsiva com **rolagem interna** (sem estourar a tela do seu celular ou computador).
* **Filtros e Busca**: Utilize a barra de pesquisa para buscar produtos por nome, código ou palavra-chave.
* **Detalhes do Produto (`/produtos/[id]`)**: Veja especificações técnicas, preço, fotos em alta resolução e disponibilidade em estoque.
* **"Cotar com Assistente"**: Na página de um produto, clique no botão dedicado para abrir o chat já falando daquele item.

### 👤 2. Conta (`/conta/login`, `/conta/cadastro`, `/conta/perfil`)
* **Criar conta**: cadastre-se em `/conta/cadastro` com nome, e-mail e senha (senha de demonstração fixa: `12345`).
* **Login**: entre em `/conta/login` — sem conta, o sistema ainda funciona como visitante anônimo, mas fazendo login o assistente lembra seu histórico de compras e pedidos.

### 🛒 3. Pedidos e Carrinho de Compras (`/pedidos`)
* **Carrinho de Compras**: Adicione produtos, ajuste quantidades e veja o resumo do seu pedido.
* **Histórico de Pedidos (`/pedidos/historico`)**: Acompanhe seus pedidos e o status de cada um: `reservado` (estoque separado, aguardando o pagamento), `venda_concluida` (comprovante validado) ou `pagamento_divergente` (o valor do comprovante não confere).

### 📅 4. Agendamentos de Visita (`/agendamentos`)
* Visualize a lista de todas as reuniões ou visitas presenciais agendadas entre você e a nossa equipe (marcadas via site ou através do chat assistente).
* Os botões "Agendar Visita pelo Chat" já abrem o assistente com a mensagem preenchida com seu nome e e-mail (se você estiver logado), para não precisar digitar tudo de novo.

### 📖 5. Central de Suporte e FAQ (`/suporte`)
* Perguntas frequentes em cartões, sobre pedidos, garantia, manuais e agendamento de visitas, com um atalho para abrir o assistente quando a resposta não estiver ali.

### ☎️ 6. Contato (`/contato`) e Perfil (`/conta/perfil`)
* **Contato**: e-mail, telefone e endereço da empresa.
* **Perfil** (logado): seus dados, a classificação que o assistente atribuiu a você (Cliente recorrente, Esporádico ou Lead) e seus pedidos e reservas recentes, com link para o histórico completo.

---

## 💬 Como usar o Assistente Virtual (Widget de Chat)

O **Assistente Virtual** é um robô inteligente disponível **em todas as páginas do site**. 

* **Como abrir**: Basta clicar no **ícone flutuante de balão de conversa** localizado no canto inferior direito da tela.
* **Funcionamento**: Você pode usá-lo tanto como visitante anônimo quanto logado na sua conta. Se estiver logado, ele lembrará das suas conversas anteriores e pedidos recentes!
* **Botões do chat**: **Falar com atendente humano** (veja a última seção), **Encerrar atendimento** (finaliza a sessão; conversas paradas por 30 minutos também são encerradas sozinhas) e **Limpar histórico** (apaga as mensagens e a memória da conversa). Visitantes anônimos perdem a conversa ao fechar o navegador; logado, ela é retomada na próxima visita.
* **Indicadores de Modelo**: Respostas do modelo local (GPU) são exibidas no balão cinza padrão. Quando o assistente consulta o modelo especialista em nuvem para perguntas externas ou mais complexas, o balão de resposta recebe um **destaque em vermelho clarinho**.

---

## 🎨 Recursos Multimodais no Chat (Texto, Áudio e Imagem)

Você não precisa apenas digitar! O nosso assistente entende **Texto**, **Voz (Áudio)** e **Fotos (Imagens)**:

---

### 1. 💬 Mensagens de Texto
* Digite qualquer pergunta ou saudação (ex: *"boa noite"*, *"olá"*) no campo de mensagem e pressione **Enter** ou clique na seta de enviar. Saudações genéricas são respondidas de forma imediata e acolhedora, sem poluir sua tela com listas desnecessárias.
* O assistente responde em tempo real. Você verá as respostas sendo "digitadas" na tela.

---

### 2. 🎤 Mensagens de Voz (Áudio)
* Não quer digitar? Clique no botão do **Microfone** no chat.
* Fale a sua dúvida normalmente (ex.: *"Qual o prazo de entrega para o CEP 01001-000?"*).
* Clique novamente no botão para finalizar a gravação. O assistente converterá a sua fala em texto automaticamente e responderá em seguida!

---

### 3. 📷 Envio de Fotos e Imagens
Clique no botão de **Anexo / Câmera** para enviar fotos do seu computador ou celular. O sistema suporta dois tipos de uso:

#### 📄 A) Envio de Comprovantes e Documentos (Leitura Automática / OCR)
* Envie fotos ou arquivos legíveis de comprovantes de pagamento, notas ou documentos.
* A inteligência artificial lerá o texto da imagem e validará as informações do seu atendimento.

#### 🔍 B) Busca de Produtos por Foto (Similaridade Visual)
* Viu um produto ou peça e não sabe o nome exato?
* Tire uma foto do produto e envie no chat. O assistente procurará no nosso catálogo itens iguais ou visualmente semelhantes ao da foto!

---

## 🎯 O que você pode pedir ao Chat (Por Área de Atendimento)

O assistente é treinado para resolver solicitações em 4 domínios principais:

---

### 1. 🛍️ Vendas e Cotações B2B
* **Consulta de Estoque**: *"Vocês têm o modelo X em estoque na quantidade de 10 unidades?"*
* **Cálculo de Frete**: *"Quanto fica o frete para o CEP 04538-133?"*
* **Cotações e Orçamentos**: *"Quero uma cotação para 50 peças do item Y com desconto de empresa."*
* **Fechamento do Pedido**: o assistente confirma produto, quantidade e total e, se você estiver logado, indica como finalizar na página **Pedidos** do site, onde o pedido vira uma reserva de estoque. Depois, você pode enviar o comprovante de pagamento pelo próprio chat para efetivar a venda. (A criação da reserva diretamente pelo chat ainda não está implementada.)

---

### 2. 🔧 Suporte Técnico
* **Dúvidas de Instalação**: *"Como faço a instalação inicial do equipamento Z?"*
* **Resolução de Problemas**: *"O meu aparelho está piscando uma luz vermelha, o que significa?"*
* **Manuais Técnicos**: O assistente consulta os manuais oficiais da fábrica e responde com o passo-a-passo exato para você.

---

### 3. 💬 Atendimento Geral e Dúvidas Institucionais
* **Horários e Localização**: *"Qual o horário de atendimento da loja física?"*
* **Políticas da Empresa**: *"Como funciona a política de troca e devolução?"*

---

### 4. 📅 Agendamento de Visita ou Reunião
* **Agendar Reunião**: *"Gostaria de agendar uma visita técnica para a próxima terça-feira às 14h."*
* **Integração Automática**: O assistente verifica a disponibilidade, cria o compromisso na agenda oficial e exibe a confirmação diretamente na tela do chat!

---

## 📦 Interação com Cards Ricos no Chat

Em vez de apenas mensagens de texto longas, o assistente pode enviar **Cards Interativos** direto no chat:

* **Card de Produto**: foto, preço atual e disponibilidade em estoque; ao clicar, abre a página do produto no site.
* **Card de Cotação**: a proposta comercial com os descontos aplicados; ao clicar, abre a página do produto para você seguir com o pedido.
* **Card de Agendamento**: Exibe a data, hora e link do agendamento confirmado da sua visita.
* **Card de Download de Documento** (novo, 2026-10-05): quando sua pergunta bate com alta confiança num manual, catálogo ou outro documento da nossa base de conhecimento, o assistente anexa um card com o nome do arquivo, o tamanho e um botão **"📥 Baixar Documento"** para você baixar o arquivo original completo — sem precisar de login.

---

## 🙋‍♂️ Atendimento Humano e Suporte Especializado

Se em algum momento o assistente não conseguir resolver a sua dúvida ou se você solicitar explicitamente para falar com um atendente:

1. O **Monitor de Tom** da nossa plataforma identificará a sua necessidade de suporte humano.
2. O chat exibirá um banner de aviso, por exemplo: *"Identificamos urgência na sua solicitação. Um atendente humano foi notificado e já está ciente do seu caso."* (ou, no caso de insatisfação, *"Percebemos sua insatisfação e lamentamos o transtorno..."*).
3. Sua conversa entra na **fila de atendimento** da equipe (a IA para de responder). Um atendente assume o chat pela Central de Atendimento e conversa com você na mesma janela, com todo o histórico à vista, para que você não precise repetir o que já foi dito.
4. Você também pode pedir direto, por exemplo "quero falar com um atendente humano". Ao final, o atendente encerra ou devolve a conversa ao assistente.
