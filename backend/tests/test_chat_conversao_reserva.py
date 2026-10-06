import asyncio
from datetime import UTC, datetime
from decimal import Decimal
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.chat import (
    router as chat_router,
    get_local_client,
    get_external_client,
    get_rag_client,
    get_rag_client_admin,
    get_stt_client,
    get_clip_store,
    get_clip_embedder,
    get_calendar_client,
    get_scheduling_config,
    get_sales_catalog_client,
    get_intent_router_provider,
    get_tone_monitor_enabled,
    get_tone_monitor_provider,
)
from app.db.models import Pedido, PedidoItem, Produto
from app.router.orchestrator import RouterDecision, TokenEvent, handle_message
from app.router.sales_catalog import (
    buscar_reserva_ativa,
    detectar_intencao_comprovante,
    processar_conversao_comprovante,
)


class _SingleSessionMaker:
    def __init__(self, session) -> None:
        self._session = session
        self._lock = asyncio.Lock()

    def __call__(self):
        return self

    async def __aenter__(self):
        await self._lock.acquire()
        return self._session

    async def __aexit__(self, *exc_info) -> bool:
        self._lock.release()
        return False


def _parse_sse(texto: str) -> list[tuple[str, dict]]:
    eventos = []
    for bloco in texto.strip().split("\n\n"):
        tipo = dados = None
        for linha in bloco.split("\n"):
            if linha.startswith("event:"):
                tipo = linha[len("event:") :].strip()
            elif linha.startswith("data:"):
                try:
                    dados = json.loads(linha[len("data:") :].strip())
                except Exception:
                    dados = linha[len("data:") :].strip()
        if tipo and dados is not None:
            eventos.append((tipo, dados))
    return eventos


def test_detectar_intencao_comprovante():
    assert detectar_intencao_comprovante("Segue o comprovante do pagamento PIX de R$ 1.500,00") is True
    assert detectar_intencao_comprovante("Paguei a reserva, aqui está o recibo com autenticação 12345") is True
    assert detectar_intencao_comprovante("[Texto extraído da imagem]:\nComprovante de Transferência") is True
    assert detectar_intencao_comprovante("Quanto custa um gerador solar?") is False
    assert detectar_intencao_comprovante("Vocês têm estoque em São Paulo?") is False


@pytest.mark.asyncio
async def test_chat_conversao_item_unico_sucesso(db_session):
    # Setup de produto e pedido reservado com 1 item
    prod = Produto(nome="Painel Solar 500W", descricao="Painel fotovoltaico", preco=Decimal("1500.00"), categoria="Solar")
    db_session.add(prod)
    await db_session.flush()

    pedido = Pedido(
        user_email="cliente@gmail.com",
        conversation_id="conv-b2c-1",
        status="reservado",
    )
    db_session.add(pedido)
    await db_session.flush()

    item = PedidoItem(
        pedido_id=pedido.id,
        produto_id=prod.id,
        quantidade=1,
        centro_distribuicao="CD-SP",
        preco_unitario=Decimal("1500.00"),
    )
    db_session.add(item)
    await db_session.commit()

    sessionmaker = _SingleSessionMaker(db_session)

    events = []
    async for ev in handle_message(
        message="Segue o comprovante do pagamento PIX de R$ 1.500,00 da reserva. Código de autenticação: E12345678202610051200",
        recent_messages=[],
        local_client=AsyncMock(),
        external_client=AsyncMock(),
        rag_client=AsyncMock(),
        complexity_strategy="heuristic",
        conversation_id="conv-b2c-1",
        db_sessionmaker=sessionmaker,
        user_email="cliente@gmail.com",
    ):
        events.append(ev)

    token_events = [e for e in events if isinstance(e, TokenEvent)]
    assert len(token_events) > 0
    assert "confirmado com sucesso" in token_events[0].text.lower()
    assert "venda concluída" in token_events[0].text.lower()

    decisions = [e for e in events if isinstance(e, RouterDecision)]
    assert len(decisions) == 1
    assert decisions[0].motivo_escalonamento == "vendas_comprovante_pagamento"
    assert decisions[0].domain == "vendas"

    await db_session.refresh(pedido)
    assert pedido.status == "venda_concluida"
    assert pedido.tipo_conversao == "auto_chat"
    assert pedido.convertido_em is not None
    assert pedido.convertido_por == "sistema_llm"
    assert pedido.llm_parecer is not None
    parecer = json.loads(pedido.llm_parecer)
    assert parecer["valido"] is True
    assert parecer["valor_pago"] == 1500.0


