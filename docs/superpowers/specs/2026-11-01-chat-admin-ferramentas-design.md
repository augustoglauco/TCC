# Chat Admin com ferramentas de consulta e escrita — design

Data: 2026-11-01. Requisitos: R3 (catálogo), R12 (estoque/pedidos), R9 (gráficos
do Admin). Estado: **aguardando revisão do usuário**.

## Objetivo

O perfil Admin pode, pelo chat, consultar o banco, gerar gráficos, incluir
produto, alterar nome e descrição de produto, dar baixa em estoque e mudar o
status de uma venda (inclusive cancelar devolvendo os itens ao estoque).
Hoje o chat Admin só lê: gráficos com SQL somente-SELECT (`safe_sql`) e RAG.

"Controle absoluto" é entendido como **um conjunto fixo de ações tipadas**, não
SQL livre de escrita: o LLM só escolhe a ação e os argumentos, e quem grava é o
código. Decisões do usuário (2026-11-01): mecanismo = ferramentas fixas +
`consultar(sql)` só de SELECT; **toda escrita pede confirmação**; escopo inclui
`atualizar_venda` com os status abaixo.

## Ferramentas

| Ferramenta | Tipo | Reaproveita |
|---|---|---|
| `consultar(sql)` | leitura | `safe_sql.execute_readonly_sql` |
| `consultar_estoque(produto, cd?)` | leitura | `ProdutoEstoque` |
| `grafico(...)` | leitura | `chart_generator` (já existe) |
| `incluir_produto(nome, descricao, preco, categoria, opcionais…)` | escrita | `criar_produto` / `ProdutoCreate` |
| `alterar_nome_produto(produto, novo_nome)` | escrita | `atualizar_produto` |
| `alterar_descricao_produto(produto, nova_descricao)` | escrita | `atualizar_produto` |
| `baixa_estoque(produto, cd, quantidade)` | escrita | `atualizar_estoque`, com decremento atômico |
| `atualizar_venda(pedido_id, novo_status)` | escrita | `Pedido` / `admin_pedidos_conversao` |

Regras comuns:

- Produto é resolvido por nome ou id. Se casar com mais de um, o chat lista os
  candidatos e pede a escolha; nunca altera "o primeiro que achar".
- `consultar(sql)`: mesma validação do `safe_sql` (só SELECT, lista de tabelas
  permitidas, padrões de escrita bloqueados), mais **limite de linhas** e
  **tempo máximo** da consulta. Resultado volta ao chat como tabela.
- Argumentos de cada ferramenta vêm de um esquema Pydantic fixo.

## `atualizar_venda` — máquina de status

Status existentes: `reservado`, `venda_concluida`, `pagamento_divergente`. Novo:
`cancelada` (terminal).

| De | Para | Efeito |
|---|---|---|
| `reservado` | `venda_concluida` | preenche `tipo_conversao="chat_admin"`, `convertido_em`, `convertido_por` |
| `pagamento_divergente` | `venda_concluida` | idem |
| `reservado`, `pagamento_divergente`, `venda_concluida` | `cancelada` | **devolve cada item ao estoque** do `centro_distribuicao` do item (`quantidade` somada em `produto_estoque`), na mesma transação |
| `cancelada` | qualquer | recusado (terminal) |

A criação do pedido já decrementa o estoque (`criar_pedido`), por isso o
cancelamento é o inverso exato. Cancelar uma venda já concluída mostra na
prévia um aviso extra. Qualquer outro status que passe a existir entra na
tabela acima, nunca por texto livre. `# MVP:` sem estorno financeiro nem
parcial (cancelar parte dos itens).

## Fluxo de uma escrita

1. O admin pede em linguagem natural.
2. Um classificador simples de intenção (padrão do `detect_chart_request`) separa
   leitura de escrita; o LLM devolve só uma **proposta** JSON (ferramenta +
   argumentos). Ele não executa nada.
3. O código valida, resolve produto/pedido e monta a **prévia** (antes → depois).
4. O chat mostra a prévia com **Confirmar** e **Cancelar**. A proposta fica no
   servidor, com id, expiração curta e vinculada ao admin.
5. O botão chama um endpoint próprio (`require_admin`), que **revalida**,
   grava e registra a auditoria. O texto da conversa nunca dispara a gravação.

Garantias: só Admin usa as ferramentas (`is_admin` já existe no orquestrador);
instrução maliciosa vinda de documento do RAG ou de mensagem só gera prévia;
não existe SQL de escrita em nenhum ponto.

## Dados e auditoria

Tabela nova `chat_admin_acoes` (migração 0031): `id`, `admin`, `ferramenta`,
`argumentos` (JSON), `antes` (JSON), `depois` (JSON), `status`
(`proposta`/`executada`/`cancelada`/`expirada`), `criado_em`, `executado_em`.
As propostas pendentes usam a mesma tabela. É a trilha de auditoria que o
`Pedido` hoje não tem.

Baixa de estoque e devolução usam `UPDATE … SET quantidade = quantidade ± n
[WHERE quantidade >= n]` em uma instrução, o que também fecha a corrida que o
cadastro do MVP deixava aberta.

## Fora desta entrega

Excluir produto, alterar preço, mexer em clientes/agendamentos, SQL livre de
escrita, estorno financeiro, cancelamento parcial.

## Testes

- Cada ferramenta: argumento inválido, produto/pedido inexistente, produto
  ambíguo, não-admin (recusado).
- Confirmação: sem confirmar não grava; proposta expirada recusada; reconfirmar
  a mesma proposta não grava duas vezes.
- Estoque: baixa maior que o saldo recusada; devolução soma no CD certo; duas
  baixas concorrentes não deixam saldo negativo.
- `consultar`: INSERT/UPDATE/DELETE/DDL e tabela fora da lista bloqueados, limite
  de linhas e tempo.
- Injeção: texto de documento do RAG pedindo "dê baixa em tudo" gera no máximo
  uma prévia, nunca uma gravação.

## Entrega em etapas

1. `consultar(sql)` no chat Admin (+ limite de linhas e tempo).
2. Mecanismo de proposta, confirmação e auditoria (migração 0031).
3. `incluir_produto`, `alterar_nome_produto`, `alterar_descricao_produto`.
4. `baixa_estoque`.
5. `atualizar_venda` (inclui o status `cancelada` e a devolução ao estoque).

## Documentos a atualizar na implementação

`docs/ARCHITECTURE.md` (decisão e `# MVP:`), `docs/FRONTEND.md` (cartão de
prévia e endpoint de confirmação), `docs/ROADMAP.md`,
`docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md` (prompt do roteador de ferramentas) e
`docs/Manuais/HOWTO_ADMINISTRADOR.md`.
