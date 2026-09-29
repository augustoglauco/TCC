"""cria a tabela agendamentos (R11, Fase 7)

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agendamentos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_email", sa.String(), nullable=False),
        sa.Column("nome_cliente", sa.String(), nullable=False),
        sa.Column("telefone", sa.String(), nullable=True),
        sa.Column("data_hora_inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_hora_fim", sa.DateTime(timezone=True), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="confirmado"),
        sa.Column("origem", sa.String(), nullable=False, server_default="chat"),
        sa.Column("google_event_id", sa.String(), nullable=True),
        sa.Column("google_event_link", sa.String(), nullable=True),
        sa.Column("conversation_id", sa.String(), nullable=True),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agendamentos_user_email", "agendamentos", ["user_email"])
    op.create_index("ix_agendamentos_data_hora_inicio", "agendamentos", ["data_hora_inicio"])
    op.create_index("ix_agendamentos_status", "agendamentos", ["status"])
    op.create_index("ix_agendamentos_conversation_id", "agendamentos", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_agendamentos_conversation_id", table_name="agendamentos")
    op.drop_index("ix_agendamentos_status", table_name="agendamentos")
    op.drop_index("ix_agendamentos_data_hora_inicio", table_name="agendamentos")
    op.drop_index("ix_agendamentos_user_email", table_name="agendamentos")
    op.drop_table("agendamentos")
