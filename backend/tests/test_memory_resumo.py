"""Resumo automático periódico da conversa (R9, Fase 6) — `app.memory.resumo`."""

import logging

import pytest

from app.db.engine import create_db_engine, create_session_factory
from app.db.models import Base, Conversa
from app.memory.resumo import INTERVALO_RESUMO, atualizar_resumo, precisa_resumir
from app.memory.store import registrar_troca
from app.router.llm_client import LLMResponse


class _FakeLLM:
    def __init__(self, texto: str = "Cliente quer 2 geradores GD-15.", falha: bool = False):
        self._texto = texto
        self._falha = falha
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> LLMResponse:
        self.prompts.append(prompt)
        if self._falha:
            raise ConnectionError("ollama fora do ar")
        return LLMResponse(text=self._texto, total_duration_ms=1.0)


@pytest.fixture
async def factory():
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield create_session_factory(engine)
    await engine.dispose()


async def _trocas(factory, conversation_id: str, quantidade: int, inicio: int = 1) -> None:
    async with factory() as session:
        for i in range(inicio, inicio + quantidade):
            await registrar_troca(
                session, conversation_id, f"pergunta {i}", f"resposta {i}", "vendas"
            )


def test_precisa_resumir_a_cada_seis_mensagens_novas():
    assert INTERVALO_RESUMO == 6
    assert not precisa_resumir(total_mensagens=4, mensagens_resumidas=0)
    assert precisa_resumir(total_mensagens=6, mensagens_resumidas=0)
    assert not precisa_resumir(total_mensagens=10, mensagens_resumidas=6)
    assert precisa_resumir(total_mensagens=12, mensagens_resumidas=6)


async def test_primeiro_resumo_cobre_as_seis_mensagens(factory):
    await _trocas(factory, "conv-r1", 3)
    llm = _FakeLLM()

    await atualizar_resumo(factory, "conv-r1", llm)

    async with factory() as session:
        conversa = await session.get(Conversa, "conv-r1")
    assert conversa.resumo == "Cliente quer 2 geradores GD-15."
    assert conversa.mensagens_resumidas == 6
    [prompt] = llm.prompts
    assert "(nenhum ainda)" in prompt
    assert "Cliente: pergunta 1" in prompt
    assert "Assistente: resposta 3" in prompt


async def test_segundo_resumo_parte_do_anterior_e_so_das_mensagens_novas(factory):
    await _trocas(factory, "conv-r2", 3)
    await atualizar_resumo(factory, "conv-r2", _FakeLLM("Resumo antigo."))
    await _trocas(factory, "conv-r2", 3, inicio=4)
    llm = _FakeLLM("Resumo novo.")

    await atualizar_resumo(factory, "conv-r2", llm)

    [prompt] = llm.prompts
    assert "Resumo antigo." in prompt
    assert "pergunta 4" in prompt
    assert "pergunta 3" not in prompt  # já coberta pelo resumo anterior
    async with factory() as session:
        conversa = await session.get(Conversa, "conv-r2")
    assert (conversa.resumo, conversa.mensagens_resumidas) == ("Resumo novo.", 12)


async def test_menos_de_seis_mensagens_novas_nao_chama_o_llm(factory):
    await _trocas(factory, "conv-r3", 2)
    llm = _FakeLLM()

    await atualizar_resumo(factory, "conv-r3", llm)

    assert llm.prompts == []


async def test_falha_do_llm_nao_levanta_e_deixa_para_a_proxima_troca(factory, caplog):
    await _trocas(factory, "conv-r4", 3)

    with caplog.at_level(logging.WARNING, logger="app.memory.resumo"):
        await atualizar_resumo(factory, "conv-r4", _FakeLLM(falha=True))

    async with factory() as session:
        conversa = await session.get(Conversa, "conv-r4")
    assert (conversa.resumo, conversa.mensagens_resumidas) == (None, 0)
    assert any(r.getMessage() == "resumo_falhou" for r in caplog.records)
