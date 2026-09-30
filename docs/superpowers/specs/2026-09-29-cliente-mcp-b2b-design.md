# Design — Cliente Independente MCP B2B com Interface Web (Streamlit)

> Spec resultante de sessão de brainstorming com o desenvolvedor em 2026-09-29.
> Define a arquitetura, estrutura e implementação de um projeto cliente independente (`cliente-b2b/`) para conectar, demonstrar e consumir o servidor MCP B2B provido pela empresa (R12, Fase 5).

---

## 1. Visão Geral e Objetivos

O ecossistema já disponibiliza um servidor MCP B2B corporativo em `backend/src/app/mcp_server/b2b.py` que expõe recursos de catálogo/estoque/preços/manuais e ferramentas transacionais de cotação, frete, compatibilidade e reserva de pedidos via transporte HTTP Streamable protegido por Bearer Token.

O objetivo deste novo projeto é fornecer uma aplicação cliente independente e simples que atue como o **Portal do Parceiro / Cliente B2B**, permitindo:
1. **Conexão e Autenticação MCP**: Configurar a URL do servidor MCP (local ou domínio DuckDNS com HTTPS/Caddy) e a chave do parceiro comercial.
2. **Consulta a Recursos (MCP Resources)**: Explorar o catálogo de produtos (`catalogo://`), saldos de estoque por centro de distribuição (`estoque://`), tabelas de preços com faixas de desconto (`precos://`) e pesquisa semântica em manuais técnicos via RAG (`manuais://`).
3. **Execução de Ferramentas Transacionais (MCP Tools)**:
   - Simular cotações comerciais com cálculo progressivo de descontos por volume (`cotar`).
   - Consultar frete e prazos de entrega estimados por CEP (`consultar_frete`).
   - Validar compatibilidade técnica entre produtos (`validar_compatibilidade`).
   - Efetuar a emissão e fechamento de pedidos com baixa real de estoque (`reservar_pedido`).
4. **Inspeção de Protocolo (Auditoria/Demonstração)**: Permitir a visualização dos payloads brutos JSON-RPC trocados entre o cliente e o servidor MCP para fins de validação no TCC.

---

## 2. Estrutura de Diretórios do Projeto (`cliente-b2b/`)

O projeto residirá em uma pasta isolada e desacoplada do backend principal:

```
cliente-b2b/
├── pyproject.toml              # Metadados e dependências do projeto (uv/pip)
├── requirements.txt            # Dependências em formato pip
├── README.md                   # Documentação de execução e guia de uso
├── src/
│   ├── __init__.py
│   ├── client.py               # Motor MCP assíncrono (sessão, tools e resources)
│   └── app.py                  # Aplicação Streamlit (Interface gráfica reativa)
└── tests/
    ├── __init__.py
    └── test_client.py          # Testes unitários do cliente MCP com mocks
```

---

## 3. Arquitetura da Camada do Cliente MCP (`src/client.py`)

A classe `B2BMCPClient` centraliza a lógica de comunicação via protocolo MCP oficial (`mcp>=2.0` Python SDK) e `httpx`:

### 3.1 Inicialização e Conexão
- **Parâmetros**: `server_url: str`, `auth_token: str`, `timeout_seconds: float = 20.0`.
- **`conectar() -> dict`**:
  - Cria cliente HTTP streamable com cabeçalho `Authorization: Bearer <auth_token>`.
  - Executa handshake `ClientSession.initialize()` e obtém `ServerCapabilities` e `serverInfo` (`name`, `version`).
  - Lista as ferramentas disponíveis (`session.list_tools()`) e recursos (`session.list_resources()`).
  - Retorna resumo com status de conexão e ferramentas encontradas.
  - Trata explicitamente HTTP 401 (chave recusada) e falhas de conexão de rede.

### 3.2 Consumo de Recursos (Resources)
- **`obter_catalogo() -> list[dict]`**: Lê `catalogo://` e devolve a lista de produtos (id, nome, categoria, peso_kg, dimensoes).
- **`obter_estoque() -> list[dict]`**: Lê `estoque://` e devolve os centros de distribuição e estoques por produto.
- **`obter_tabela_precos() -> list[dict]`**: Lê `precos://` e devolve preços unitários e faixas de desconto por volume.
- **`pesquisar_manuais(query: str, top_k: int = 5) -> list[dict]`**: Lê `manuais://?query=...` ou executa a busca textual em documentações técnicas.

### 3.3 Consumo de Ferramentas (Tools)
- **`cotar(itens: list[dict]) -> dict`**:
  - Argumentos: `itens: [{"produto_id": int, "quantidade": int}]`.
  - Retorna: itens com preço unitário de tabela, percentual de desconto aplicado, preço líquido, subtotal e total da cotação.
