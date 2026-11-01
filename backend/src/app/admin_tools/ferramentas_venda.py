"""Ferramenta `atualizar_venda`: muda o status de um pedido pelo chat do Admin."""

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_tools.ferramentas import (
    FERRAMENTAS,
    Previa,
    PropostaInvalidaError,
    validar_args,
)
from app.db.catalog import devolver_estoque, obter_pedido
from app.db.models import Pedido

# Única fonte de verdade das transições.
# MVP: sem estorno financeiro (não há gateway) e sem cancelamento parcial de itens.
TRANSICOES: dict[str, set[str]] = {
    "reservado": {"venda_concluida", "cancelada"},
    "pagamento_divergente": {"venda_concluida", "cancelada"},
    "venda_concluida": {"cancelada"},
    "cancelada": set(),
}


class _AtualizarVenda(BaseModel):
    pedido_id: uuid.UUID
    novo_status: Literal["venda_concluida", "cancelada"]


async def _pedido_para_mudar(session: AsyncSession, args: dict[str, Any]) -> tuple[Pedido, str]:
    dados = validar_args(_AtualizarVenda, args)
    pedido = await obter_pedido(session, dados.pedido_id)
    if pedido is None:
        raise PropostaInvalidaError("Pedido não encontrado.")
    if dados.novo_status not in TRANSICOES.get(pedido.status, set()):
        raise PropostaInvalidaError(
            f"Não é possível ir de '{pedido.status}' para '{dados.novo_status}'."
        )
    return pedido, dados.novo_status


def _devolucao(pedido: Pedido) -> dict[str, int]:
    soma: dict[str, int] = {}
    for item in pedido.itens:
        soma[item.centro_distribuicao] = soma.get(item.centro_distribuicao, 0) + item.quantidade
    return soma


async def _reivindicar_status(
    session: AsyncSession, pedido: Pedido, novo: str, admin_id: int
) -> None:
    """UPDATE condicional no status lido: só uma confirmação concorrente vence (e só ela
    devolve estoque). Não faz commit."""
    valores: dict[str, Any] = {"status": novo}
    if novo == "cancelada":
        # Cancelada não conta como convertida: limpa a conversão da venda concluída.
        valores.update(tipo_conversao=None, convertido_em=None, convertido_por=None)
    else:
        valores.update(
            tipo_conversao="chat_admin",
            convertido_em=datetime.now(UTC),
            convertido_por=f"admin:{admin_id}",
        )
    resultado = await session.execute(
        update(Pedido)
        .where(Pedido.id == pedido.id, Pedido.status == pedido.status)
        .values(**valores)
        .execution_options(synchronize_session=False)
    )
    if resultado.rowcount == 0:
        raise PropostaInvalidaError("O status do pedido mudou; refaça o pedido.")


class AtualizarVenda:
    nome = "atualizar_venda"

    async def preparar(self, session: AsyncSession, args: dict[str, Any]) -> Previa:
        pedido, novo = await _pedido_para_mudar(session, args)
        depois: dict[str, Any] = {"status": novo}
        aviso = None
        if novo == "cancelada":
            depois["estoque_devolvido"] = _devolucao(pedido)
            if pedido.status == "venda_concluida":
                aviso = "Esta venda já foi concluída; cancelar devolve os itens ao estoque."
        return Previa(
            titulo=f"Pedido {str(pedido.id)[:8]}: {pedido.status} → {novo}",
            antes={"status": pedido.status},
            depois=depois,
            aviso=aviso,
        )

    async def executar(
        self, session: AsyncSession, args: dict[str, Any], *, admin_id: int
    ) -> dict[str, Any]:
        pedido, novo = await _pedido_para_mudar(session, args)
        await _reivindicar_status(session, pedido, novo, admin_id)
        resultado: dict[str, Any] = {"status": novo}
        if novo == "cancelada":
            for item in pedido.itens:
                await devolver_estoque(
                    session, item.produto_id, item.centro_distribuicao, item.quantidade
                )
            resultado["estoque_devolvido"] = _devolucao(pedido)
        return resultado


FERRAMENTAS["atualizar_venda"] = AtualizarVenda()
