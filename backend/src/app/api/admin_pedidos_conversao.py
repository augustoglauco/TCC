"""Endpoints REST administrativos para Gestão de Pedidos e Conversão de Reserva em Venda."""

from datetime import UTC, datetime
from decimal import Decimal
import logging
from pathlib import Path
from typing import Any
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.admin_auth import require_admin
from app.api.rag_dependencies import get_db_session
from app.db.catalog import obter_pedido
from app.db.models import Pedido
from app.services.comprovante_evaluator import ComprovanteEvaluator

logger = logging.getLogger("assistente.admin_pedidos_conversao")

router = APIRouter(
    prefix="/api/admin/pedidos",
    tags=["Admin Pedidos - Conversão"],
    dependencies=[Depends(require_admin)],
)

COMPROVANTES_DIR = Path("uploads/comprovantes")


def _salvar_arquivo_comprovante(pedido_id: str, filename: str, conteudo: bytes) -> str:
    """Salva o comprovante em disco e retorna o caminho relativo do arquivo."""
    COMPROVANTES_DIR.mkdir(parents=True, exist_ok=True)
    # Sanitiza filename
    safe_name = Path(filename).name
    target_path = COMPROVANTES_DIR / f"{pedido_id}_{safe_name}"
    target_path.write_bytes(conteudo)
    return f"/uploads/comprovantes/{pedido_id}_{safe_name}"


def _calcular_total_pedido(pedido: Pedido) -> Decimal:
    """Calcula o valor total do pedido a partir de seus itens."""
    total = Decimal("0.00")
    for item in pedido.itens:
        total += item.preco_unitario * item.quantidade
    return total


def _serializar_pedido(pedido: Pedido) -> dict[str, Any]:
    """Serializa os dados do pedido com metadados de conversão e lista de itens."""
    total = _calcular_total_pedido(pedido)
    itens_list = [
        {
            "id": str(i.id),
            "produto_id": i.produto_id,
            "centro_distribuicao": i.centro_distribuicao,
            "quantidade": i.quantidade,
            "preco_unitario": float(i.preco_unitario),
            "subtotal": float(i.preco_unitario * i.quantidade),
        }
        for i in pedido.itens
    ]
    return {
        "id": str(pedido.id),
        "status": pedido.status,
        "user_email": pedido.user_email,
        "conversation_id": pedido.conversation_id,
        "comprovante_url": pedido.comprovante_url,
        "tipo_conversao": pedido.tipo_conversao,
        "convertido_em": pedido.convertido_em.isoformat() if pedido.convertido_em else None,
        "convertido_por": pedido.convertido_por,
        "llm_parecer": pedido.llm_parecer,
        "criado_em": pedido.criado_em.isoformat() if pedido.criado_em else None,
        "valor_total": float(total),
        "itens": itens_list,
    }


class ConfirmarConversaoRequest(BaseModel):
    comprovante_url: str | None = Field(default=None, description="URL do arquivo comprovante")
    parecer_json: str | None = Field(default=None, description="Parecer em JSON da avaliação do LLM")
    convertido_por: str | None = Field(default=None, description="Identificador do operador admin")


