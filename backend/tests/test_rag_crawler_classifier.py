import asyncio

import pytest

from app.background_tasks import _background_tasks
from app.rag.crawler_classifier import classify_page


class _FakeLLMClient:
    """Mock de LLM único deste arquivo — carrega os campos de uso (tokens,
    custo, modelo) para cobrir tanto a classificação em si quanto a
    telemetria no ledger unificado (item E)."""

    def __init__(
        self,
        texto_resposta: str,
        prompt_tokens=None,
        completion_tokens=None,
        estimated_cost_usd=None,
        model_name=None,
    ) -> None:
        self.text = texto_resposta
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.estimated_cost_usd = estimated_cost_usd
        self.model_name = model_name
        self.model = model_name

    async def generate(self, prompt: str):
        return self


async def test_classify_page_json_valido():
    llm = _FakeLLMClient('{"domain": "suporte", "confidence": 0.92}')

    resultado = await classify_page(llm, "conteúdo da página")

    assert resultado.domain == "suporte"
    assert resultado.confidence == 0.92


async def test_classify_page_com_code_fence():
    llm = _FakeLLMClient('```json\n{"domain": "vendas", "confidence": 0.8}\n```')

    resultado = await classify_page(llm, "conteúdo da página")

    assert resultado.domain == "vendas"
    assert resultado.confidence == 0.8


async def test_classify_page_json_malformado_confidence_zero():
    llm = _FakeLLMClient("não é json")

    resultado = await classify_page(llm, "conteúdo da página")

    assert resultado.confidence == 0.0


async def test_classify_page_domain_invalido_confidence_zero():
    llm = _FakeLLMClient('{"domain": "financeiro", "confidence": 0.9}')

    resultado = await classify_page(llm, "conteúdo da página")

    assert resultado.confidence == 0.0


@pytest.mark.asyncio
async def test_classify_page_registra_uso_no_ledger(monkeypatch):
    """O classificador do crawler foi o último ponto de uso de IA a entrar
    no ledger unificado (item E) — antes disso escrevia em
    `IngestionCostEvent`, que o painel deixou de ler."""
    registros: list[dict] = []

    async def _fake_registrar(**kwargs):
        registros.append(kwargs)
        return None

    monkeypatch.setattr("app.rag.crawler_classifier.registrar_uso_ia", _fake_registrar)

    llm = _FakeLLMClient(
        '{"domain": "vendas", "confidence": 0.9}',
        prompt_tokens=500,
        completion_tokens=20,
        estimated_cost_usd=0.0008,
        model_name="gpt-x",
    )

    resultado = await classify_page(llm, "promoções", source_identifier="https://ex.com/p")
    await asyncio.sleep(0)  # dá chance à background task de rodar (fire-and-forget)

    assert resultado.domain == "vendas"
    assert len(registros) == 1
    assert registros[0]["origem"] == "admin"
    assert registros[0]["operacao"] == "classificacao_crawler"
    assert registros[0]["ambiente"] == "externo"
    assert registros[0]["modelo"] == "gpt-x"
    assert registros[0]["tokens_entrada"] == 500
    assert registros[0]["tokens_saida"] == 20
    assert registros[0]["custo_usd"] == 0.0008
    assert registros[0]["referencia_id"] == "https://ex.com/p"


@pytest.mark.asyncio
async def test_classify_page_sem_uso_reportado_registra_none_nao_zero(monkeypatch):
    """`None` = não capturado; nunca um zero fabricado (semântica do
    ledger, itens A/B/D)."""
    registros: list[dict] = []

    async def _fake_registrar(**kwargs):
        registros.append(kwargs)
        return None

    monkeypatch.setattr("app.rag.crawler_classifier.registrar_uso_ia", _fake_registrar)

    llm = _FakeLLMClient('{"domain": "suporte", "confidence": 0.5}')
    await classify_page(llm, "texto")
    await asyncio.sleep(0)  # dá chance à background task de rodar (fire-and-forget)

    assert len(registros) == 1
    assert registros[0]["tokens_entrada"] is None
    assert registros[0]["custo_usd"] is None


@pytest.mark.asyncio
async def test_classify_page_sobrevive_a_falha_de_telemetria(monkeypatch):
    """Telemetria não derruba a classificação que ela registra. A exceção
    precisa de fato acontecer aqui (não só existir como coroutine nunca
    executada) — por isso o teste espiona a chamada e aguarda a volta do
    event loop antes de checar `chamou`, e depois consome a exceção da task
    via `task.exception()` para a saída do pytest ficar limpa (sem
    "exception was never retrieved")."""
    chamou = False

    async def _explode(**kwargs):
        nonlocal chamou
        chamou = True
        raise RuntimeError("banco fora")

    monkeypatch.setattr("app.rag.crawler_classifier.registrar_uso_ia", _explode)

    antes = set(_background_tasks)
    llm = _FakeLLMClient('{"domain": "vendas", "confidence": 0.8}')
    resultado = await classify_page(llm, "texto")

    novas = set(_background_tasks) - antes
    assert len(novas) == 1
    task = novas.pop()

    assert resultado.domain == "vendas"
    assert resultado.confidence == 0.8

    await asyncio.sleep(0)  # dá chance à task de rodar e de fato explodir
    assert chamou is True
    assert task.done()
    assert isinstance(task.exception(), RuntimeError)  # consome a exceção
