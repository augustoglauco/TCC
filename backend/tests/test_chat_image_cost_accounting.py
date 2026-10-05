import base64
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.main import create_app
from app.rag.clip_embedder import CLIP_VECTOR_DIMENSION
from app.router.openrouter_client import VisionResult
from app.router.rag_client import Document


class _FakeClipEmbedder:
    async def embed_images(self, images):
        return [[0.1] * CLIP_VECTOR_DIMENSION for _ in images]

    async def embed_texts(self, texts):
        return [[0.1] * CLIP_VECTOR_DIMENSION for _ in texts]


def _png_b64() -> str:
    # 1x1 PNG dummy
    raw = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    return base64.b64encode(raw).decode()


def _parse_sse(texto: str) -> list[tuple[str, dict]]:
    eventos = []
    for bloco in texto.strip().split("\n\n"):
        tipo = dados = None
        for linha in bloco.split("\n"):
            if linha.startswith("event:"):
                tipo = linha[len("event:") :].strip()
            elif linha.startswith("data:"):
                dados = json.loads(linha[len("data:") :].strip())
        if tipo and dados is not None:
            eventos.append((tipo, dados))
    return eventos


def test_chat_image_external_vision_populates_done_event_costs():
    app = create_app()

    store = MagicMock()
    # CLIP sem match para forçar fallback externo de visão
    store.search_by_image = AsyncMock(return_value=[])
    app.state.clip_image_store = store
    app.state.clip_embedder = _FakeClipEmbedder()

    vision_res = VisionResult(
        content=json.dumps({"produto": "Câmera Bullet HD", "e_do_portfolio": True, "confianca": 0.92}),
        prompt_tokens=1500,
        completion_tokens=70,
        total_tokens=1570,
        cost_prompt_usd=0.0075,
        cost_completion_usd=0.00105,
        estimated_cost_usd=0.00855,
        model_name="google/gemma-4-31b-it:free",
    )

    vision = MagicMock()
    vision.describe_image = AsyncMock(return_value=vision_res)
    app.state.external_client = vision

    rag = MagicMock()
    rag.search = AsyncMock(
        return_value=[Document(content="Manual da Câmera Bullet", source="manual.pdf", score=0.9)]
    )
    app.state.rag_client = rag

    stt = MagicMock()
    stt.transcribe = AsyncMock(return_value="")
    app.state.stt_client = stt

    client = TestClient(app)
    resp = client.post("/api/chat/messages", json={"image": _png_b64()})
    assert resp.status_code == 200

    eventos = _parse_sse(resp.text)
    done = next(dados for tipo, dados in eventos if tipo == "done")

    assert done["domain"] == "vendas"
    assert done["backend_used"] == "externo"
    assert done["prompt_tokens"] == 1500
    assert done["completion_tokens"] == 70
    assert done["total_tokens"] == 1570
    assert pytest.approx(done["cost_prompt_usd"], 0.00001) == 0.0075
    assert pytest.approx(done["cost_completion_usd"], 0.00001) == 0.00105
    assert pytest.approx(done["estimated_cost_usd"], 0.00001) == 0.00855
    assert done.get("vision_used") is True
