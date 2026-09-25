"""Testes para os endpoints de imagem: POST /api/rag/images e o campo
`image` em POST /api/chat/messages (R6, Fase 3)."""

import base64
import io

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.ocr.image_processor import OcrIndisponivelError
from app.rag.clip_embedder import CLIP_VECTOR_DIMENSION

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_png_bytes() -> bytes:
    pytest.importorskip("PIL", reason="Pillow não instalado")
    from PIL import Image

    img = Image.new("RGB", (4, 4), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _png_b64() -> str:
    return base64.b64encode(_make_png_bytes()).decode()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _FakeClipEmbedder:
    async def embed_images(self, images):
        return [[0.1] * CLIP_VECTOR_DIMENSION for _ in images]

    async def embed_texts(self, texts):
        return [[0.1] * CLIP_VECTOR_DIMENSION for _ in texts]


class _FakeClipStore:
    def __init__(self):
        self.upserted: list[dict] = []

    async def upsert_image(self, embedder, image_bytes, filename, domain):
        self.upserted.append({"filename": filename, "domain": domain})
        return "fake-uuid"

    async def search_by_image(self, embedder, image_bytes, domain=None, **kw):
        return []

    async def search_by_text(self, embedder, query, domain=None, **kw):
        return []


@pytest.fixture
def client_with_fake_clip(monkeypatch):
    app = create_app()
    store = _FakeClipStore()
    app.state.clip_image_store = store
    app.state.clip_embedder = _FakeClipEmbedder()
    return TestClient(app), store


# ---------------------------------------------------------------------------
# POST /api/rag/images — ingestão
# ---------------------------------------------------------------------------


def test_ingest_image_ok(client_with_fake_clip):
    client, store = client_with_fake_clip
    png = _make_png_bytes()
    resp = client.post(
        "/api/rag/images",
        data={"domain": "vendas"},
        files={"file": ("produto.png", png, "image/png")},
    )
    assert resp.status_code == 201
    assert resp.json()["image_id"] == "fake-uuid"
    assert store.upserted[0]["filename"] == "produto.png"


def test_ingest_image_formato_invalido(client_with_fake_clip):
    client, _ = client_with_fake_clip
    resp = client.post(
        "/api/rag/images",
        data={"domain": "vendas"},
        files={"file": ("doc.txt", b"texto puro", "text/plain")},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/rag/images/search — busca
# ---------------------------------------------------------------------------


def test_search_sem_file_nem_query_retorna_422(client_with_fake_clip):
    client, _ = client_with_fake_clip
    resp = client.post("/api/rag/images/search", data={})
    assert resp.status_code == 422


def test_search_por_texto_ok(client_with_fake_clip):
    client, _ = client_with_fake_clip
    resp = client.post("/api/rag/images/search", data={"query": "gerador"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_search_por_imagem_ok(client_with_fake_clip):
    client, _ = client_with_fake_clip
    png = _make_png_bytes()
    resp = client.post(
        "/api/rag/images/search",
        files={"file": ("q.png", png, "image/png")},
    )
    assert resp.status_code == 200


def test_identify_sem_catalogo_e_sem_vision_vira_nao_identificado(client_with_fake_clip):
    # Fake store devolve [] e o create_app usa OpenRouter com vision_model
    # vazio → visão indisponível → nao_identificado (sem erro ao usuário).
    client, _ = client_with_fake_clip
    png = _make_png_bytes()
    resp = client.post(
        "/api/rag/images/identify",
        files={"file": ("q.png", png, "image/png")},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "nao_identificado"


def test_identify_formato_invalido_retorna_400(client_with_fake_clip):
    client, _ = client_with_fake_clip
    resp = client.post(
        "/api/rag/images/identify",
        files={"file": ("doc.txt", b"texto puro", "text/plain")},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/chat/messages — campo image
# ---------------------------------------------------------------------------


@pytest.fixture
def chat_client(monkeypatch):
    """Cliente de chat com STT, LLM e RAG mockados — foca no fluxo de imagem."""
    from unittest.mock import AsyncMock, MagicMock

    from app.router.llm_client import LLMStreamChunk

    app = create_app()

    # STT: não transcreve nada (sem áudio)
    stt = MagicMock()
    stt.transcribe = AsyncMock(return_value="")
    app.state.stt_client = stt

    # LLM local: devolve um chunk simples
    chunk = LLMStreamChunk(
        text="resposta",
        done=True,
        prompt_tokens=1,
        completion_tokens=1,
        total_duration_ms=10.0,
        estimated_cost_usd=0.0,
    )

    async def _stream(prompt):
        yield chunk

    local = MagicMock()
    local.model = "fake-model"
    local.is_model_ready = AsyncMock(return_value=True)
    local.generate_stream = _stream
    local.generate = AsyncMock(
        return_value=MagicMock(text='{"domain":"vendas","complexity":"baixa","confidence":0.9}')
    )
    app.state.local_client = local
    app.state.external_client = local
    app.state.complexity_strategy = "heuristic"

    # RAG: sem resultados
    rag = MagicMock()
    rag.search = AsyncMock(return_value=[])
    app.state.rag_client = rag

    return TestClient(app)


def test_chat_com_imagem_e_texto(chat_client, monkeypatch):
    """image + message + intent documento: OCR mockado retorna texto, concatenado."""
    monkeypatch.setattr(
        "app.api.chat.extract_text_from_base64",
        lambda b64: "TEXTO DO OCR",
    )
    resp = chat_client.post(
        "/api/chat/messages",
        json={"message": "o que é isso?", "image": _png_b64(), "image_intent": "documento"},
    )
    assert resp.status_code == 200


def test_chat_so_imagem_sem_texto(chat_client, monkeypatch):
    """Só image + intent documento: OCR extrai texto e a request prossegue."""
    monkeypatch.setattr(
        "app.api.chat.extract_text_from_base64",
        lambda b64: "TEXTO DO OCR",
    )
    resp = chat_client.post(
        "/api/chat/messages",
        json={"image": _png_b64(), "image_intent": "documento"},
    )
    assert resp.status_code == 200


def test_chat_ocr_indisponivel_com_texto_fallback(chat_client, monkeypatch):
    """OCR indisponível + message presente: degrada graciosamente (não 503)."""
    monkeypatch.setattr(
        "app.api.chat.extract_text_from_base64",
        lambda b64: (_ for _ in ()).throw(OcrIndisponivelError("tesseract ausente")),
    )
    resp = chat_client.post(
        "/api/chat/messages",
        json={
            "message": "resuma esse comprovante",
            "image": _png_b64(),
            "image_intent": "documento",
        },
    )
    assert resp.status_code == 200


def test_chat_ocr_indisponivel_sem_texto_retorna_503(chat_client, monkeypatch):
    """OCR indisponível + sem message + intent documento: deve retornar 503."""
    monkeypatch.setattr(
        "app.api.chat.extract_text_from_base64",
        lambda b64: (_ for _ in ()).throw(OcrIndisponivelError("tesseract ausente")),
    )
    resp = chat_client.post(
        "/api/chat/messages",
        json={"image": _png_b64(), "image_intent": "documento"},
    )
    assert resp.status_code == 503


def test_chat_imagem_formato_invalido_retorna_400(chat_client, monkeypatch):
    from app.ocr.image_processor import ImageFormatError

    monkeypatch.setattr(
        "app.api.chat.extract_text_from_base64",
        lambda b64: (_ for _ in ()).throw(ImageFormatError("formato inválido")),
    )
    resp = chat_client.post(
        "/api/chat/messages",
        json={
            "image": base64.b64encode(b"\x00\x01\x02").decode(),
            "image_intent": "documento",
        },
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/chat/messages — identificação de produto (padrão, sem intent)
# ---------------------------------------------------------------------------


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    import json

    eventos = []
    for bloco in body.split("\n\n"):
        if not bloco.strip():
            continue
        tipo = dados = None
        for linha in bloco.split("\n"):
            if linha.startswith("event:"):
                tipo = linha[len("event:") :].strip()
            elif linha.startswith("data:"):
                dados = json.loads(linha[len("data:") :].strip())
        if tipo and dados is not None:
            eventos.append((tipo, dados))
    return eventos


def _identificacao_app(monkeypatch, *, clip_results, vision_answer, rag_docs):
    """Monta um app com CLIP/visão/RAG controlados para o fluxo de identificação."""
    from unittest.mock import AsyncMock, MagicMock

    from app.rag.image_search import ImageSearchResult
    from app.router.rag_client import Document

    app = create_app()

    store = MagicMock()
    store.search_by_image = AsyncMock(return_value=[ImageSearchResult(**r) for r in clip_results])
    app.state.clip_image_store = store
    app.state.clip_embedder = _FakeClipEmbedder()

    vision = MagicMock()
    if vision_answer is None:
        from app.router.openrouter_client import VisionModelIndisponivelError

        vision.describe_image = AsyncMock(side_effect=VisionModelIndisponivelError("x"))
    else:
        import json

        vision.describe_image = AsyncMock(return_value=json.dumps(vision_answer))
    app.state.external_client = vision

    rag = MagicMock()
    rag.search = AsyncMock(return_value=[Document(**d) for d in rag_docs])
    app.state.rag_client = rag

    stt = MagicMock()
    stt.transcribe = AsyncMock(return_value="")
    app.state.stt_client = stt

    app.state.image_internal_confidence = 0.30
    app.state.image_external_confidence = 0.80
    return TestClient(app)


def test_chat_identifica_produto_no_catalogo_interno(monkeypatch):
    client = _identificacao_app(
        monkeypatch,
        clip_results=[
            {"image_id": "i1", "filename": "Câmera IP", "domain": "vendas", "score": 0.45}
        ],
        vision_answer=None,  # não deve ser chamado
        rag_docs=[{"content": "Câmera IP 4MP com visão noturna.", "source": "cat", "score": 1.0}],
    )
    resp = client.post("/api/chat/messages", json={"image": _png_b64()})
    assert resp.status_code == 200
    eventos = _parse_sse(resp.text)
    ident = next(d for t, d in eventos if t == "identification")
    assert ident["status"] == "encontrado_interno"
    assert ident["produto"] == "Câmera IP"
    done = next(d for t, d in eventos if t == "done")
    assert done["backend_used"] == "identificacao_imagem"


def test_chat_identifica_produto_via_visao_externa(monkeypatch):
    client = _identificacao_app(
        monkeypatch,
        clip_results=[],  # nada no catálogo interno
        vision_answer={"produto": "Catraca X", "e_do_portfolio": True, "confianca": 0.9},
        rag_docs=[{"content": "Catraca X biométrica.", "source": "cat", "score": 1.0}],
    )
    resp = client.post("/api/chat/messages", json={"image": _png_b64()})
    assert resp.status_code == 200
    eventos = _parse_sse(resp.text)
    ident = next(d for t, d in eventos if t == "identification")
    assert ident["status"] == "encontrado_externo"
    assert ident["produto"] == "Catraca X"


def test_chat_nao_identifica_produto_fora_do_portfolio(monkeypatch):
    client = _identificacao_app(
        monkeypatch,
        clip_results=[],
        vision_answer={"produto": "Geladeira", "e_do_portfolio": False, "confianca": 0.95},
        rag_docs=[],
    )
    resp = client.post("/api/chat/messages", json={"image": _png_b64()})
    assert resp.status_code == 200
    eventos = _parse_sse(resp.text)
    ident = next(d for t, d in eventos if t == "identification")
    assert ident["status"] == "nao_identificado"


def test_chat_imagem_invalida_no_fluxo_de_identificacao_retorna_400(db_session):
    """Regressão (bug 2026-09-20): imagem-lixo no fluxo de identificação
    (sem image_intent) travava o chat silenciosamente (200 OK, corpo vazio),
    porque os bytes chegavam ao PIL.Image.open dentro do CLIP sem validação.

    Usa o ClipImageStore REAL (não mockado) + ClipEmbedder real: a validação
    de formato deve barrar ANTES de tocar no CLIP, devolvendo 400. Se a
    validação sumir, este teste ou vira 500 (PIL estoura) ou 200 vazio.
    """
    from unittest.mock import AsyncMock, MagicMock

    from fastapi import FastAPI
    from qdrant_client import AsyncQdrantClient

    from app.api.chat import (
        get_calendar_client,
        get_clip_embedder,
        get_clip_store,
        get_complexity_strategy,
        get_external_client,
        get_local_client,
        get_rag_client,
        get_sales_catalog_client,
        get_scheduling_config,
        get_stt_client,
    )
    from app.api.chat import router as chat_router
    from app.api.rag_dependencies import get_db_session
    from app.rag.clip_embedder import ClipEmbedder
    from app.rag.image_search import ClipImageStore

    app = FastAPI()
    app.include_router(chat_router)

    # ClipImageStore + ClipEmbedder REAIS (o embedder só seria carregado se o
    # CLIP fosse de fato invocado — a validação deve impedir isso).
    real_store = ClipImageStore(AsyncQdrantClient(location=":memory:"))
    real_embedder = ClipEmbedder()

    dummy_llm = MagicMock()
    dummy_llm.is_model_ready = AsyncMock(return_value=True)
    dummy_rag = MagicMock()
    dummy_rag.search = AsyncMock(return_value=[])
    dummy_stt = MagicMock()
    dummy_stt.transcribe = AsyncMock(return_value="")

    app.dependency_overrides[get_local_client] = lambda: dummy_llm
    app.dependency_overrides[get_external_client] = lambda: dummy_llm
    app.dependency_overrides[get_rag_client] = lambda: dummy_rag
    app.dependency_overrides[get_stt_client] = lambda: dummy_stt
    app.dependency_overrides[get_clip_store] = lambda: real_store
    app.dependency_overrides[get_clip_embedder] = lambda: real_embedder
    app.dependency_overrides[get_complexity_strategy] = lambda: "heuristic"
    # `calendar_client`/`scheduling_config` ausentes (None) — mesma razão do
    # `_build_app` de test_chat_api.py: este teste nem chega ao orchestrator
    # (a validação de formato barra antes, com 400), só precisa que a
    # dependência resolva sem estourar `AttributeError` em app.state.
    app.dependency_overrides[get_calendar_client] = lambda: None
    app.dependency_overrides[get_scheduling_config] = lambda: None
    app.dependency_overrides[get_sales_catalog_client] = lambda: None
    # Task 7 (R8): `send_message` agora também depende de `get_db_session`
    # (persistência de escalonamento do Monitor de Tom) — precisa resolver
    # sem estourar AttributeError em app.state mesmo neste teste, que nem
    # chega a escalar (a validação de formato barra antes, com 400).
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.state.image_internal_confidence = 0.30
    app.state.image_external_confidence = 0.80
    client = TestClient(app)
    lixo_b64 = base64.b64encode(b"isto-nao-e-uma-imagem").decode()
    resp = client.post("/api/chat/messages", json={"image": lixo_b64})

    assert resp.status_code == 400
