"""Endpoints REST para gestão de Pedidos, Cotação e Frete (R12, Fase 7)."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rag_dependencies import get_db_session
from app.db.catalog import (
    EstoqueInsuficienteError,
    ProdutoInexistenteError,
    calcular_item_cotacao,
    criar_pedido,
    listar_pedidos,
    obter_pedido,
    obter_produto,
)
from app.mcp_server.b2b import _FRETE_ADICIONAL_POR_KG, _FRETE_CUSTO_BASE_E_PRAZO_POR_REGIAO
from app.models.orders import (
    FreightQuoteIn,
    FreightQuoteOut,
    OrderCreateIn,
    OrderItemOut,
    OrderOut,
    OrderSimulationIn,
    OrderSimulationItemOut,
    OrderSimulationOut,
    OrdersListOut,
)

router = APIRouter(prefix="/api/orders", tags=["pedidos"])


def _map_order_to_out(pedido) -> OrderOut:
    itens_out = []
    total = Decimal("0.00")
    for item in pedido.itens:
        sub = item.preco_unitario * item.quantidade
        total += sub
        itens_out.append(
            OrderItemOut(
                id=item.id,
                produto_id=item.produto_id,
                nome_produto=None,  # pode ser enriquecido
                quantidade=item.quantidade,
                centro_distribuicao=item.centro_distribuicao,
                preco_unitario=item.preco_unitario,
                subtotal=sub,
            )
        )
    return OrderOut(
        id=pedido.id,
        status=pedido.status,
        criado_em=pedido.criado_em,
        user_email=pedido.user_email,
        conversation_id=pedido.conversation_id,
        itens=itens_out,
        valor_total=total,
    )


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order_endpoint(
    payload: OrderCreateIn,
    session: AsyncSession = Depends(get_db_session),
):
    itens_tuples = [
        (item.produto_id, item.quantidade, item.centro_distribuicao) for item in payload.itens
    ]
    try:
        pedido = await criar_pedido(
            session,
            itens_tuples,
            user_email=payload.user_email,
            conversation_id=payload.conversation_id,
        )
    except ProdutoInexistenteError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EstoqueInsuficienteError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    # Enriquece o nome do produto se disponível
    for item_out in _map_order_to_out(pedido).itens:
        prod = await obter_produto(session, item_out.produto_id)
        if prod:
            item_out.nome_produto = prod.nome

    return _map_order_to_out(pedido)


@router.get("", response_model=OrdersListOut)
async def list_orders_endpoint(
    user_email: str | None = Query(None),
    conversation_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
):
    pedidos, total = await listar_pedidos(
        session,
        user_email=user_email,
        conversation_id=conversation_id,
        limit=limit,
        offset=offset,
    )

    items_out = []
    for p in pedidos:
        out = _map_order_to_out(p)
        for item_out in out.itens:
            prod = await obter_produto(session, item_out.produto_id)
            if prod:
                item_out.nome_produto = prod.nome
        items_out.append(out)

    return OrdersListOut(items=items_out, total=total, limit=limit, offset=offset)


@router.get("/{order_id}", response_model=OrderOut)
async def get_order_endpoint(
    order_id: UUID,
    session: AsyncSession = Depends(get_db_session),
):
    pedido = await obter_pedido(session, order_id)
    if not pedido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {order_id} não encontrado.",
        )
    out = _map_order_to_out(pedido)
    for item_out in out.itens:
        prod = await obter_produto(session, item_out.produto_id)
        if prod:
            item_out.nome_produto = prod.nome
    return out


@router.post("/quote", response_model=OrderSimulationOut)
async def calculate_quote_endpoint(
    payload: OrderSimulationIn,
    session: AsyncSession = Depends(get_db_session),
):
    itens_out = []
    total_cotado = Decimal("0.00")

    for item_in in payload.itens:
        prod = await obter_produto(session, item_in.produto_id)
        if not prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Produto {item_in.produto_id} não encontrado.",
            )

        preco_base, percentual, subtotal = calcular_item_cotacao(prod, item_in.quantidade)
        total_cotado += subtotal

        itens_out.append(
            OrderSimulationItemOut(
                produto_id=prod.id,
                nome_produto=prod.nome,
                quantidade=item_in.quantidade,
                preco_unitario_base=preco_base,
                percentual_desconto_aplicado=percentual,
                subtotal=subtotal,
            )
        )

    return OrderSimulationOut(itens=itens_out, valor_total=total_cotado)


@router.post("/freight", response_model=FreightQuoteOut)
async def calculate_freight_endpoint(
    payload: FreightQuoteIn,
    session: AsyncSession = Depends(get_db_session),
):
    cep_limpo = payload.cep.replace("-", "").strip()
    primeiro_digito = cep_limpo[0] if cep_limpo else "0"

    custo_base, prazo = _FRETE_CUSTO_BASE_E_PRAZO_POR_REGIAO.get(
        primeiro_digito, (Decimal("50.00"), 5)
    )

    peso_total_kg = Decimal("0.00")
    for item_in in payload.itens:
        prod = await obter_produto(session, item_in.produto_id)
        if not prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Produto {item_in.produto_id} não encontrado.",
            )
        peso_item = prod.peso_kg or Decimal("1.00")
        peso_total_kg += peso_item * item_in.quantidade

    custo_total = custo_base + (peso_total_kg * _FRETE_ADICIONAL_POR_KG)
    custo_total = custo_total.quantize(Decimal("0.01"))

    return FreightQuoteOut(
        cep=payload.cep,
        peso_total_kg=peso_total_kg,
        custo_estimado=custo_total,
        prazo_dias=prazo,
    )