@pytest.mark.asyncio
async def test_chat_conversao_multiplos_itens_sucesso(db_session):
    # Setup de pedido reservado com múltiplos itens faturados
    prod = Produto(nome="Inversor Híbrido 5kW", descricao="Inversor Solar", preco=Decimal("450.00"), categoria="Solar")
    db_session.add(prod)
    await db_session.flush()

    pedido = Pedido(
        user_email="compras@industria.com.br",
        conversation_id="conv-multi-1",
        status="reservado",
    )
    db_session.add(pedido)
    await db_session.flush()

    item = PedidoItem(
        pedido_id=pedido.id,
        produto_id=prod.id,
        quantidade=10,
        centro_distribuicao="CD-SP",
        preco_unitario=Decimal("450.00"),
    )
    db_session.add(item)
    await db_session.commit()

    sessionmaker = _SingleSessionMaker(db_session)

    events = []
    async for ev in handle_message(
        message="Segue comprovante de pagamento da reserva: TED no valor de R$ 4.500,00. Transação: TED998877",
        recent_messages=[],
        local_client=AsyncMock(),
        external_client=AsyncMock(),
        rag_client=AsyncMock(),
        complexity_strategy="heuristic",
        conversation_id="conv-multi-1",
        db_sessionmaker=sessionmaker,
        user_email="compras@industria.com.br",
    ):
        events.append(ev)

    token_events = [e for e in events if isinstance(e, TokenEvent)]
    assert len(token_events) > 0
    assert "confirmado com sucesso" in token_events[0].text.lower()

    await db_session.refresh(pedido)
    assert pedido.status == "venda_concluida"
    assert pedido.tipo_conversao == "auto_chat"


@pytest.mark.asyncio
async def test_chat_conversao_pagamento_divergente(db_session):
    prod = Produto(nome="Bateria de Lítio", descricao="Bateria 48V", preco=Decimal("2000.00"), categoria="Baterias")
    db_session.add(prod)
    await db_session.flush()

    pedido = Pedido(
        user_email="cliente@gmail.com",
        conversation_id="conv-div-1",
        status="reservado",
    )
    db_session.add(pedido)
    await db_session.flush()

    item = PedidoItem(
        pedido_id=pedido.id,
        produto_id=prod.id,
        quantidade=1,
        centro_distribuicao="CD-MG",
        preco_unitario=Decimal("2000.00"),
    )
    db_session.add(item)
    await db_session.commit()

    sessionmaker = _SingleSessionMaker(db_session)

    events = []
    async for ev in handle_message(
        message="Segue o comprovante do pagamento PIX de R$ 1.500,00. Transação: E999",
        recent_messages=[],
        local_client=AsyncMock(),
        external_client=AsyncMock(),
        rag_client=AsyncMock(),
        complexity_strategy="heuristic",
        conversation_id="conv-div-1",
        db_sessionmaker=sessionmaker,
        user_email="cliente@gmail.com",
    ):
        events.append(ev)

    token_events = [e for e in events if isinstance(e, TokenEvent)]
    assert len(token_events) > 0
    assert "divergência" in token_events[0].text.lower() or "divergencia" in token_events[0].text.lower()

    await db_session.refresh(pedido)
    assert pedido.status == "pagamento_divergente"
    assert pedido.tipo_conversao is None


