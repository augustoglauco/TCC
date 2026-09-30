"""Testes para app.rag.image_identification (R6, Fase 3)."""

import json
from decimal import Decimal

from app.rag.image_identification import identify_product_by_image
from app.rag.image_search import ImageSearchResult
from app.router.openrouter_client import VisionModelIndisponivelError
from app.router.rag_client import Document
from app.router.sales_catalog import CandidatoProduto, DadosCatalogoVendas

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

    async def search(self, query: str, domain: str, **kwargs) -> list[Document]:
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


# Detalhes do produto vêm do banco (decisão de 2026-09-27); o RAG fica para
# produto que ainda não está no cadastro.

_RADIO = DadosCatalogoVendas(
    produto_nome="Rádio Comunicador Analógico RC 4102g2",
    estoque_total=17,
    descricao="Rádio portátil para comunicação em campo.",
    especificacoes_tecnicas="16 canais; IP54.",
    dimensoes_cm="12x6x4",
    peso_kg=Decimal("0.300"),
)


class _FakeSalesCatalog:
    def __init__(self, candidatos=None, dados=_RADIO, exc: Exception | None = None) -> None:
        self._candidatos = candidatos or []
        self._dados = dados
        self._exc = exc
        self.detalhes_consultados: list[int] = []

    async def buscar_candidatos(self, termos, limite=10):
        if self._exc is not None:
            raise self._exc
        return self._candidatos

    async def consultar_detalhes(self, produto_id, produto_relacionado_id, quantidade):
        if self._exc is not None:
            raise self._exc
        self.detalhes_consultados.append(produto_id)
        return self._dados


async def _identificar(store, vision, rag, catalogo):
    return await identify_product_by_image(
        _IMG,
        clip_store=store,
        clip_embedder=object(),
        vision_client=vision,
        rag_client=rag,
        internal_confidence=0.30,
        external_confidence=0.80,
        sales_catalog_client=catalogo,
    )


async def test_acerto_interno_com_produto_id_traz_a_ficha_do_banco_sem_rag():
    hit = ImageSearchResult(
        image_id="i1", filename="radio.jpg", domain="vendas", score=0.5, produto_id=7
    )
    rag = _FakeRAGClient(documents=[Document(content="Relógio de ponto", source="x", score=1)])
    catalogo = _FakeSalesCatalog()

    result = await _identificar(_FakeClipStore([hit]), _FakeVisionClient(), rag, catalogo)

    assert result.status == "encontrado_interno"
    assert result.produto == "Rádio Comunicador Analógico RC 4102g2"
    assert result.produto_id == 7
    assert catalogo.detalhes_consultados == [7]
    assert "Rádio portátil para comunicação em campo." in result.detalhes
    assert "Especificações técnicas: 16 canais; IP54." in result.detalhes
    assert "Dimensões: 12x6x4 cm · Peso: 0.300 kg" in result.detalhes
    assert "Relógio" not in result.detalhes
    assert rag.queries == []


async def test_visao_externa_com_nome_unico_no_banco_traz_a_ficha():
    vision = _FakeVisionClient(
        answer={"produto": "Rádio RC 4102g2", "e_do_portfolio": True, "confianca": 0.9}
    )
    catalogo = _FakeSalesCatalog(
        candidatos=[CandidatoProduto(id=7, nome="Rádio RC 4102g2 Analógico", categoria="radios")]
    )
    rag = _FakeRAGClient()

    result = await _identificar(_FakeClipStore(), vision, rag, catalogo)

    assert result.status == "encontrado_externo"
    assert result.produto_id == 7
    assert result.fonte == "visao_externa+catalogo"
    assert "16 canais" in result.detalhes
    assert rag.queries == []


async def test_nome_generico_com_varios_produtos_cai_no_rag():
    vision = _FakeVisionClient(
        answer={"produto": "Câmera IP", "e_do_portfolio": True, "confianca": 0.9}
    )
    catalogo = _FakeSalesCatalog(
        candidatos=[
            CandidatoProduto(id=1, nome="Câmera IP 2MP", categoria="cftv"),
            CandidatoProduto(id=2, nome="Câmera IP 4MP", categoria="cftv"),
        ]
    )
    rag = _FakeRAGClient(documents=[Document(content="Câmera IP manual", source="m", score=1)])

    result = await _identificar(_FakeClipStore(), vision, rag, catalogo)

    assert result.fonte == "visao_externa+rag_texto"
    assert result.detalhes == "Câmera IP manual"
    assert catalogo.detalhes_consultados == []


async def test_banco_fora_do_ar_cai_no_rag():
    hit = ImageSearchResult(
        image_id="i1", filename="Camera XPTO", domain="vendas", score=0.5, produto_id=3
    )
    rag = _FakeRAGClient(documents=[Document(content="Camera XPTO manual", source="m", score=1)])

    result = await _identificar(
        _FakeClipStore([hit]),
        _FakeVisionClient(),
        rag,
        _FakeSalesCatalog(exc=ConnectionError("banco fora")),
    )

    assert result.status == "encontrado_interno"
    assert result.produto == "Camera XPTO"
    assert result.detalhes == "Camera XPTO manual"
