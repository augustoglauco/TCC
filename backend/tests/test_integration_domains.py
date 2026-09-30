"""Testes de integração dos quatro domínios de atendimento (Fase 9,
`docs/ROADMAP.md`) através do endpoint HTTP real (`chat_router` via
`TestClient`, parseando o SSE), não chamando `handle_message` direto como
`test_orchestrator.py`.

Diferença para `test_chat_api.py`: lá, `calendar_client`/`scheduling_config`/
`sales_catalog_client` ficam sempre `None` de propósito (dependências
externas desligadas para os testes de infraestrutura do endpoint em si) —
aqui as quatro dependências externas (LLM local/externo, RAG, calendário,
catálogo de vendas) são dublês, mas TODAS ficam ligadas, para exercitar o
mecanismo que de fato distingue cada domínio:

- Vendas consulta o catálogo (desambiguação por LLM + card rico de cotação).
- Suporte só usa RAG — nunca chama o catálogo de vendas.
- Atendimento injeta o histórico de compras do cliente autenticado no prompt.
- Agendamento roda a máquina de estados real (coleta de slots →
  confirmação → criação de evento no calendário), em duas requisições HTTP
  sequenciais com o mesmo `conversation_id`.
"""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.chat import (
    get_calendar_client,
    get_clip_embedder,
    get_clip_store,
    get_complexity_strategy,
    get_external_client,
    get_local_client,
    get_rag_client,
    get_rag_client_admin,
    get_sales_catalog_client,
    get_scheduling_config,
    get_stt_client,
)
from app.api.chat import router as chat_router
from app.db.models import Cliente, ClienteCompra
from app.router.llm_client import LLMResponse, LLMStreamChunk
from app.router.rag_client import Document
from app.router.sales_catalog import CandidatoProduto, DadosCatalogoVendas
from app.router.scheduling import SchedulingConfig, reset_all_booking_slots
from tests.test_chat_api import (
    _FakeClipStore,
    _FakeRAGClient,
    _FakeSttClient,
    _find,
    _parse_sse,
    _SingleSessionMaker,
)
from tests.test_orchestrator import (
    _data_futura_valida_iso,
    _FakeCalendarClient,
    _FakeSalesCatalogClient,
)

_SCHEDULING_CONFIG = SchedulingConfig(
    timezone="America/Sao_Paulo",
    expediente_dias="seg-sex",
    expediente_inicio="09:00",
    expediente_fim="18:00",
)


class _DomainAwareLLMClient:
    """Uma única resposta fixa não serve para todos os domínios: Vendas
    (`extract_sales_slots`) e Agendamento (`extract_booking_slots`) fazem
    uma chamada de EXTRAÇÃO estruturada (JSON) via `generate()` antes da
    resposta final do playbook — esta fake inspeciona o prompt e devolve o
    JSON certo quando reconhece uma extração, por um marcador exclusivo do
    template de cada uma (`"produto_id":` de
    `app.router.sales_catalog._EXTRACTION_PROMPT_TEMPLATE`; `"confirmacao"`
    de `app.router.scheduling`); caso contrário devolve a resposta final
    configurada. Para Agendamento, distingue turno 1 (pede dados) de turno 2
    (confirma) pelo mesmo sinal que o prompt real usa: "está aguardando uma
    confirmação do cliente? sim/não" reflete `BookingSlots.awaiting_confirmation`.
    `generate_stream` (resposta final do playbook) nunca faz extração —
    extração sempre usa `generate()` (não-streaming), nunca `generate_stream`."""

    def __init__(self, resposta_final: str = "Claro, posso ajudar.") -> None:
        self._resposta_final = resposta_final
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> LLMResponse:
        self.prompts.append(prompt)
        if '"produto_id":' in prompt:
            payload = {
                "produto_id": 1,
                "produto_relacionado_id": None,
                "quantidade": 5,
                "categoria": None,
                "listar_tudo": False,
            }
        elif '"confirmacao"' in prompt:
            if "confirmação do cliente? sim" in prompt:
                payload = {
                    "data_hora": None,
                    "nome": None,
                    "email": None,
                    "telefone": None,
                    "confirmacao": True,
                }
            else:
                payload = {
                    "data_hora": _data_futura_valida_iso(),
                    "nome": "Maria",
                    "email": "maria@teste.com",
                    "telefone": "11999999999",
                    "confirmacao": None,
                }
        else:
            return LLMResponse(text=self._resposta_final, total_duration_ms=10.0)
        return LLMResponse(text=json.dumps(payload), total_duration_ms=10.0)

    async def is_model_ready(self) -> bool:
        return True

    async def describe_image(self, image_bytes: bytes, prompt: str) -> str:
        raise NotImplementedError

    async def generate_stream(self, prompt: str):
        self.prompts.append(prompt)
        yield LLMStreamChunk(text=self._resposta_final)
        yield LLMStreamChunk(done=True, total_duration_ms=10.0)


