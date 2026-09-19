from app.router.llm_client import LLMResponse
from app.rag.crawler_classifier import classify_page


class _FakeLLMClient:
    def __init__(self, texto_resposta: str) -> None:
        self._texto_resposta = texto_resposta

    async def generate(self, prompt: str) -> LLMResponse:
        return LLMResponse(text=self._texto_resposta, total_duration_ms=1.0)

    def generate_stream(self, prompt: str):
        raise NotImplementedError

    async def is_model_ready(self) -> bool:
        return True


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
