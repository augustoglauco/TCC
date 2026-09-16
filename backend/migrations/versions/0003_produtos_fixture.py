"""create produtos fixture table (R4 - conector de leitura a BD relacional)

# MVP: tabela fictícia usada como fixture de exemplo para o conector de
leitura a BD relacional — análoga em espírito a
`backend/scripts/sample_docs/` para PDFs/textos, mas para dados
estruturados. Não é uma tabela usada pelo restante da aplicação (não há
model SQLAlchemy em `app.db.models` para ela de propósito: o conector lê
qualquer tabela via reflexão, não é acoplado a este schema específico).

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "produtos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("descricao", sa.String(), nullable=False),
        sa.Column("preco", sa.Numeric(10, 2), nullable=False),
        sa.Column("categoria", sa.String(), nullable=False),
    )

    produtos = sa.table(
        "produtos",
        sa.column("nome", sa.String()),
        sa.column("descricao", sa.String()),
        sa.column("preco", sa.Numeric(10, 2)),
        sa.column("categoria", sa.String()),
    )
    op.bulk_insert(
        produtos,
        [
            {
                "nome": "Gerador Diesel GD-15",
                "descricao": (
                    "Potência de 15 kVA, ideal para pequenos comércios e obras. "
                    "Autonomia de 8 horas com tanque cheio."
                ),
                "preco": 24900.00,
                "categoria": "geradores",
            },
            {
                "nome": "Gerador Diesel GD-30",
                "descricao": (
                    "Potência de 30 kVA, indicado para condomínios e indústrias de "
                    "pequeno porte. Autonomia de 10 horas com tanque cheio. Aceita "
                    "cabine de insonorização opcional."
                ),
                "preco": 42500.00,
                "categoria": "geradores",
            },
            {
                "nome": "Gerador Diesel GD-60",
                "descricao": (
                    "Potência de 60 kVA, indicado para indústrias de médio porte com "
                    "necessidade de backup contínuo. Compatível com o Quadro de "
                    "Transferência Automática QTA-100."
                ),
                "preco": 78000.00,
                "categoria": "geradores",
            },
            {
                "nome": "Quadro de Transferência Automática QTA-100",
                "descricao": (
                    "Chaveamento automático entre rede elétrica e gerador em caso de "
                    "queda de energia, suporta até 100A."
                ),
                "preco": 6200.00,
                "categoria": "acessórios",
            },
            {
                "nome": "Cabine de Insonorização",
                "descricao": (
                    "Redução de ruído de até 15 dB para geradores diesel da linha GD-30 e GD-60."
                ),
                "preco": 6800.00,
                "categoria": "acessórios",
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("produtos")
