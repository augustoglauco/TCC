"""Testes da API REST Administrativa para Conversão de Reserva em Venda (/api/admin/pedidos)."""

from decimal import Decimal
import io
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.rag_dependencies import get_db_session
from app.db.models import Cliente, Pedido, PedidoItem, Produto
from app.main import create_app


@pytest.fixture
def test_app(db_session):
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: db_session
    return app


@pytest.fixture
async def admin_headers(db_session):
    admin = Cliente(nome="Admin Pedidos", email="admin@empresa.com")
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return {"Authorization": f"Bearer mock-token-{admin.id}"}


@pytest.fixture
async def pedido_reservado(db_session):
    prod = Produto(
        nome="Cimento Especial 50kg",
        descricao="Cimento de alta resistência",
        preco=Decimal("50.00"),
        categoria="Construção",
    )
    db_session.add(prod)
    await db_session.commit()
    await db_session.refresh(prod)

    pedido = Pedido(
        status="reservado",
        user_email="cliente@exemplo.com",
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)

    item = PedidoItem(
        pedido_id=pedido.id,
        produto_id=prod.id,
        centro_distribuicao="CD-Principal",
        quantidade=10,
        preco_unitario=Decimal("50.00"),  # Total = 500.00
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


@pytest.mark.asyncio
async def test_admin_pedidos_unauthorized(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/admin/pedidos")
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_pedidos_list_and_filter(test_app, admin_headers, pedido_reservado):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Listar todos
        res = await client.get("/api/admin/pedidos", headers=admin_headers)
        assert res.status_code == 200
        pedidos = res.json()
        assert len(pedidos) >= 1
        ped = next(p for p in pedidos if p["id"] == str(pedido_reservado.id))
        assert ped["status"] == "reservado"
        assert ped["valor_total"] == 500.0
        assert len(ped["itens"]) == 1

        # 2. Filtrar por status
        res_filter = await client.get(
            "/api/admin/pedidos?status=reservado", headers=admin_headers
        )
        assert res_filter.status_code == 200
        assert any(p["id"] == str(pedido_reservado.id) for p in res_filter.json())


@pytest.mark.asyncio
async def test_admin_converter_manual_simples(test_app, admin_headers, pedido_reservado, db_session):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            f"/api/admin/pedidos/{pedido_reservado.id}/converter-manual-simples",
            data={"convertido_por": "Gerente Carlos"},
            headers=admin_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "venda_concluida"
        assert data["tipo_conversao"] == "manual_simples"
        assert data["convertido_por"] == "Gerente Carlos"
        assert data["convertido_em"] is not None

        # Confere no banco
        saved = await db_session.get(Pedido, pedido_reservado.id)
        assert saved.status == "venda_concluida"


@pytest.mark.asyncio
async def test_admin_analisar_e_confirmar_manual_padrao(test_app, admin_headers, pedido_reservado):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Analisa comprovante
        comprovante_content = b"COMPROVANTE PIX\nValor: R$ 500,00\nID Transacao: E11223344"
        files = {
            "comprovante": ("comprovante_500.txt", io.BytesIO(comprovante_content), "text/plain")
        }

        res_analise = await client.post(
            f"/api/admin/pedidos/{pedido_reservado.id}/analisar-comprovante",
            files=files,
            headers=admin_headers,
        )
        assert res_analise.status_code == 200
        data_analise = res_analise.json()
        assert data_analise["valor_devido"] == 500.0
        assert data_analise["parecer"]["valido"] is True
        assert data_analise["parecer"]["valor_pago"] == 500.0

        # 2. Confirma conversão
        res_confirma = await client.post(
            f"/api/admin/pedidos/{pedido_reservado.id}/confirmar-conversao",
            json={
                "comprovante_url": data_analise["comprovante_url"],
                "parecer_json": '{"valido": true, "valor_pago": 500.0}',
                "convertido_por": "Admin Validador",
            },
            headers=admin_headers,
        )
        assert res_confirma.status_code == 200
        data_confirma = res_confirma.json()
        assert data_confirma["status"] == "venda_concluida"
        assert data_confirma["tipo_conversao"] == "manual_padrao"


@pytest.mark.asyncio
async def test_admin_converter_auto_admin_sucesso(test_app, admin_headers, pedido_reservado):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        comprovante_content = b"COMPROVANTE TRANSFERENCIA\nValor: R$ 500,00\nAutenticacao: ABC-999"
        files = {
            "comprovante": ("recibo.txt", io.BytesIO(comprovante_content), "text/plain")
        }

        res = await client.post(
            f"/api/admin/pedidos/{pedido_reservado.id}/converter-auto-admin",
            files=files,
            headers=admin_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "venda_concluida"
        assert data["tipo_conversao"] == "auto_admin"


@pytest.mark.asyncio
async def test_admin_converter_auto_admin_divergente(test_app, admin_headers, pedido_reservado, db_session):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        comprovante_content = b"COMPROVANTE TRANSFERENCIA\nValor: R$ 350,00\nAutenticacao: ABC-888"
        files = {
            "comprovante": ("recibo_divergente.txt", io.BytesIO(comprovante_content), "text/plain")
        }

        res = await client.post(
            f"/api/admin/pedidos/{pedido_reservado.id}/converter-auto-admin",
            files=files,
            headers=admin_headers,
        )
        assert res.status_code == 422
        data = res.json()
        assert data["status"] == "pagamento_divergente"

        # Confere status alterado para pagamento_divergente no banco
        saved = await db_session.get(Pedido, pedido_reservado.id)
        assert saved.status == "pagamento_divergente"