def _build_app(
    *,
    local_client,
    rag_client,
    sales_catalog_client,
    calendar_client,
    db_session,
) -> FastAPI:
    app = FastAPI()
    app.include_router(chat_router)
    app.dependency_overrides[get_local_client] = lambda: local_client
    app.dependency_overrides[get_external_client] = lambda: local_client
    app.dependency_overrides[get_rag_client] = lambda: rag_client
    app.dependency_overrides[get_rag_client_admin] = lambda: rag_client
    app.dependency_overrides[get_stt_client] = lambda: _FakeSttClient(text="")
    app.dependency_overrides[get_clip_store] = lambda: _FakeClipStore(results=[])
    app.dependency_overrides[get_clip_embedder] = lambda: object()
    app.dependency_overrides[get_complexity_strategy] = lambda: "heuristic"
    # Ao contrário de `test_chat_api.py`, as três dependências abaixo ficam
    # LIGADAS — é o ponto central destes testes (ver docstring do módulo).
    app.dependency_overrides[get_calendar_client] = lambda: calendar_client
    app.dependency_overrides[get_scheduling_config] = lambda: _SCHEDULING_CONFIG
    app.dependency_overrides[get_sales_catalog_client] = lambda: sales_catalog_client
    app.state.db_sessionmaker = _SingleSessionMaker(db_session)
    app.state.image_internal_confidence = 0.30
    app.state.image_external_confidence = 0.80
    return app


async def test_integracao_suporte_usa_rag_e_nunca_consulta_catalogo(db_session):
    rag_client = _FakeRAGClient(
        documents=[
            Document(
                content="Verifique o disjuntor e reinicie o gerador.",
                source="manual_gd15.pdf",
                score=0.9,
            )
        ]
    )
    sales_catalog_client = _FakeSalesCatalogClient()
    local_client = _DomainAwareLLMClient(
        resposta_final="Verifique o disjuntor e tente reiniciar o equipamento."
    )
    app = _build_app(
        local_client=local_client,
        rag_client=rag_client,
        sales_catalog_client=sales_catalog_client,
        calendar_client=_FakeCalendarClient(),
        db_session=db_session,
    )

    with TestClient(app) as client:
        resposta = client.post(
            "/api/chat/messages",
            json={"message": "Meu gerador está quebrado e aparece um erro estranho"},
        )

    dados_done = _find(_parse_sse(resposta.text), "done")
    assert dados_done["domain"] == "suporte"
    assert dados_done["rag_chunks"] == [{"source": "manual_gd15.pdf", "score": 0.9}]
    # Distingue Suporte de Vendas: nunca consulta o catálogo/cotação.
    assert sales_catalog_client.termos_buscados == []
    assert dados_done["card"] is None


async def test_integracao_atendimento_injeta_historico_de_compras_no_prompt(db_session):
    cliente = Cliente(email="ana.recorrente@teste.com", nome="Ana")
    db_session.add(cliente)
    await db_session.flush()
    db_session.add(
        ClienteCompra(
            cliente_id=cliente.id,
            quantidade=1,
            valor_total=Decimal("18500.00"),
            comprado_em=datetime.now(UTC) - timedelta(days=10),
        )
    )
    await db_session.commit()

    local_client = _DomainAwareLLMClient(resposta_final="Sua nota fiscal foi enviada por e-mail.")
    app = _build_app(
        local_client=local_client,
        rag_client=_FakeRAGClient(),
        sales_catalog_client=_FakeSalesCatalogClient(),
        calendar_client=_FakeCalendarClient(),
        db_session=db_session,
    )

    with TestClient(app) as client:
        resposta = client.post(
            "/api/chat/messages",
            json={
                "message": "Quero a nota fiscal da minha última compra",
                "user_email": "ana.recorrente@teste.com",
            },
        )

    dados_done = _find(_parse_sse(resposta.text), "done")
    assert dados_done["domain"] == "atendimento"
    # Distingue Atendimento dos demais: histórico de compras vai pro prompt.
    # `any(...)`, não `prompts[-1]`: o Monitor de Tom (R8) roda em paralelo
    # com a geração da resposta, chamando `generate()` também — a ordem de
    # conclusão entre as duas chamadas não é garantida.
    assert any("[Dados do Cliente e Histórico de Compras]:" in p for p in local_client.prompts)


