"""cria compatibilidades/pedidos para as 4 ferramentas do MCP B2B (R12, Fase 5)

Modela as três tabelas novas exigidas pelas ferramentas transacionais do MCP
B2B (validação de compatibilidade, reserva/pedido) — ver decisão registrada
em `docs/ARCHITECTURE.md` §5 (2026-09-24). "Consulta de frete e prazos" e
"cotação automática" não precisam de tabela nova (estimativa determinística
interna e lógica sobre `produtos`/`produto_descontos_volume` já existentes,
respectivamente).

# MVP: pares de `produto_compatibilidades` cadastrados manualmente via esta
fixture (mesmo espírito da fixture de produtos/estoque/descontos da migração
0008) — sem regra automática de dedução por categoria/especificação técnica.
`pedidos`/`pedido_itens` não têm trilha de auditoria nem tratamento de
concorrência (lock otimista/pessimista) — evolução futura explícita
registrada em `docs/ARCHITECTURE.md` §6 ("Governança e segurança").

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-24

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "produto_compatibilidades",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=False),
        sa.Column(
            "compativel_com_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=False
        ),
    )
    op.create_index(
        "ix_produto_compatibilidades_produto_id", "produto_compatibilidades", ["produto_id"]
    )
    op.create_index(
        "ix_produto_compatibilidades_compativel_com_id",
        "produto_compatibilidades",
        ["compativel_com_id"],
    )

    op.create_table(
        "pedidos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("status", sa.String(), nullable=False, server_default="reservado"),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "pedido_itens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("pedido_id", sa.Uuid(), sa.ForeignKey("pedidos.id"), nullable=False),
        sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=False),
        sa.Column("centro_distribuicao", sa.String(), nullable=False),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.Column("preco_unitario", sa.Numeric(10, 2), nullable=False),
    )
    op.create_index("ix_pedido_itens_pedido_id", "pedido_itens", ["pedido_id"])
    op.create_index("ix_pedido_itens_produto_id", "pedido_itens", ["produto_id"])

    # Pares fictícios de compatibilidade entre os 5 produtos já semeados na
    # migração 0008 — QTA-100 (quadro de transferência) funciona com
    # qualquer um dos 3 geradores diesel; a cabine de insonorização foi
    # dimensionada para o GD-30. Coerente com a base pequena de demonstração
    # já usada nas fixtures anteriores (não é uma regra de negócio real).
    conn = op.get_bind()
    produtos_tabela = sa.table(
        "produtos", sa.column("id", sa.Integer()), sa.column("nome", sa.String())
    )
    produtos_existentes = {
        row.nome: row.id
        for row in conn.execute(sa.select(produtos_tabela.c.id, produtos_tabela.c.nome))
    }

    pares = [
        ("Quadro de Transferência Automática QTA-100", "Gerador Diesel GD-15"),
        ("Quadro de Transferência Automática QTA-100", "Gerador Diesel GD-30"),
        ("Cabine de Insonorização", "Gerador Diesel GD-30"),
    ]
    compatibilidades_tabela = sa.table(
        "produto_compatibilidades",
        sa.column("id", sa.Uuid()),
        sa.column("produto_id", sa.Integer()),
        sa.column("compativel_com_id", sa.Integer()),
    )
    linhas = []
    for nome_a, nome_b in pares:
        produto_id = produtos_existentes.get(nome_a)
        compativel_com_id = produtos_existentes.get(nome_b)
        if produto_id is None or compativel_com_id is None:
            continue
        linhas.append(
            {
                "id": uuid.uuid4(),
                "produto_id": produto_id,
                "compativel_com_id": compativel_com_id,
            }
        )
    if linhas:
        op.bulk_insert(compatibilidades_tabela, linhas)


def downgrade() -> None:
    op.drop_index("ix_pedido_itens_produto_id", table_name="pedido_itens")
    op.drop_index("ix_pedido_itens_pedido_id", table_name="pedido_itens")
    op.drop_table("pedido_itens")
    op.drop_table("pedidos")
    op.drop_index(
        "ix_produto_compatibilidades_compativel_com_id", table_name="produto_compatibilidades"
    )
    op.drop_index("ix_produto_compatibilidades_produto_id", table_name="produto_compatibilidades")
    op.drop_table("produto_compatibilidades")
