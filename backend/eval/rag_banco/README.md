# Conjunto de banco (R12, Fase 10)

80 perguntas sobre preço, estoque, prazo, comparação e categoria, montadas a
partir das linhas de `produtos`/`produto_estoque`.

```bash
cd backend
.venv/bin/python eval/rag_banco/gerar_dataset.py          # grava dataset.json
.venv/bin/python eval/rag_banco/gerar_dataset.py --dry-run
```

Exige só Postgres no ar.

## Por que este conjunto não tem revisão humana

O gabarito é **exato por construção**: a pergunta é montada por template a
partir da própria linha, então a resposta certa é o valor que está no banco.
Junto com o conjunto de imagem (gabarito = nome da pasta do fornecedor), é um
dos dois conjuntos sem revisão humana (`docs/EVALUATION.md` Seção 0).

Cada caso carrega `gabarito_bruto` com o valor cru que a resposta afirma. Se o
preço mudar no banco, o caso fica **detectavelmente** velho em vez de
silenciosamente errado.

## Que caminho de produção isto exercita

O de **Vendas**, não o conector de banco do RAG. "Quanto custa o iDTouch?" é
classificada como vendas e respondida por `app.router.sales_catalog`
(`extract_sales_slots` → `consultar_detalhes`). O `app.rag.db_connector` é a
outra feature do R4 — ingerir uma tabela como texto — e tem outro propósito.

## Composição (2026-10-17, 47 produtos no catálogo)

| Tipo | n | O que mede |
| --- | --- | --- |
| `preco` | 22 | leitura direta de um campo |
| `estoque_total` | 12 | soma dos CDs, incluindo os 8 produtos zerados (resposta negativa) |
| `estoque_cd` | 12 | leitura por centro de distribuição |
| `prazo` | 12 | `dias_alerta_estoque` |
| `comparacao_preco` | 12 | exige trazer dois produtos e comparar, não repetir um campo |
| `categoria` | 10 | listagem — limitado pelas 10 categorias distintas do catálogo |

A cota de `categoria` fecha em 10 porque só existem 10 categorias; o total é
completado com perguntas de preço sobre produtos que ainda não entraram, para
o conjunto ter exatamente 80 itens.

## Dados inventados

Preço, estoque e prazo são fictícios, autorizados pelo dono em 2026-10-17, e
gerados por `backend/scripts/popular_produtos_corpus.py` de forma
**determinística** (hash do nome, não `random`): rodar de novo dá o mesmo
catálogo, então um conjunto gerado antes continua válido.
