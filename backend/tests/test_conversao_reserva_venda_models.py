import pytest
from datetime import datetime, UTC
from app.db.models import Pedido

@pytest.mark.asyncio
async def test_pedido_conversao_venda_fields(db_session):
    now = datetime.now(UTC)
    pedido = Pedido(
        status="venda_concluida",
        user_email="cliente@exemplo.com",
        comprovante_url="/uploads/comprovantes/pix_123.pdf",
        tipo_conversao="auto_chat",
        convertido_em=now,
        convertido_por="sistema_llm",
        llm_parecer='{"valido": true, "valor_comprovante": 1500.00, "divergencia": 0.0}',
    )
    db_session.add(pedido)
    await db_session.commit()

    saved_pedido = await db_session.get(Pedido, pedido.id)
    assert saved_pedido is not None
    assert saved_pedido.status == "venda_concluida"
    assert saved_pedido.comprovante_url == "/uploads/comprovantes/pix_123.pdf"
    assert saved_pedido.tipo_conversao == "auto_chat"
    assert saved_pedido.convertido_em is not None
    assert saved_pedido.convertido_por == "sistema_llm"
    assert "valido" in saved_pedido.llm_parecer
