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
        return_value=MagicMock(
            text='{"domain":"vendas","complexity":"baixa","confidence":0.9}'
        )
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
    """image + message: OCR mockado retorna texto, que é concatenado."""
    monkeypatch.setattr(
        "app.api.chat.extract_text_from_base64",
        lambda b64: "TEXTO DO OCR",
    )
    resp = chat_client.post(
        "/api/chat/messages",
        json={"message": "o que é isso?", "image": _png_b64()},
    )
    assert resp.status_code == 200


def test_chat_so_imagem_sem_texto(chat_client, monkeypatch):
    """Só image (sem message): OCR extrai texto e a request prossegue."""
    monkeypatch.setattr(
        "app.api.chat.extract_text_from_base64",
        lambda b64: "TEXTO DO OCR",
    )
    resp = chat_client.post(
        "/api/chat/messages",
        json={"image": _png_b64()},
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
        json={"message": "resuma esse comprovante", "image": _png_b64()},
    )
    assert resp.status_code == 200


def test_chat_ocr_indisponivel_sem_texto_retorna_503(chat_client, monkeypatch):
    """OCR indisponível + sem message: deve retornar 503."""
    monkeypatch.setattr(
        "app.api.chat.extract_text_from_base64",
        lambda b64: (_ for _ in ()).throw(OcrIndisponivelError("tesseract ausente")),
    )
    resp = chat_client.post(
        "/api/chat/messages",
        json={"image": _png_b64()},
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
        json={"image": base64.b64encode(b"\x00\x01\x02").decode()},
    )
    assert resp.status_code == 400
