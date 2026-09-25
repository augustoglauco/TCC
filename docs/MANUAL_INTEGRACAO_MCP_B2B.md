# 📖 Manual de Integração MCP B2B (Model Context Protocol)
> **Guia para Desenvolvedores e Empresas Parceiras**  
> *Versão do Protocolo: MCP v1.x / v2.x (Server-Sent Events — SSE sobre HTTPS)*

---

## 1. Visão Geral

O **Servidor MCP B2B** expõe os dados de produtos, estoques, manuais e ferramentas comerciais da empresa para integração direta com **Agentes de IA, Marketplaces, ERPs e IAs parceiras**.

Através do padrão **Model Context Protocol (MCP)**, sistemas parceiros podem:
* Consultar informações técnicas e manuais em tempo real (Recursos/RAG B2B).
* Validar compatibilidade entre equipamentos e acessórios.
* Gerar cotações comerciais automatizadas com descontos por volume e frete.
* Efetuar reservas de estoque e ordens de compra transacionais.

---

## 2. Dados de Conexão & Autenticação

### Endereço do Servidor (Endpoint)
```http
https://augustoglauco.duckdns.org:8443/mcp
```

### Autenticação
A comunicação é protegida por **Criptografia TLS (HTTPS)** e **Autenticação via Bearer Token**.

Toda requisição para o servidor (inicialização SSE, listagem e chamadas de ferramentas) **DEVE** conter o seguinte cabeçalho HTTP:

```http
Authorization: Bearer <SUA_CHAVE_DE_PARCEIRO>
```

> ⚠️ **Atenção:** Mantenha sua chave de parceiro em segredo. Se a chave for omitida ou for inválida, o servidor retornará um erro **`HTTP 401 Unauthorized`**.

---

## 3. Capacidades Expostas (Capabilities)

### 3.1 Recursos (Resources — Somente Leitura)

Os recursos fornecem acesso direto aos dados estruturados e à base de conhecimento (RAG B2B exclusivo):

| Recurso | Descrição |
| :--- | :--- |
| `catalog://produtos` | Catálogo de produtos, dimensões, pesos e especificações. |
| `inventory://estoque` | Saldo de estoque disponível em tempo real. |
| `pricing://tabelas` | Tabelas de preços vigentes e regras de desconto por volume. |
| `docs://manuais` | Esquemas elétricos, guias de instalação e termos de garantia. |

---

### 3.2 Ferramentas (Tools — Execução de Ações)

O servidor dispõe das seguintes ferramentas transacionais:

#### 1. `validar_compatibilidade`
Verifica se um acessório ou peça é compatível com um equipamento principal.
* **Argumentos:**
  * `produto_id` *(int, obrigatório)*: ID do produto principal (ex.: Gerador a Diesel).
  * `acessorio_id` *(int, obrigatório)*: ID da peça ou acessório.
* **Retorno:** Booleano de compatibilidade com detalhes técnicos e restrições.

#### 2. `consultar_frete`
Calcula o valor do frete e o prazo de entrega para o CEP de destino.
* **Argumentos:**
  * `itens` *(array, obrigatório)*: Lista de objetos `{"produto_id": int, "quantidade": int}`.
  * `cep_destino` *(string, obrigatório)*: CEP com 8 dígitos (ex.: `"01310-100"`).
* **Retorno:** Custo total do frete, transportadora e estimativa em dias úteis.

#### 3. `cotar`
Gera uma cotação comercial com aplicação automática de descontos e prazos de pagamento.
* **Argumentos:**
  * `itens` *(array, obrigatório)*: Lista de objetos `{"produto_id": int, "quantidade": int}`.
  * `uf` *(string, opcional)*: Sigla do estado de destino para cálculo tributário (ex.: `"SP"`).
* **Retorno:** Cotação detalhada (preço unitário, descontos aplicados, total e validade).

