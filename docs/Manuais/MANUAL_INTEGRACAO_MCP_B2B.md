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

Os recursos fornecem acesso direto aos dados estruturados e à base de conhecimento (RAG B2B). As respostas são JSON.

| URI | Descrição |
| :--- | :--- |
| `catalogo://produtos{?categoria}` | Catálogo de produtos, com filtro opcional por categoria. |
| `catalogo://produtos/{produto_id}` | Detalhe de um produto: dimensões, peso e especificações. |
| `estoque://produtos/{produto_id}` | Saldo de estoque por centro de distribuição. |
| `precos://produtos/{produto_id}` | Preço, promoção vigente e descontos por volume. |
| `manuais://busca/{domain}{?query}` | Busca semântica em manuais e documentação técnica. `domain` é `vendas`, `suporte` ou `atendimento`. Alcança o acervo público do chat e o conteúdo exclusivo do canal B2B. |

---

### 3.2 Ferramentas (Tools — Execução de Ações)

O servidor dispõe de cinco ferramentas:

#### 1. `validar_compatibilidade`
Verifica se dois produtos do catálogo são compatíveis. A relação é simétrica.
* **Argumentos:** `produto_id` *(int)* e `produto_relacionado_id` *(int)*, ambos obrigatórios.

#### 2. `consultar_frete`
Estima custo e prazo de frete para um CEP, a partir do peso total dos itens. É uma estimativa interna, sem consulta a transportadora.
* **Argumentos:** `cep` *(string, 8 dígitos, com ou sem hífen)* e `itens` *(array de `{"produto_id": int, "quantidade": int}`)*.
* **Retorno:** CEP, peso total em kg, custo estimado e prazo em dias.

#### 3. `cotar`
Gera uma cotação com o desconto por volume aplicado automaticamente.
* **Argumentos:** `itens` *(array de `{"produto_id": int, "quantidade": int}`)*.
* **Retorno:** por item, preço unitário, percentual de desconto aplicado e subtotal, mais o total.

#### 4. `reservar_pedido`
Cria uma reserva e baixa o estoque do centro de distribuição indicado.
* **Argumentos:** `itens` *(array de `{"produto_id": int, "quantidade": int, "centro_distribuicao": string}`)*.
* **Retorno:** `id` do pedido, `status` (`reservado`), `criado_em` e os itens reservados.
* O pedido fica registrado em nome do **seu cadastro de parceiro** (o e-mail ligado à sua chave), e não como visitante anônimo.
* O `preco_unitario` de cada item é o preço **já com o desconto por volume** da faixa atingida (mesma regra de `cotar`), com até 4 casas decimais (ex.: `"123.4050"`). O valor a pagar é a soma de `preco_unitario × quantidade`, e é contra ele que o comprovante é validado.
* Quantidade acima do estoque do centro é recusada.

#### 5. `converter_reserva_venda`
Converte uma reserva em venda concluída, validando o comprovante de pagamento com um modelo multimodal.
* **Argumentos:** `pedido_id` *(string)*, `comprovante_base64_ou_texto` *(string: texto ou arquivo em base64)* e `nome_arquivo` *(string, opcional; padrão `comprovante.txt`)*.
* **Retorno:** o resultado da conversão (venda concluída ou pagamento divergente), com o parecer da validação.

> **Limitações do protótipo:** uma chave estática por parceiro, sem OAuth, limite de uso nem auditoria completa; reserva sem controle de concorrência. Decisões em `docs/ARCHITECTURE.md` §6.

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
PARTNER_KEY = "SUA_CHAVE_DE_PARCEIRO_AQUI"