@router.get("")
async def listar_pedidos_admin(
    status: str | None = Query(default=None, description="Filtrar por status: reservado, venda_concluida, pagamento_divergente"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Lista pedidos do sistema com suporte a filtro por status e metadados de conversão."""
    stmt = select(Pedido).options(selectinload(Pedido.itens))
    if status:
        stmt = stmt.where(Pedido.status == status)

    stmt = stmt.order_by(Pedido.criado_em.desc()).offset(offset).limit(limit)
    res = await session.execute(stmt)
    pedidos = res.scalars().all()
    return [_serializar_pedido(p) for p in pedidos]


@router.get("/{pedido_id}")
async def obter_pedido_admin(
    pedido_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retorna os detalhes completos de um pedido específico."""
    pedido = await obter_pedido(session, pedido_id)
    if not pedido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {pedido_id} não encontrado.",
        )
    return _serializar_pedido(pedido)


@router.post("/{pedido_id}/converter-manual-simples")
async def post_converter_manual_simples(
    pedido_id: uuid.UUID,
    convertido_por: str | None = Form(default=None),
    comprovante: UploadFile | None = File(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Modalidade 1: Conversão Manual Simples (Admin).
    
    Converte a reserva em venda diretamente, sem exigir análise por LLM.
    """
    pedido = await obter_pedido(session, pedido_id)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado.")

    if pedido.status != "reservado":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pedido em status '{pedido.status}' não pode ser convertido.",
        )

    if comprovante and comprovante.filename:
        conteudo = await comprovante.read()
        comprovante_url = _salvar_arquivo_comprovante(str(pedido.id), comprovante.filename, conteudo)
        pedido.comprovante_url = comprovante_url

    pedido.status = "venda_concluida"
    pedido.tipo_conversao = "manual_simples"
    pedido.convertido_em = datetime.now(UTC)
    pedido.convertido_por = convertido_por or "admin"

    await session.commit()
    await session.refresh(pedido, attribute_names=["itens"])
    return _serializar_pedido(pedido)


@router.post("/{pedido_id}/analisar-comprovante")
async def post_analisar_comprovante(
    pedido_id: uuid.UUID,
    request: Request,
    comprovante: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Modalidade 2 (Etapa 1): Submete o comprovante para auditoria do LLM.
    
    Retorna o parecer técnico (valores, divergência, justificativa) para conferência manual do Admin.
    """
    pedido = await obter_pedido(session, pedido_id)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado.")

    if pedido.status != "reservado":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pedido em status '{pedido.status}' não pode ser analisado para conversão.",
        )

    valor_devido = _calcular_total_pedido(pedido)
    conteudo = await comprovante.read()
    comprovante_url = _salvar_arquivo_comprovante(str(pedido.id), comprovante.filename or "comprovante.bin", conteudo)

    llm_client = getattr(request.app.state, "local_client", None) or getattr(request.app.state, "external_client", None)
    vision_client = getattr(request.app.state, "external_client", None)
    evaluator = ComprovanteEvaluator(llm_client=llm_client, vision_client=vision_client)

    parecer = await evaluator.avaliar_documento(conteudo, comprovante.filename or "arquivo.bin", valor_devido)

    return {
        "pedido_id": str(pedido.id),
        "valor_devido": float(valor_devido),
        "comprovante_url": comprovante_url,
        "parecer": {
            "valido": parecer.valido,
            "valor_pago": float(parecer.valor_pago),
            "divergencia": float(parecer.divergencia),
            "justificativa": parecer.justificativa,
            "codigo_transacao": parecer.codigo_transacao,
        },
    }


@router.post("/{pedido_id}/confirmar-conversao")
async def post_confirmar_conversao(
    pedido_id: uuid.UUID,
    payload: ConfirmarConversaoRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Modalidade 2 (Etapa 2): Confirmação Manual do Admin após validação do parecer de IA."""
    pedido = await obter_pedido(session, pedido_id)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado.")

    if pedido.status != "reservado":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pedido em status '{pedido.status}' não pode ser convertido.",
        )

    pedido.status = "venda_concluida"
    pedido.tipo_conversao = "manual_padrao"
    pedido.convertido_em = datetime.now(UTC)
    pedido.convertido_por = payload.convertido_por or "admin"
    if payload.comprovante_url:
        pedido.comprovante_url = payload.comprovante_url
    if payload.parecer_json:
        pedido.llm_parecer = payload.parecer_json

    await session.commit()
    await session.refresh(pedido, attribute_names=["itens"])
    return _serializar_pedido(pedido)


@router.post("/{pedido_id}/converter-auto-admin")
async def post_converter_auto_admin(
    pedido_id: uuid.UUID,
    request: Request,
    comprovante: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Modalidade 3: Conversão Automática no Admin por Upload.
    
    Processa o comprovante com LLM; se validado e com divergência 0, converte automaticamente.
    Em caso de divergência ou inconsistência, altera o pedido para 'pagamento_divergente'.
    """
    pedido = await obter_pedido(session, pedido_id)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado.")

    if pedido.status != "reservado":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pedido em status '{pedido.status}' não pode ser convertido.",
        )

    valor_devido = _calcular_total_pedido(pedido)
    conteudo = await comprovante.read()
    comprovante_url = _salvar_arquivo_comprovante(str(pedido.id), comprovante.filename or "comprovante.bin", conteudo)

    llm_client = getattr(request.app.state, "local_client", None) or getattr(request.app.state, "external_client", None)
    vision_client = getattr(request.app.state, "external_client", None)
    evaluator = ComprovanteEvaluator(llm_client=llm_client, vision_client=vision_client)

    parecer = await evaluator.avaliar_documento(conteudo, comprovante.filename or "arquivo.bin", valor_devido)

    pedido.comprovante_url = comprovante_url
    pedido.llm_parecer = parecer.to_json()

    if parecer.valido:
        pedido.status = "venda_concluida"
        pedido.tipo_conversao = "auto_admin"
        pedido.convertido_em = datetime.now(UTC)
        pedido.convertido_por = "admin_auto_upload"
        await session.commit()
        await session.refresh(pedido, attribute_names=["itens"])
        return _serializar_pedido(pedido)

    # Divergência encontrada
    pedido.status = "pagamento_divergente"
    await session.commit()
    await session.refresh(pedido, attribute_names=["itens"])

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "pagamento_divergente",
            "mensagem": "Comprovante com divergência ou inválido.",
            "justificativa": parecer.justificativa,
            "valor_devido": float(valor_devido),
            "valor_pago": float(parecer.valor_pago),
            "divergencia": float(parecer.divergencia),
        },
    )