#### 4. `reservar_pedido`
Efetua uma reserva formal no estoque para o parceiro ou cliente final.
* **Argumentos:**
  * `itens` *(array, obrigatório)*: Lista de objetos `{"produto_id": int, "quantidade": int}`.
  * `cep_destino` *(string, obrigatório)*: CEP de entrega.
  * `cliente_final` *(string, opcional)*: Razão Social ou Nome do cliente final.
* **Retorno:** Número do pedido de reserva, prazo de garantia da reserva e status de confirmação.

---

## 4. Guia Prático de Integração (Exemplo em Python)

Para integrar sua aplicação em Python, utilize a biblioteca oficial do MCP:

```bash
pip install "mcp>=2.0" httpx
```

### Exemplo de Código Completo:

```python
import asyncio
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

# Configurações de Conexão
MCP_URL = "https://augustoglauco.duckdns.org:8443/mcp"
PARNER_KEY = "SUA_CHAVE_DE_PARCEIRO_AQUI"

async def executar_integracao_b2b():
    # 1. Configura o cliente HTTP com a chave no cabeçalho Authorization
    headers = {"Authorization": f"Bearer {PARNER_KEY}"}
    
    async with create_mcp_http_client(headers=headers) as http_client:
        # 2. Conecta ao transporte SSE do servidor MCP
        async with streamable_http_client(MCP_URL, http_client=http_client) as (leitura, escrita):
            async with ClientSession(leitura, escrita) as session:
                
                # 3. Inicializa o handshake com o servidor
                servidor_info = await session.initialize()
                print(f"✅ Conectado com sucesso ao servidor: {servidor_info.server_info.name}")

                # 4. Listar ferramentas disponíveis
                ferramentas = await session.list_tools()
                print(f"🔧 Ferramentas disponíveis: {[t.name for t in ferramentas.tools]}")

                # 5. Executar uma Cotação Comercial
                print("\n🛒 Solicitando cotação de 2 unidades do produto #1...")
                resultado_cotacao = await session.call_tool(
                    "cotar", 
                    arguments={
                        "itens": [{"produto_id": 1, "quantidade": 2}],
                        "uf": "SP"
                    }
                )
                
                print("📄 Resposta da Cotação:")
                print(resultado_cotacao.structured_content or resultado_cotacao.content)

if __name__ == "__main__":
    asyncio.run(executar_integracao_b2b())
```

---

## 5. Testando a Conexão com o Script Utilitário

O repositório fornece um script utilitário CLI para testar rapidamente se o seu ambiente e sua chave estão funcionando antes de escrever o código de produção:

```bash
python backend/scripts/cliente_mcp_b2b.py \
    --url https://augustoglauco.duckdns.org:8443/mcp \
    --chave <SUA_CHAVE_DE_PARCEIRO>
```

**Saída esperada:**
```text
Sem chave: HTTP 401 ✅
Com chave: initialize ok (mcp-b2b-server) ✅
Com chave: tools/list ok (4 ferramentas) ✅
Com chave: tools/call cotar ok ✅
{
  "sucesso": true,
  "itens": [...],
  "valor_total": ...
}
```

---

## 6. Tratamento de Erros e Resolução de Problemas

| Sintoma / Erro | Causa Provável | Solução |
| :--- | :--- | :--- |
| **`HTTP 401 Unauthorized`** | Chave ausente ou incorreta no cabeçalho `Authorization`. | Verifique se enviou `Bearer <sua-chave>` corretamente. |
| **`Connection Refused / Timeout`** | Servidor fora do ar ou firewall bloqueando a porta 8443. | Verifique se a porta 8443 está liberada na sua rede de saída. |
| **`SSL Certificate Error`** | Certificado TLS não reconhecido pela aplicação cliente. | Garanta que o SO da sua aplicação possui a cadeia CA padrão atualizada. |
| **`Tool Error: Produto não encontrado`** | ID de produto inexistente enviado nos argumentos. | Consulte os IDs válidos via recurso `catalog://produtos`. |

---
*Em caso de dúvidas técnicas sobre a integração B2B ou solicitação de renovação de chaves, entre em contato com a equipe de suporte de TI.*
