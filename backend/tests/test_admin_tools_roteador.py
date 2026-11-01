import pytest

from app.admin_tools import ferramentas_produto  # noqa: F401  (registra as ferramentas)
from app.admin_tools.intencao import detectar_escrita
from app.admin_tools.roteador import interpretar_escrita


@pytest.mark.parametrize(
    ("mensagem", "esperado"),
    [
        ("inclua o produto Câmera X na categoria CFTV por 199,90", True),
        ("altere o nome do produto 12 para Câmera Y", True),
        ("mude a descrição do iDFace Max", True),
        ("dê baixa de 5 unidades do produto 3 no CD Sul", True),
        ("cancele a venda 6f1e…", True),
        ("liste os produtos", False),
        ("qual o prazo de entrega?", False),
    ],
)
def test_detectar_escrita(mensagem, esperado):
    assert detectar_escrita(mensagem) is esperado


class _LLM:
    def __init__(self, texto):
        self.texto = texto

    async def generate(self, prompt):
        class _R:
            pass

        r = _R()
        r.response = r.text = self.texto
        return r


class _LLMQuebrado:
    async def generate(self, prompt):
        raise RuntimeError("ollama fora do ar")


@pytest.mark.asyncio
async def test_interpretar_escrita_extrai_ferramenta_e_argumentos():
    llm = _LLM(
        '{"ferramenta": "alterar_nome_produto", "argumentos": {"produto": 12, "novo_nome": "Y"}}'
    )
    assert await interpretar_escrita(llm, "altere o nome do produto 12 para Y") == {
        "ferramenta": "alterar_nome_produto",
        "argumentos": {"produto": 12, "novo_nome": "Y"},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resposta",
    [
        "texto livre",
        '{"ferramenta": "apagar_tudo", "argumentos": {}}',
        '{"argumentos": {}}',
        '{"ferramenta": null}',
        "{json quebrado}",
    ],
)
async def test_interpretar_escrita_ignora_resposta_fora_do_catalogo(resposta):
    assert await interpretar_escrita(_LLM(resposta), "x") is None


@pytest.mark.asyncio
async def test_interpretar_escrita_llm_fora_do_ar_devolve_none():
    assert await interpretar_escrita(_LLMQuebrado(), "x") is None
