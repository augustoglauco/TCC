import pytest

from app.admin_tools.handler import processar_pedido_admin
from app.admin_tools.intencao import detectar_consulta
from app.router.orchestrator import RouterDecision, TokenEvent


@pytest.mark.parametrize(
    ("mensagem", "esperado"),
    [
        ("consulte quantos pedidos foram cancelados", True),
        ("liste os produtos da categoria CFTV", True),
        ("mostre o estoque do iDFace", True),
        ("qual o horário de atendimento?", False),
        ("gere um gráfico de vendas", False),
    ],
)
def test_detectar_consulta(mensagem, esperado):
    assert detectar_consulta(mensagem) is esperado


class _LLM:
    async def generate(self, prompt):
        class _R:
            response = text = '{"sql": "SELECT 1 AS um"}'

        return _R()


class _LLMFixo:
    def __init__(self, texto):
        self._texto = texto

    async def generate(self, prompt):
        class _R:
            pass

        r = _R()
        r.response = r.text = self._texto
        return r


class _LLMQuebrado:
    async def generate(self, prompt):
        raise RuntimeError("ollama fora do ar")


class _Maker:
    def __init__(self, session):
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *a):
        return False


async def _rodar(db_session, llm, msg="liste os produtos", is_admin=True):
    return await _coletar(
        processar_pedido_admin(
            msg,
            is_admin=is_admin,
            local_client=llm,
            db_sessionmaker=_Maker(db_session),
            intent_router_provider="heuristica_llm",
        )
    )


def _texto_e_decisao(eventos):
    token = next(e for e in eventos if isinstance(e, TokenEvent))
    decisao = next(e for e in eventos if isinstance(e, RouterDecision))
    return token.text, decisao


async def _coletar(gerador):
    return [e async for e in gerador]


@pytest.mark.asyncio
async def test_nao_admin_nao_executa_consulta(db_session):
    eventos = await _coletar(
        processar_pedido_admin(
            "liste os produtos",
            is_admin=False,
            local_client=_LLMQuebrado(),
            db_sessionmaker=lambda: db_session,
            intent_router_provider="heuristica_llm",
        )
    )
    assert eventos == []


@pytest.mark.asyncio
async def test_admin_recebe_card_tabela_com_o_resultado(db_session, monkeypatch):
    class _Maker:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *a):
            return False

    eventos = await _coletar(
        processar_pedido_admin(
            "liste os produtos",
            is_admin=True,
            local_client=_LLM(),
            db_sessionmaker=_Maker(),
            intent_router_provider="heuristica_llm",
        )
    )
    decisao = next(e for e in eventos if isinstance(e, RouterDecision))
    assert decisao.card.tipo == "tabela"
    assert decisao.card.colunas == ["um"]
    assert decisao.card.linhas == [[1]]
    token = next(e for e in eventos if isinstance(e, TokenEvent))
    assert token.text == "Encontrei 1 linha(s)."


@pytest.mark.asyncio
async def test_json_invalido_do_modelo_vira_mensagem_sem_card(db_session):
    texto, decisao = _texto_e_decisao(await _rodar(db_session, _LLMFixo("não sei")))
    assert texto.startswith("Não consegui montar uma consulta")
    assert decisao.card is None


@pytest.mark.asyncio
async def test_sql_de_escrita_vira_mensagem_de_consulta_nao_permitida(db_session):
    llm = _LLMFixo('{"sql": "DELETE FROM produtos"}')
    texto, decisao = _texto_e_decisao(await _rodar(db_session, llm))
    assert texto.startswith("Essa consulta não é permitida")
    assert decisao.card is None


@pytest.mark.asyncio
async def test_resultado_vazio_avisa_sem_card(db_session):
    llm = _LLMFixo('{"sql": "SELECT id FROM produtos WHERE 1 = 0"}')
    texto, decisao = _texto_e_decisao(await _rodar(db_session, llm))
    assert texto == "A consulta não retornou nenhuma linha."
    assert decisao.card is None


