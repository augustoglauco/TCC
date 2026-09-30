# Cliente Independente MCP B2B

Aplicação cliente independente desenvolvida em Python + Streamlit para conectar e demonstrar o consumo do Servidor MCP B2B corporativo (`backend/src/app/mcp_server/b2b.py`, R12). Projeto isolado: não importa nem depende de código do `backend/`.

## Como Executar

### 1. Instalar dependências
```bash
cd cliente-b2b
pip install -r requirements.txt
```

### 2. Executar os testes
```bash
pytest tests/
```

### 3. Subir o servidor MCP B2B (no `backend/`, com Postgres/Qdrant no ar)
```bash
cd ../backend
.venv/bin/python scripts/run_mcp_b2b_server.py
```
Escuta por padrão em `http://127.0.0.1:8100/mcp` (`MCP_B2B_HOST`/`MCP_B2B_PORT`
no `.env`) e exige uma chave de `MCP_B2B_PARTNER_KEYS`.

### 4. Iniciar a interface Streamlit
```bash
cd ../cliente-b2b
streamlit run src/app.py
```
Informe a URL do servidor (default `http://127.0.0.1:8100/mcp`) e a chave do
parceiro configurada em `MCP_B2B_PARTNER_KEYS` na barra lateral.

## Limitações desta demonstração (MVP)

- A ferramenta `reservar_pedido` do servidor exige um centro de distribuição
  por item; este cliente aplica um único CD informado na aba de pedido a
  todos os itens do carrinho (sem split de pedido entre centros).
- A busca em manuais (`manuais://busca/{domain}`) exige escolher um dos
  domínios de atendimento (vendas/suporte/atendimento).