async def executar_integracao_b2b():
    # 1. Configura o cliente HTTP com a chave no cabeçalho Authorization
    headers = {"Authorization": f"Bearer {PARTNER_KEY}"}
    
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
                        "itens": [{"produto_id": 1, "quantidade": 2}]
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
Com chave: initialize ok (mcp-b2b) ✅
Com chave: tools/list ok (5 ferramentas) ✅
Com chave: tools/call cotar ok ✅
{
  "itens": [...],
  "total": ...
}
```

---

## 6. Tratamento de Erros e Resolução de Problemas

| Sintoma / Erro | Causa Provável | Solução |
| :--- | :--- | :--- |
| **`HTTP 401 Unauthorized`** | Chave ausente ou incorreta no cabeçalho `Authorization`. | Verifique se enviou `Bearer <sua-chave>` corretamente. |
| **`Connection Refused / Timeout`** | Servidor fora do ar ou firewall bloqueando a porta 8443. | Verifique se a porta 8443 está liberada na sua rede de saída. |
| **`SSL Certificate Error`** | Certificado TLS não reconhecido pela aplicação cliente. | Garanta que o SO da sua aplicação possui a cadeia CA padrão atualizada. |
| **`Produto N não encontrado no catálogo.`** | Recurso `catalogo://produtos/{id}`, `estoque://...` ou `precos://...` com ID inexistente (`ResourceNotFoundError`). | Consulte os IDs válidos via recurso `catalogo://produtos`. |
| **`Produto N não encontrado no catálogo.`** (ferramenta) | `validar_compatibilidade`, `cotar`, `consultar_frete` ou `reservar_pedido` com `produto_id` inexistente (`ToolError`). | Idem. |
| **`produto_id inválido (esperado inteiro): ...`** | ID não numérico num recurso. | Envie o ID como inteiro. |
| **`CEP inválido (esperado 8 dígitos): ...`** | `consultar_frete` com CEP fora do formato. | Envie 8 dígitos, com ou sem hífen. |
| **`ID de pedido inválido: '...'`** / **`Pedido '...' não encontrado.`** | `converter_reserva_venda` com `pedido_id` malformado ou inexistente. | Use o `id` devolvido por `reservar_pedido`. |
| **`Divergência ou comprovante inválido: ...`** | `converter_reserva_venda`: comprovante não confere com o valor devido. | Reenvie o comprovante correto; a reserva fica como pagamento divergente. |
| **`Parâmetro 'query' é obrigatório para a busca em manuais.`** | Recurso `manuais://busca/{domain}` sem `?query=`. | Informe a consulta. |

## 7. Roteiro de Teste com o Portal do Parceiro (interface gráfica)

Roteiro para o cliente validar a integração sem escrever código, usando o **Portal do Parceiro B2B** (`cliente-b2b/`, Streamlit). Cada passo diz o que fazer na tela, o que esperar e qual capacidade do MCP está sendo exercitada. Tempo estimado: 20 minutos.

### 7.1 Preparação

1. Tenha em mãos a **URL** do servidor e a **chave de parceiro** (seção 2). Em ambiente local: `http://127.0.0.1:8100/mcp`; público: `https://augustoglauco.duckdns.org:8443/mcp`.
2. Instale e inicie o portal:
   ```bash
   cd cliente-b2b
   pip install -r requirements.txt
   streamlit run src/app.py
   ```
   O navegador abre em `http://localhost:8501`.
3. Na **barra lateral**, preencha *URL do Servidor MCP* e *Chave do Parceiro (Bearer)*. Marque **Modo Desenvolvedor (Exibir JSON-RPC)** se quiser ver as respostas brutas em JSON.

> ⚠️ Os passos 7.8 e 7.9 **baixam estoque de verdade** e criam pedido real no ambiente. Use um ambiente de homologação ou avise a equipe antes.

### 7.2 Teste 1 — Autenticação

| Ação | Resultado esperado |
| :--- | :--- |
| Deixe a chave **em branco** (ou digite uma errada) e clique em **🔌 Conectar / Testar Conexão** | Mensagem vermelha *Erro de Autenticação* (`401`) e o status continua 🔴 Desconectado. |
| Digite a chave **correta** e clique em **Conectar** | *Conectado com sucesso ao servidor* (com nome e versão), status 🟢 Conectado e, no expansor **Ver Ferramentas MCP**, as **5 ferramentas**: `validar_compatibilidade`, `consultar_frete`, `cotar`, `reservar_pedido`, `converter_reserva_venda`. |

### 7.3 Teste 2 — Catálogo (aba 📦 Catálogo & Recursos)

1. Clique em **Carregar Catálogo**. Esperado: lista de produtos com ID, nome, categoria e preço. **Anote 2 ou 3 IDs** (um deles com estoque) para os próximos testes.
2. Digite uma categoria existente em *Filtrar por categoria* e carregue de novo. Esperado: só produtos daquela categoria.
3. Digite uma categoria inexistente. Esperado: lista vazia, sem erro.

### 7.4 Teste 3 — Estoque e preços (mesma aba)

1. Em *ID do Produto*, informe um ID anotado e clique em **Consultar Estoque**. Esperado: saldo por centro de distribuição (CD). **Anote o nome de um CD com saldo.**
2. Clique em **Tabela de Preços**. Esperado: preço, promoção vigente (se houver) e faixas de desconto por volume.
3. Informe um ID inexistente (ex.: 99999). Esperado: mensagem `Produto 99999 não encontrado no catálogo.`

### 7.5 Teste 4 — Busca em manuais (mesma aba)

1. Escolha o domínio **suporte**, digite uma dúvida técnica (ex.: `alcance máximo do cabo de rede`) e clique em **Buscar Manual**. Esperado: trechos de manuais com a fonte.
2. Repita com **vendas** e **atendimento**. Esperado: resultados coerentes com o domínio.
3. Clique em **Buscar Manual** com o campo vazio. Esperado: nada acontece (a busca exige texto).

### 7.6 Teste 5 — Cotação com desconto por volume (aba 💰 Cotação de Preços)

