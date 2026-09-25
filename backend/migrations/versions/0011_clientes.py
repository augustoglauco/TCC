"""clientes e cliente_compras (classificação do usuário, R10, Fase 6)

Ver decisão de 2026-09-25 em docs/ARCHITECTURE.md §5. Base fictícia: três
clientes, um por situação da classificação. As datas das compras são
relativas ao momento em que a migração roda, para as regras de recência
("últimos 12 meses") não envelhecerem.

# MVP: base de clientes fictícia; e-mails no domínio reservado example.com.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-25

"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (e-mail, nome, [(produto, quantidade, dias atrás)])
_CLIENTES = [
    # Cliente: 3 compras, a última há 30 dias.
    (
        "ana.recorrente@example.com",
        "Ana Recorrente",
        [
            ("Gerador Diesel GD-15", 1, 30),
            ("Quadro de Transferência Automática QTA-100", 1, 90),
            ("Gerador Diesel GD-30", 1, 200),
        ],
    ),
    # Esporádico: uma única compra.
    ("bruno.unico@example.com", "Bruno Único", [("Gerador Diesel GD-60", 1, 60)]),
    # Esporádico: 2 compras, mas a mais recente há mais de 12 meses.
    (
        "carla.antiga@example.com",
        "Carla Antiga",
        [("Gerador Diesel GD-15", 2, 500), ("Cabine de Insonorização", 1, 700)],
    ),
]


def upgrade() -> None:
    op.create_table(
        "clientes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_clientes_email", "clientes", ["email"], unique=True)
    op.create_table(
        "cliente_compras",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes.id"), nullable=False),
        sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=True),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.Column("valor_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("comprado_em", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cliente_compras_cliente_id", "cliente_compras", ["cliente_id"])

    conn = op.get_bind()
    produtos = sa.table(
        "produtos", sa.column("id", sa.Integer()), sa.column("nome"), sa.column("preco")
    )
    preco_e_id = {
        row.nome: (row.id, row.preco)
        for row in conn.execute(sa.select(produtos.c.id, produtos.c.nome, produtos.c.preco))
    }
    clientes = sa.table(
        "clientes", sa.column("id", sa.Integer()), sa.column("email"), sa.column("nome")
    )
    compras = sa.table(
        "cliente_compras",
        sa.column("cliente_id", sa.Integer()),
        sa.column("produto_id", sa.Integer()),
        sa.column("quantidade", sa.Integer()),
        sa.column("valor_total", sa.Numeric(12, 2)),
        sa.column("comprado_em", sa.DateTime(timezone=True)),
    )
    agora = datetime.now(UTC)
    for email, nome, itens in _CLIENTES:
        conn.execute(sa.insert(clientes).values(email=email, nome=nome))
        cliente_id = conn.execute(
            sa.select(clientes.c.id).where(clientes.c.email == email)
        ).scalar_one()
        for produto, quantidade, dias in itens:
            produto_id, preco = preco_e_id.get(produto, (None, Decimal("0")))
            conn.execute(
                sa.insert(compras).values(
                    cliente_id=cliente_id,
                    produto_id=produto_id,
                    quantidade=quantidade,
                    valor_total=Decimal(str(preco)) * quantidade,
                    comprado_em=agora - timedelta(days=dias),
                )
            )


def downgrade() -> None:
    op.drop_index("ix_cliente_compras_cliente_id", table_name="cliente_compras")
    op.drop_table("cliente_compras")
    op.drop_index("ix_clientes_email", table_name="clientes")
    op.drop_table("clientes")