@pytest.mark.asyncio
async def test_erro_de_banco_com_sql_errado_nao_quebra_o_turno(db_session):
    llm = _LLMFixo('{"sql": "SELECT coluna_inexistente FROM produtos"}')
    texto, decisao = _texto_e_decisao(await _rodar(db_session, llm))
    assert texto.startswith("A consulta falhou")
    assert decisao.card is None


@pytest.mark.asyncio
async def test_llm_que_levanta_excecao_nao_quebra_o_turno(db_session):
    texto, decisao = _texto_e_decisao(await _rodar(db_session, _LLMQuebrado()))
    assert texto.startswith("A consulta falhou")
    assert decisao.card is None


@pytest.mark.asyncio
@pytest.mark.parametrize("msg", ["gere um gráfico de vendas", "qual o horário de atendimento?"])
async def test_mensagens_que_nao_sao_consulta_nao_emitem_eventos(db_session, msg):
    assert await _rodar(db_session, _LLMQuebrado(), msg=msg) == []


# --- escrita (Task 3) ---------------------------------------------------------


async def _rodar_escrita(db_session, llm, msg, *, is_admin=True, admin_id=1):
    return await _coletar(
        processar_pedido_admin(
            msg,
            is_admin=is_admin,
            local_client=llm,
            db_sessionmaker=_Maker(db_session),
            intent_router_provider="heuristica_llm",
            admin_id=admin_id,
        )
    )


@pytest.mark.asyncio
async def test_admin_pede_alteracao_e_recebe_proposta_sem_gravar(db_session):
    from decimal import Decimal

    from app.admin_tools import ferramentas_produto  # noqa: F401
    from app.db.catalog import criar_produto, obter_produto

    p = await criar_produto(
        db_session, nome="Original", descricao="d", preco=Decimal("1"), categoria="x"
    )
    llm = _LLMFixo(
        '{"ferramenta": "alterar_nome_produto", '
        f'"argumentos": {{"produto": {p.id}, "novo_nome": "Y"}}}}'
    )
    eventos = await _rodar_escrita(db_session, llm, f"altere o nome do produto {p.id} para Y")
    _, decisao = _texto_e_decisao(eventos)
    assert decisao.card.tipo == "acao_proposta"
    assert decisao.card.depois == {"nome": "Y"}
    assert (await obter_produto(db_session, p.id)).nome == "Original"


@pytest.mark.asyncio
async def test_escrita_de_nao_admin_ou_sem_admin_id_nao_emite_eventos(db_session):
    msg = "altere o nome do produto 1 para Y"
    assert await _rodar_escrita(db_session, _LLMQuebrado(), msg, is_admin=False) == []
    assert await _rodar_escrita(db_session, _LLMQuebrado(), msg, admin_id=None) == []


@pytest.mark.asyncio
async def test_escrita_nao_entendida_pede_reformulacao(db_session):
    llm = _LLMFixo('{"ferramenta": null}')
    texto, decisao = _texto_e_decisao(
        await _rodar_escrita(db_session, llm, "altere o nome do produto")
    )
    assert texto.startswith("Não entendi")
    assert decisao.card is None


@pytest.mark.asyncio
async def test_escrita_com_llm_quebrado_nao_derruba_o_turno(db_session):
    texto, decisao = _texto_e_decisao(
        await _rodar_escrita(db_session, _LLMQuebrado(), "altere o nome do produto 1 para Y")
    )
    assert texto.startswith("Não entendi")
    assert decisao.card is None


@pytest.mark.asyncio
async def test_escrita_invalida_ou_ambigua_vira_mensagem(db_session):
    llm = _LLMFixo(
        '{"ferramenta": "alterar_nome_produto", '
        '"argumentos": {"produto": 999999, "novo_nome": "Y"}}'
    )
    texto, decisao = _texto_e_decisao(
        await _rodar_escrita(db_session, llm, "altere o nome do produto 999999 para Y")
    )
    assert "não encontrado" in texto
    assert decisao.card is None


@pytest.mark.parametrize(
    ("token", "esperado"), [("mock-token-7", 7), ("mock-token-x", None), (None, None), ("", None)]
)
def test_admin_id_do_token(token, esperado):
    from app.api.chat import _admin_id_do_token

    assert _admin_id_do_token(token) == esperado
