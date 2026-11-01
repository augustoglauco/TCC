import pytest

from app.admin_tools.consulta import executar_consulta, gerar_sql
from app.services.safe_sql import SQLSecurityError


@pytest.mark.asyncio
async def test_executar_consulta_devolve_linhas(db_session):
    linhas = await executar_consulta(db_session, "SELECT 1 AS um")
    assert linhas == [{"um": 1}]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM produtos",
        "SELECT * FROM produtos; DROP TABLE produtos",
        "SELECT * FROM usuarios_secretos",
        "UPDATE produtos SET preco = 0",
    ],
)
async def test_executar_consulta_bloqueia_escrita_e_tabela_fora_da_lista(db_session, sql):
    with pytest.raises(SQLSecurityError):
        await executar_consulta(db_session, sql)


class _LLM:
    def __init__(self, texto):
        self._texto = texto

    async def generate(self, prompt):
        class _R:
            response = self._texto
            text = self._texto

        return _R()


@pytest.mark.asyncio
async def test_gerar_sql_extrai_o_sql_do_json_do_modelo():
    llm = _LLM('{"sql": "SELECT nome FROM produtos"}')
    assert await gerar_sql(llm, "liste os produtos", "esquema") == "SELECT nome FROM produtos"


@pytest.mark.asyncio
async def test_gerar_sql_devolve_none_se_o_modelo_nao_responde_json():
    assert await gerar_sql(_LLM("não sei"), "x", "esquema") is None
