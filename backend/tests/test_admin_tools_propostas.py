from datetime import UTC, datetime, timedelta

import pytest

from app.admin_tools import ferramentas
from app.admin_tools.ferramentas import Previa
from app.admin_tools.propostas import (
    PROPOSTA_TTL,
    PropostaInvalidaError,
    cancelar,
    confirmar,
    criar_proposta,
)


class _Fake:
    nome = "fake"

    def __init__(self):
        self.execucoes = 0

    async def preparar(self, session, args):
        return Previa(titulo="Fake", antes={"v": 1}, depois={"v": args["v"]})

    async def executar(self, session, args, *, admin_id):
        self.execucoes += 1
        return {"v": args["v"]}


class _Quebra(_Fake):
    async def executar(self, session, args, *, admin_id):
        raise RuntimeError("falha no meio da escrita")


@pytest.fixture
def fake(monkeypatch):
    f = _Fake()
    monkeypatch.setitem(ferramentas.FERRAMENTAS, "fake", f)
    return f


@pytest.mark.asyncio
async def test_criar_proposta_grava_previa_sem_executar(db_session, fake):
    acao, previa = await criar_proposta(
        db_session, admin_id=1, ferramenta="fake", argumentos={"v": 2}
    )
    assert acao.status == "proposta" and acao.antes == {"v": 1} and acao.depois == {"v": 2}
    assert previa.titulo == "Fake" and fake.execucoes == 0


@pytest.mark.asyncio
async def test_confirmar_executa_uma_vez_e_registra(db_session, fake):
    acao, _ = await criar_proposta(db_session, admin_id=1, ferramenta="fake", argumentos={"v": 2})
    feita = await confirmar(db_session, acao.id, admin_id=1)
    assert feita.status == "executada" and feita.executado_em is not None and fake.execucoes == 1
    with pytest.raises(PropostaInvalidaError):
        await confirmar(db_session, acao.id, admin_id=1)  # reconfirmar não grava de novo
    assert fake.execucoes == 1


@pytest.mark.asyncio
async def test_confirmar_proposta_de_outro_admin_ou_expirada_falha(db_session, fake):
    acao, _ = await criar_proposta(db_session, admin_id=1, ferramenta="fake", argumentos={"v": 2})
    with pytest.raises(PropostaInvalidaError):
        await confirmar(db_session, acao.id, admin_id=2)
    depois = datetime.now(UTC) + PROPOSTA_TTL + timedelta(seconds=1)
    with pytest.raises(PropostaInvalidaError):
        await confirmar(db_session, acao.id, admin_id=1, agora=depois)
    assert fake.execucoes == 0
    await db_session.refresh(acao)
    assert acao.status == "expirada"


@pytest.mark.asyncio
async def test_cancelar_marca_cancelada_e_nao_executa(db_session, fake):
    acao, _ = await criar_proposta(db_session, admin_id=1, ferramenta="fake", argumentos={"v": 2})
    feita = await cancelar(db_session, acao.id, admin_id=1)
    assert feita.status == "cancelada" and fake.execucoes == 0


@pytest.mark.asyncio
async def test_cancelar_proposta_ja_resolvida_falha(db_session, fake):
    acao, _ = await criar_proposta(db_session, admin_id=1, ferramenta="fake", argumentos={"v": 2})
    await confirmar(db_session, acao.id, admin_id=1)
    with pytest.raises(PropostaInvalidaError):
        await cancelar(db_session, acao.id, admin_id=1)
    await db_session.refresh(acao)
    assert acao.status == "executada"


@pytest.mark.asyncio
async def test_ferramenta_desconhecida_levanta(db_session):
    with pytest.raises(PropostaInvalidaError):
        await criar_proposta(db_session, admin_id=1, ferramenta="nao_existe", argumentos={})


@pytest.mark.asyncio
async def test_executar_que_levanta_nao_grava_e_proposta_continua_pendente(db_session, monkeypatch):
    monkeypatch.setitem(ferramentas.FERRAMENTAS, "fake", _Quebra())
    acao, _ = await criar_proposta(db_session, admin_id=1, ferramenta="fake", argumentos={"v": 2})
    with pytest.raises(RuntimeError):
        await confirmar(db_session, acao.id, admin_id=1)
    await db_session.refresh(acao)
    assert acao.status == "proposta" and acao.executado_em is None