@pytest.mark.asyncio
async def test_chat_conversao_acha_reserva_de_conversa_anterior_pelo_email(db_session):
    """Regressão (achado de 2026-10-05): cliente faz o pedido numa conversa,
    e meses/dias depois volta numa conversa NOVA só para confirmar o
    pagamento ("já paguei"). `buscar_reserva_ativa` priorizava
    conversation_id sobre user_email com um `elif` — como toda mensagem de
    chat tem um conversation_id, user_email nunca era tentado como
    fallback quando a reserva foi criada numa conversa diferente da atual,
    e o cliente recebia "não encontrei nenhuma reserva pendente" mesmo
    tendo uma reserva real e ativa associada ao seu e-mail."""
    prod = Produto(
        nome="Controle de Acesso IDFACE",
        descricao="Facial",
        preco=Decimal("2109.85"),
        categoria="Controle de Acesso",
    )
    db_session.add(prod)
    await db_session.flush()

    # Reserva criada na conversa original de compra.
    pedido = Pedido(
        user_email="carla@gmail.com",
        conversation_id="conv-compra-original",
        status="pagamento_divergente",
    )
    db_session.add(pedido)
    await db_session.flush()

    item = PedidoItem(
        pedido_id=pedido.id,
        produto_id=prod.id,
        quantidade=1,
        centro_distribuicao="CD-SP",
        preco_unitario=Decimal("2109.85"),
    )
    db_session.add(item)
    await db_session.commit()

    sessionmaker = _SingleSessionMaker(db_session)

    # Cliente volta numa conversa NOVA e diferente só para avisar que pagou.
    events = []
    async for ev in handle_message(
        message="já paguei",
        recent_messages=["olá, eu tenho pagamento de compra pendente?"],
        local_client=AsyncMock(),
        external_client=AsyncMock(),
        rag_client=AsyncMock(),
        complexity_strategy="heuristic",
        conversation_id="conv-nova-confirmacao",
        db_sessionmaker=sessionmaker,
        user_email="carla@gmail.com",
    ):
        events.append(ev)

    token_events = [e for e in events if isinstance(e, TokenEvent)]
    assert len(token_events) > 0
    resposta = token_events[0].text.lower()
    # Deve achar a reserva pelo e-mail e pedir o comprovante — não a
    # mensagem de "não encontrei nenhuma reserva".
    assert "não encontrei nenhuma reserva" not in resposta


@pytest.mark.asyncio
async def test_chat_conversao_apenas_intencao_sem_conteudo_pede_anexo(db_session):
    """Regressão: mensagem que só ANUNCIA a intenção de enviar o comprovante
    (sem anexar nada e sem colar dados reais de uma transação) não deve ser
    mandada para o avaliador de IA como se fosse o próprio comprovante — isso
    sempre reprova e confunde o cliente. Deve pedir o anexo e NÃO marcar a
    reserva como `pagamento_divergente` (nada foi de fato submetido para
    haver uma divergência a registrar)."""
    prod = Produto(
        nome="Câmera IDFACE",
        descricao="Controle de acesso facial",
        preco=Decimal("2109.85"),
        categoria="Controle de Acesso",
    )
    db_session.add(prod)
    await db_session.flush()

    pedido = Pedido(
        user_email="carla@gmail.com",
        conversation_id="conv-intencao-1",
        status="reservado",
    )
    db_session.add(pedido)
    await db_session.flush()

    item = PedidoItem(
        pedido_id=pedido.id,
        produto_id=prod.id,
        quantidade=1,
        centro_distribuicao="CD-SP",
        preco_unitario=Decimal("2109.85"),
    )
    db_session.add(item)
    await db_session.commit()

    sessionmaker = _SingleSessionMaker(db_session)

    events = []
    async for ev in handle_message(
        message="quero enviar o comprovante de pagamento",
        recent_messages=[],
        local_client=AsyncMock(),
        external_client=AsyncMock(),
        rag_client=AsyncMock(),
        complexity_strategy="heuristic",
        conversation_id="conv-intencao-1",
        db_sessionmaker=sessionmaker,
        user_email="carla@gmail.com",
    ):
        events.append(ev)

    token_events = [e for e in events if isinstance(e, TokenEvent)]
    assert len(token_events) > 0
    resposta = token_events[0].text.lower()
    assert "envie" in resposta or "anexe" in resposta
    assert "foto" in resposta or "arquivo" in resposta
    # Não deve ser a mensagem de reprovação do avaliador de IA.
    assert "não foi possível validar" not in resposta

    await db_session.refresh(pedido)
    assert pedido.status == "reservado"