- **`consultar_frete(cep_destino: str, itens: list[dict]) -> dict`**:
  - Argumentos: `cep_destino: str`, `itens: [{"produto_id": int, "quantidade": int}]`.
  - Retorna: região de entrega, prazo em dias úteis, custo base, custo por peso e valor total do frete.
- **`validar_compatibilidade(produto_id_a: int, produto_id_b: int) -> dict`**:
  - Argumentos: IDs dos produtos.
  - Retorna: booleano `compativeis` e mensagem detalhada de compatibilidade.
- **`reservar_pedido(itens: list[dict], cep_entrega: str, identificador_externo: str | None = None) -> dict`**:
  - Argumentos: itens, CEP e identificador único de compra do parceiro.
  - Retorna: número do pedido gerado, valor total, status de reserva e confirmação da baixa em estoque.

---

## 4. Arquitetura da Interface Streamlit (`src/app.py`)

A aplicação Streamlit será interativa e orientada a tarefas:

### 4.1 Barra Lateral (Configuração e Estado)
- Entrada da URL do Servidor MCP (default: `http://127.0.0.1:8000/mcp/b2b`).
- Entrada da Chave do Parceiro / Bearer Token (default: `parceiro_alpha_segredo_123`).
- Botão **"Conectar ao Servidor"**:
  - Inicializa a sessão e salva o cliente em `st.session_state`.
  - Exibe badge de status: 🟢 **Conectado** ou 🔴 **Desconectado / Erro de Autenticação**.
- Checkbox de depuração: **"Modo Desenvolvedor (Exibir JSON-RPC)"** para auditar a resposta crua das ferramentas.

### 4.2 Abas Principais

1. **Aba 1: 📦 Catálogo & Recursos**
   - Carrega em tempo real os dados de `catalogo://`, `estoque://` e `precos://`.
   - Exibe tabela filtrável com ID, Nome, Categoria, Preço Base e Estoque Total.
   - Seção de Pesquisa Técnica: campo para pesquisar termos em `manuais://` com exibição de trechos relevantes.

2. **Aba 2: 💰 Cotação B2B**
   - Interface dinâmica para selecionar produto por nome/ID e informar quantidade.
   - Permite adicionar múltiplos itens na cesta de cotação.
   - Botão **"Calcular Cotação"**.
   - Exibe cards com métricas financeiras (Subtotal Bruto, Desconto Total, Total Líquido) e tabela discriminada de itens.

3. **Aba 3: 🚚 Consulta de Frete**
   - Entrada de CEP de destino (com máscara ou validação de 8 dígitos).
   - Utiliza os itens da cotação atual ou permite especificar itens avulsos.
   - Botão **"Consultar Frete"**.
   - Exibe prazo estimado de entrega (dias úteis), região identificada e custo total do frete.

4. **Aba 4: 🔍 Validador de Compatibilidade**
   - Dois selects contendo os produtos do catálogo.
   - Botão **"Verificar Compatibilidade"**.
   - Exibe alerta visual: verde com ícone de sucesso quando compatíveis, ou amarelo/vermelho com o motivo técnico caso incompatíveis.

5. **Aba 5: 🛒 Emissão de Pedido B2B**
   - Resumo da cesta de itens a serem comprados e CEP de entrega.
   - Campo para Identificador Externo do Parceiro (ex.: `PEDIDO-EXT-2026-001`).
   - Checkbox de confirmação de compra consciente ("Confirmo que esta operação reservará estoque real").
   - Botão **"Efetivar Pedido"**.
   - Exibe cartão de confirmação com ID do pedido gerado, valor total faturado e status confirmado.

---

## 5. Estratégia de Testes Automatizados (`tests/test_client.py`)

A suíte de testes unitários utilizará `pytest` e `pytest-asyncio` com fakes/mocks da `ClientSession` do MCP, assegurando:
1. `test_conectar_sucesso`: valida handshake, inicialização e carregamento de ferramentas.
2. `test_conectar_chave_invalida_retorna_erro`: valida rejeição graciosa em caso de HTTP 401.
3. `test_obter_catalogo_recurso`: valida leitura do recurso `catalogo://`.
4. `test_cotar_ferramenta`: valida chamada à tool `cotar` com payload estruturado de retorno.
5. `test_consultar_frete_ferramenta`: valida chamada à tool `consultar_frete`.
6. `test_validar_compatibilidade_ferramenta`: valida chamada à tool `validar_compatibilidade`.
7. `test_reservar_pedido_ferramenta`: valida chamada à tool `reservar_pedido`.

---

## 6. Critérios de Sucesso
- Projeto totalmente contido na pasta `cliente-b2b/`, sem acoplamento a código do backend.
- Execução local simples via `streamlit run src/app.py`.
- 100% dos testes unitários do cliente em `tests/test_client.py` passando.
- Demonstração funcional de ponta a ponta com o servidor MCP B2B em execução.