1. Adicione um produto com **quantidade 1** e clique em **Calcular Cotação B2B**. Esperado: sem desconto (0%).
2. Clique em **Limpar Cesta**, adicione o mesmo produto com quantidade que atinja a **faixa de desconto** vista no Teste 3 e calcule de novo. Esperado: desconto aplicado, *Total Líquido* menor que o *Subtotal Bruto*.
3. Adicione 2 ou 3 produtos diferentes. Esperado: um subtotal por item e o total geral somando todos.
4. Confira à mão: `quantidade × preço unitário × (1 − desconto)` deve bater com o subtotal exibido.

### 7.7 Teste 6 — Frete e compatibilidade

**🚚 Consulta de Frete** (usa a cesta montada no Teste 5):
1. Com o CEP padrão `01310-100`, clique em **Calcular Frete dos Itens**. Esperado: peso total, custo estimado e prazo em dias.
2. Troque por um CEP com menos de 8 dígitos (ex.: `1234`). Esperado: `CEP inválido (esperado 8 dígitos)`.

**🔍 Compatibilidade:**
1. Informe dois IDs de produtos que você sabe que se combinam (ex.: equipamento e acessório) e clique em **Verificar Compatibilidade Técnica**. Esperado: ✅ *Produtos Compatíveis!*.
2. Inverta a ordem dos dois IDs. Esperado: o mesmo resultado (a relação é simétrica).
3. Informe dois produtos sem relação. Esperado: ⚠️ *Produtos Não Compatíveis*.

### 7.8 Teste 7 — Reserva de pedido (aba 🛒 Fechar Pedido) — altera estoque

1. Na aba de cotação, monte uma cesta pequena (1 item, quantidade 1 ou 2) de um produto **com saldo** no CD anotado.
2. Na aba **Fechar Pedido**, confira a lista de itens e a prévia de valor (o *Valor estimado da reserva* é o total da cotação, já com o desconto por volume), escolha o **CD** na lista (só aparecem CDs com saldo para toda a cesta), marque a caixa de confirmação e clique em **🛒 Emitir Pedido B2B**.
3. Esperado: 🎉 *Reserva criada com sucesso*, com o `id` (UUID, copiável), `status: reservado`, data, a tabela de itens (CD, preço unitário, subtotal) e o *Valor a pagar*. A cesta é esvaziada. **Copie o `id`.**
4. Volte ao Teste 3 e consulte o estoque do produto: o saldo do CD deve ter **diminuído** na quantidade reservada.
5. Tente reservar uma quantidade **maior que o saldo**. Esperado: pedido recusado, sem alterar o estoque.
6. Com a cesta vazia, tente emitir. Esperado: aviso de cesta vazia.

> O portal usa **um único CD para todos os itens** da cesta (limitação do protótipo; a ferramenta `reservar_pedido` aceita um CD por item).

### 7.9 Teste 8 — Comprovante e conversão em venda (aba 🧾 Converter Reserva / Comprovante)

O campo *ID do Pedido* já vem preenchido com a última reserva criada.

1. **Comprovante divergente:** escolha *Texto / Linha Digitável / PIX*, escreva um valor errado (ex.: `PIX de R$ 1,00 para Empresa`) e clique em **Enviar Comprovante & Converter em Venda**. Esperado: mensagem de *Divergência ou comprovante inválido* (ou conversão registrada como divergente, conforme o parecer); o pedido **não** vira venda concluída.
2. **Comprovante correto:** envie um comprovante (arquivo PDF/PNG/JPG, ou texto) com o **valor exato** do pedido (o *Valor a pagar* do Teste 7). Esperado: 🎉 mensagem de sucesso, *Status Atual* `venda_concluida` e o *Parecer Financeiro da IA*.
3. **Pedido inexistente:** informe um UUID qualquer. Esperado: `Pedido '...' não encontrado.`

### 7.10 Folha de resultado

Preencha e devolva à equipe:

| # | Teste | Passou? | Observações |
| :-: | :--- | :-: | :--- |
| 1 | Autenticação (sem chave, chave certa, 5 ferramentas) | ☐ | |
| 2 | Catálogo (completo, por categoria, vazio) | ☐ | |
| 3 | Estoque e preços (válido e inexistente) | ☐ | |
| 4 | Busca em manuais (3 domínios) | ☐ | |
| 5 | Cotação (sem desconto, com desconto, vários itens) | ☐ | |
| 6 | Frete e compatibilidade (inclui CEP inválido e simetria) | ☐ | |
| 7 | Reserva (estoque baixou, quantidade excessiva recusada) | ☐ | |
| 8 | Conversão (divergente, correto, inexistente) | ☐ | |

Em caso de falha, anote a mensagem exata (com **Modo Desenvolvedor** ligado, copie o JSON) e consulte a seção 6.

---
*Em caso de dúvidas técnicas sobre a integração B2B ou solicitação de renovação de chaves, entre em contato com a equipe de suporte de TI.*