async def test_integracao_vendas_consulta_catalogo_e_gera_card_de_cotacao(db_session):
    sales_catalog_client = _FakeSalesCatalogClient(
        candidatos=[CandidatoProduto(id=1, nome="Gerador Diesel GD-15", categoria="geradores")],
        dados=DadosCatalogoVendas(
            produto_id=1,
            produto_nome="Gerador Diesel GD-15",
            preco=Decimal("24900.00"),
            estoque_total=17,
            cotacao=(Decimal("24900.00"), Decimal("0"), Decimal("124500.00")),
            quantidade=5,
        ),
    )
    local_client = _DomainAwareLLMClient(resposta_final="Aqui está sua cotação para 5 unidades.")
    app = _build_app(
        local_client=local_client,
        rag_client=_FakeRAGClient(),
        sales_catalog_client=sales_catalog_client,
        calendar_client=_FakeCalendarClient(),
        db_session=db_session,
    )

    with TestClient(app) as client:
        resposta = client.post(
            "/api/chat/messages",
            json={"message": "Quero um orçamento para 5 unidades do Gerador Diesel GD-15"},
        )

    dados_done = _find(_parse_sse(resposta.text), "done")
    assert dados_done["domain"] == "vendas"
    # Distingue Vendas dos demais: consulta o catálogo e gera card de cotação.
    assert sales_catalog_client.detalhes_consultados == [(1, None, 5)]
    assert dados_done["card"] is not None
    assert dados_done["card"]["tipo"] == "cotacao"


async def test_integracao_agendamento_fluxo_completo_ate_confirmar(db_session):
    reset_all_booking_slots()
    calendar_client = _FakeCalendarClient(available=True)
    local_client = _DomainAwareLLMClient(
        resposta_final="(não deveria aparecer — agendamento responde com templates, não LLM)"
    )
    app = _build_app(
        local_client=local_client,
        rag_client=_FakeRAGClient(),
        sales_catalog_client=_FakeSalesCatalogClient(),
        calendar_client=calendar_client,
        db_session=db_session,
    )
    conversation_id = "conv-integracao-agendamento"

    with TestClient(app) as client:
        # Turno 1: pede a visita com todos os dados — o roteador extrai os
        # slots (fake LLM) e, como estão completos e dentro do expediente, a
        # máquina de estados pede confirmação (não cria o evento ainda).
        resposta1 = client.post(
            "/api/chat/messages",
            json={
                "message": (
                    "Quero marcar uma visita para quinta às 10h, meu nome é Maria, "
                    "email maria@teste.com, telefone 11999999999"
                ),
                "conversation_id": conversation_id,
            },
        )
        dados_done1 = _find(_parse_sse(resposta1.text), "done")
        assert dados_done1["domain"] == "agendamento"
        assert calendar_client.create_event_calls == []

        # Turno 2: confirma — a mensagem em si não tem nenhuma palavra-chave
        # de domínio, mas a conversa continua em agendamento porque já há
        # slots aguardando confirmação para este `conversation_id`.
        resposta2 = client.post(
            "/api/chat/messages",
            json={"message": "sim, pode confirmar", "conversation_id": conversation_id},
        )
        dados_done2 = _find(_parse_sse(resposta2.text), "done")

    assert dados_done2["domain"] == "agendamento"
    # Distingue Agendamento dos demais: máquina de estados cria o evento de
    # verdade no calendário só após a confirmação do segundo turno.
    assert len(calendar_client.create_event_calls) == 1
    reset_all_booking_slots()
