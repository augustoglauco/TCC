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


@pytest.mark.asyncio
async def test_postgres_recebe_timeout_e_transacao_somente_leitura(monkeypatch):
    from types import SimpleNamespace

    from app.admin_tools import consulta

    emitidos = []

    class _Sessao:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        async def execute(self, stmt):
            emitidos.append(str(stmt))

    async def _ro(session, sql):
        return [{"ok": 1}]

    monkeypatch.setattr(consulta, "execute_readonly_sql", _ro)
    assert await consulta.executar_consulta(_Sessao(), "SELECT 1") == [{"ok": 1}]
    assert emitidos == [
        f"SET LOCAL statement_timeout = {consulta.TEMPO_MAX_MS}",
        "SET TRANSACTION READ ONLY",
    ]
