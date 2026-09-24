"""estende produtos + cria estoque/descontos por volume (R12, Fase 5)

Modela o backend único de dados (catálogo, estoque, preços) reaproveitado
tanto pelo RAG quanto pelo futuro servidor MCP B2B — ver
`docs/ARCHITECTURE.md` §5/§6. Estende a tabela fixture `produtos` (migração
`0003`) em vez de criar um schema paralelo. "Manuais" (o quarto recurso do
R12) não ganha tabela aqui — continuam sendo documentos RAG (ver comentário
no model `Produto` em `app.db.models`).

# MVP: sem tratamento de concorrência em reservas/pedidos nem trilha de
auditoria (evolução futura explícita, `docs/ARCHITECTURE.md` §6) — esta
migração só modela dados de leitura (catálogo/estoque/preços), não o
comportamento transacional das ferramentas MCP (item futuro da Fase 5).

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-24

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("produtos", sa.Column("especificacoes_tecnicas", sa.String(), nullable=True))
    op.add_column("produtos", sa.Column("dimensoes_cm", sa.String(), nullable=True))
    op.add_column("produtos", sa.Column("peso_kg", sa.Numeric(10, 3), nullable=True))
    op.add_column("produtos", sa.Column("preco_promocional", sa.Numeric(10, 2), nullable=True))
    op.add_column(
        "produtos",
        sa.Column("promocao_valida_ate", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "produto_estoque",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=False),
        sa.Column("centro_distribuicao", sa.String(), nullable=False),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "produto_descontos_volume",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=False),
        sa.Column("quantidade_minima", sa.Integer(), nullable=False),
        sa.Column("percentual_desconto", sa.Numeric(5, 2), nullable=False),
    )

    # Achado no code-review (2026-09-24): toda consulta em app.db.catalog
    # filtra por produto_id (listar_estoque, listar_descontos_volume, o
    # upsert de atualizar_estoque, os deletes filhos de deletar_produto) —
    # Postgres não indexa FK automaticamente, mesma lição já registrada na
    # migração 0007 (ix_tom_escalonamentos_criado_em).
    op.create_index("ix_produto_estoque_produto_id", "produto_estoque", ["produto_id"])
    op.create_index(
        "ix_produto_descontos_volume_produto_id", "produto_descontos_volume", ["produto_id"]
    )

    # Dados fictícios coerentes com a fixture original (0003), só
    # complementando os campos novos — mesmo espírito de "não é produção,
    # é uma base pequena de demonstração" (docs/ARCHITECTURE.md §6).
    conn = op.get_bind()
    produtos_tabela = sa.table(
        "produtos",
        sa.column("id", sa.Integer()),
        sa.column("nome", sa.String()),
        sa.column("especificacoes_tecnicas", sa.String()),
        sa.column("dimensoes_cm", sa.String()),
        sa.column("peso_kg", sa.Numeric(10, 3)),
    )
    produtos_query = sa.select(produtos_tabela.c.id, produtos_tabela.c.nome)
    produtos_existentes = {row.nome: row.id for row in conn.execute(produtos_query)}

    especificacoes = {
        "Gerador Diesel GD-15": {
            "especificacoes_tecnicas": "Motor diesel monocilíndrico, partida elétrica, 220V/380V.",
            "dimensoes_cm": "110x70x90",
            "peso_kg": "320.000",
        },
        "Gerador Diesel GD-30": {
            "especificacoes_tecnicas": "Motor diesel 2 cilindros, partida elétrica, 220V/380V.",
            "dimensoes_cm": "150x90x110",
            "peso_kg": "560.000",
        },
        "Gerador Diesel GD-60": {
            "especificacoes_tecnicas": (
                "Motor diesel 4 cilindros, partida elétrica, trifásico 380V."
            ),
            "dimensoes_cm": "210x110x130",
            "peso_kg": "980.000",
        },
        "Quadro de Transferência Automática QTA-100": {
            "especificacoes_tecnicas": "Chaveamento automático, suporta até 100A, IP54.",
            "dimensoes_cm": "60x40x20",
            "peso_kg": "18.500",
        },
        "Cabine de Insonorização": {
            "especificacoes_tecnicas": "Painéis com manta acústica, redução de até 15 dB.",
            "dimensoes_cm": "160x100x120",
            "peso_kg": "210.000",
        },
    }
    for nome, campos in especificacoes.items():
        produto_id = produtos_existentes.get(nome)
        if produto_id is None:
            continue
        conn.execute(
            sa.update(produtos_tabela).where(produtos_tabela.c.id == produto_id).values(**campos)
        )

    produto_estoque = sa.table(
        "produto_estoque",
        sa.column("id", sa.Uuid()),
        sa.column("produto_id", sa.Integer()),
        sa.column("centro_distribuicao", sa.String()),
        sa.column("quantidade", sa.Integer()),
    )
    produto_descontos = sa.table(
        "produto_descontos_volume",
        sa.column("id", sa.Uuid()),
        sa.column("produto_id", sa.Integer()),
        sa.column("quantidade_minima", sa.Integer()),
        sa.column("percentual_desconto", sa.Numeric(5, 2)),
    )

    estoque_rows = []
    desconto_rows = []
    for nome, produto_id in produtos_existentes.items():
        if nome not in especificacoes:
            continue
        estoque_rows.append(
            {
                "id": uuid.uuid4(),
                "produto_id": produto_id,
                "centro_distribuicao": "CD-SP",
                "quantidade": 12,
            }
        )
        estoque_rows.append(
            {
                "id": uuid.uuid4(),
                "produto_id": produto_id,
                "centro_distribuicao": "CD-RJ",
                "quantidade": 5,
            }
        )
        desconto_rows.append(
            {
                "id": uuid.uuid4(),
                "produto_id": produto_id,
                "quantidade_minima": 5,
                "percentual_desconto": "5.00",
            }
        )
        desconto_rows.append(
            {
                "id": uuid.uuid4(),
                "produto_id": produto_id,
                "quantidade_minima": 10,
                "percentual_desconto": "10.00",
            }
        )

    if estoque_rows:
        op.bulk_insert(produto_estoque, estoque_rows)
    if desconto_rows:
        op.bulk_insert(produto_descontos, desconto_rows)


def downgrade() -> None:
    op.drop_index("ix_produto_descontos_volume_produto_id", table_name="produto_descontos_volume")
    op.drop_index("ix_produto_estoque_produto_id", table_name="produto_estoque")
    op.drop_table("produto_descontos_volume")
    op.drop_table("produto_estoque")
    op.drop_column("produtos", "promocao_valida_ate")
    op.drop_column("produtos", "preco_promocional")
    op.drop_column("produtos", "peso_kg")
    op.drop_column("produtos", "dimensoes_cm")
    op.drop_column("produtos", "especificacoes_tecnicas")
