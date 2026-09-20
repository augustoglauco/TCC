"""Testes para app.rag.image_identification (R6, Fase 3)."""

import json

from app.rag.image_identification import identify_product_by_image
from app.rag.image_search import ImageSearchResult
from app.router.openrouter_client import VisionModelIndisponivelError
from app.router.rag_client import Document

_IMG = b"fake-image-bytes"


class _FakeClipStore:
    def __init__(self, results: list[ImageSearchResult] | None = None) -> None:
        self._results = results or []
        self.called = False

    async def search_by_image(self, embedder, image_bytes, domain=None):
        self.called = True
        return self._results


class _FakeVisionClient:
    def __init__(self, answer: dict | None = None, raise_exc: Exception | None = None) -> None:
        self._answer = answer
        self._raise = raise_exc
        self.called = False

    async def describe_image(self, image_bytes: bytes, prompt: str) -> str:
        self.called = True
        if self._raise is not None:
            raise self._raise
        return json.dumps(self._answer)


class _FakeRAGClient:
    def __init__(self, documents: list[Document] | None = None) -> None:
        self._documents = documents or []
        self.queries: list[str] = []

    async def search(self, query: str, domain: str) -> list[Document]:
        self.queries.append(query)
        return self._documents


def _clip_hit(score: float) -> ImageSearchResult:
    return ImageSearchResult(image_id="i1", filename="Camera XPTO", domain="vendas", score=score)


async def test_acerto_interno_nao_chama_o_externo():
    store = _FakeClipStore(results=[_clip_hit(0.42)])
    vision = _FakeVisionClient()
    rag = _FakeRAGClient(documents=[Document(content="detalhes da câmera", source="cat", score=1)])

    result = await identify_product_by_image(
        _IMG,
        clip_store=store,
        clip_embedder=object(),
        vision_client=vision,
        rag_client=rag,
        internal_confidence=0.30,
        external_confidence=0.80,
    )

    assert result.status == "encontrado_interno"
    assert result.produto == "Camera XPTO"
    assert result.detalhes == "detalhes da câmera"
    assert result.confianca_interna == 0.42
    assert vision.called is False  # não gastou chamada externa


async def test_interno_abaixo_do_limiar_cai_para_externo_confirmado():
    store = _FakeClipStore(results=[_clip_hit(0.10)])  # abaixo de 0.30
    vision = _FakeVisionClient(
        answer={"produto": "Catraca X", "e_do_portfolio": True, "confianca": 0.9}
    )
    rag = _FakeRAGClient(documents=[Document(content="ficha da catraca", source="cat", score=1)])

    result = await identify_product_by_image(
        _IMG,
        clip_store=store,
        clip_embedder=object(),
        vision_client=vision,
        rag_client=rag,
        internal_confidence=0.30,
        external_confidence=0.80,
    )

    assert vision.called is True
    assert result.status == "encontrado_externo"
    assert result.produto == "Catraca X"
    assert result.detalhes == "ficha da catraca"
    assert result.confianca_externa == 0.9


async def test_externo_fora_do_portfolio_vira_nao_identificado():
    store = _FakeClipStore(results=[])
    vision = _FakeVisionClient(
        answer={"produto": "Geladeira", "e_do_portfolio": False, "confianca": 0.95}
    )
    rag = _FakeRAGClient()

    result = await identify_product_by_image(
        _IMG,
        clip_store=store,
        clip_embedder=object(),
        vision_client=vision,
        rag_client=rag,
        internal_confidence=0.30,
        external_confidence=0.80,
    )

    assert result.status == "nao_identificado"
    assert result.mensagem is not None


async def test_externo_confianca_baixa_vira_nao_identificado():
    store = _FakeClipStore(results=[])
    vision = _FakeVisionClient(
        answer={"produto": "Sensor", "e_do_portfolio": True, "confianca": 0.5}
    )
    rag = _FakeRAGClient()

    result = await identify_product_by_image(
        _IMG,
        clip_store=store,
        clip_embedder=object(),
        vision_client=vision,
        rag_client=rag,
        internal_confidence=0.30,
        external_confidence=0.80,
    )

    assert result.status == "nao_identificado"


async def test_visao_indisponivel_vira_nao_identificado():
    store = _FakeClipStore(results=[])
    vision = _FakeVisionClient(raise_exc=VisionModelIndisponivelError("sem modelo"))
    rag = _FakeRAGClient()

    result = await identify_product_by_image(
        _IMG,
        clip_store=store,
        clip_embedder=object(),
        vision_client=vision,
        rag_client=rag,
        internal_confidence=0.30,
        external_confidence=0.80,
    )

    assert result.status == "nao_identificado"


async def test_recent_messages_entram_na_busca_do_rag():
    store = _FakeClipStore(results=[])
    vision = _FakeVisionClient(
        answer={"produto": "Câmera IP", "e_do_portfolio": True, "confianca": 0.9}
    )
    rag = _FakeRAGClient(documents=[Document(content="x", source="cat", score=1)])

    await identify_product_by_image(
        _IMG,
        clip_store=store,
        clip_embedder=object(),
        vision_client=vision,
        rag_client=rag,
        internal_confidence=0.30,
        external_confidence=0.80,
        recent_messages=["preciso de uma câmera externa"],
    )

    # A query do RAG concatena o contexto recente ao nome identificado.
    assert "preciso de uma câmera externa" in rag.queries[0]
    assert "Câmera IP" in rag.queries[0]