@pytest.mark.asyncio
async def test_chat_conversao_sem_reserva_ativa(db_session):
    sessionmaker = _SingleSessionMaker(db_session)

    events = []
    async for ev in handle_message(
        message="Segue o comprovante de pagamento PIX de R$ 500,00",
        recent_messages=[],
        local_client=AsyncMock(),
        external_client=AsyncMock(),
        rag_client=AsyncMock(),
        complexity_strategy="heuristic",
        conversation_id="conv-vazia",
        db_sessionmaker=sessionmaker,
    ):
        events.append(ev)

    token_events = [e for e in events if isinstance(e, TokenEvent)]
    assert len(token_events) > 0
    assert "não encontrei nenhuma reserva" in token_events[0].text.lower()


@pytest.fixture
def chat_client(db_session):
    app = FastAPI()
    app.include_router(chat_router)
    app.state.db_sessionmaker = _SingleSessionMaker(db_session)
    app.state.complexity_strategy = "heuristic"
    app.state.image_internal_confidence = 0.8
    app.state.image_external_confidence = 0.6

    mock_local = MagicMock()
    mock_local.is_model_ready = AsyncMock(return_value=True)
    mock_ext = MagicMock()
    mock_ext.is_model_ready = AsyncMock(return_value=True)
    mock_rag = MagicMock()
    mock_rag_admin = MagicMock()
    mock_stt = MagicMock()
    mock_stt.transcribe = AsyncMock(return_value="")
    mock_clip_store = MagicMock()
    mock_clip_embedder = MagicMock()
    mock_calendar = MagicMock()
    mock_sched = MagicMock()
    mock_catalog = MagicMock()

    app.dependency_overrides[get_local_client] = lambda: mock_local
    app.dependency_overrides[get_external_client] = lambda: mock_ext
    app.dependency_overrides[get_rag_client] = lambda: mock_rag
    app.dependency_overrides[get_rag_client_admin] = lambda: mock_rag_admin
    app.dependency_overrides[get_stt_client] = lambda: mock_stt
    app.dependency_overrides[get_clip_store] = lambda: mock_clip_store
    app.dependency_overrides[get_clip_embedder] = lambda: mock_clip_embedder
    app.dependency_overrides[get_calendar_client] = lambda: mock_calendar
    app.dependency_overrides[get_scheduling_config] = lambda: mock_sched
    app.dependency_overrides[get_sales_catalog_client] = lambda: mock_catalog
    app.dependency_overrides[get_intent_router_provider] = lambda: "heuristica"
    app.dependency_overrides[get_tone_monitor_enabled] = lambda: False
    app.dependency_overrides[get_tone_monitor_provider] = lambda: "heuristica"

    with TestClient(app) as client:
        yield client


@pytest.mark.asyncio
async def test_chat_api_endpoint_comprovante_imagem(chat_client, db_session, monkeypatch):
    prod = Produto(nome="Painel Solar 500W", descricao="Painel", preco=Decimal("1500.00"), categoria="Solar")
    db_session.add(prod)
    await db_session.flush()

    pedido = Pedido(
        user_email="cliente@gmail.com",
        conversation_id="conv-img-1",
        status="reservado",
    )
    db_session.add(pedido)
    await db_session.flush()

    item = PedidoItem(
        pedido_id=pedido.id,
        produto_id=prod.id,
        quantidade=1,
        centro_distribuicao="CD-SP",
        preco_unitario=Decimal("1500.00"),
    )
    db_session.add(item)
    await db_session.commit()

    monkeypatch.setattr(
        "app.api.chat.extract_text_from_base64",
        lambda img_b64: "Comprovante de Transferência PIX\nValor: R$ 1.500,00\nAutenticação: TX12345",
    )

    png_1x1 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )

    res = chat_client.post(
        "/api/chat/messages",
        json={
            "conversation_id": "conv-img-1",
            "message": "Segue o comprovante",
            "image": png_1x1,
            "image_intent": "documento",
            "user_email": "cliente@gmail.com",
        },
    )
    assert res.status_code == 200
    eventos = _parse_sse(res.text)
    token_events = [dados for tipo, dados in eventos if tipo == "token"]
    assert any("confirmado com sucesso" in t.get("text", "").lower() for t in token_events)

    await db_session.refresh(pedido)
    assert pedido.status == "venda_concluida"
    assert pedido.tipo_conversao == "auto_chat"
    assert pedido.comprovante_url is not None

