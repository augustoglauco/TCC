"""índice em tom_escalonamentos.criado_em (achado na revisão final, R8)

A listagem administrativa (GET /api/admin/tom/escalonamentos) ordena por
`criado_em DESC LIMIT 100` — sem índice, isso é um full scan a cada chamada.
Sem custo real no volume atual do protótipo, mas correto para o padrão de
acesso real da tabela.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-24

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_tom_escalonamentos_criado_em",
        "tom_escalonamentos",
        ["criado_em"],
    )


def downgrade() -> None:
    op.drop_index("ix_tom_escalonamentos_criado_em", table_name="tom_escalonamentos")
