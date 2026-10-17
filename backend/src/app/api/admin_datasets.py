"""Painel de preparação da avaliação experimental (Fase 10) — fila de
revisão dos conjuntos de teste e disparo das tarefas longas.

A Estratégia A (`docs/EVALUATION.md` Seção 0) pede 780 itens com gabarito
revisado, distribuídos em cinco conjuntos. Revisar isso editando JSON na mão
é inviável, e as tarefas que alimentam os conjuntos (ingerir 97 PDFs, gerar
rascunhos, rodar o benchmark) levam de minutos a horas — longe demais do
padrão de `admin_ferramentas`, que bloqueia a requisição até o comando
terminar. Daí este módulo: estado dos conjuntos, revisão item a item, e um
executor de tarefas em background com log incremental.

# MVP: fora do escopo do MVP do TCC (ver docs/ROADMAP.md, "Extra fora do
# MVP — Painel de Preparação da Avaliação") — é tela de apoio à condução do
# experimento, não parte do assistente. Pedida pelo dono em 2026-10-16.
"""

import asyncio
import json
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.admin_auth import require_admin
from app.config import get_settings

logger = logging.getLogger("assistente.admin_datasets")

router = APIRouter(prefix="/api/admin/datasets", tags=["Admin Datasets"])

StatusRevisao = Literal["pendente", "aprovado", "corrigido", "descartado"]
_STATUS_VALIDOS: set[str] = {"pendente", "aprovado", "corrigido", "descartado"}


@dataclass(frozen=True)
class _Conjunto:
    """Um conjunto de teste da Fase 10.

    `revisao_automatica` marca os conjuntos cujo gabarito é exato por
    construção — imagem (o gabarito é o nome da pasta do fornecedor) e banco
    (as perguntas são geradas a partir das próprias linhas de `produtos`).
    Eles aparecem na tela como prontos, sem fila: é a decisão que derruba a
    revisão humana de 12h para ~4,5h (`docs/EVALUATION.md` Seção 0).
    """

    id: str
    nome: str
    caminho_relativo: str
    meta: int
    revisao_automatica: bool = False


CONJUNTOS: tuple[_Conjunto, ...] = (
    _Conjunto("roteador", "Roteador", "router_intents/dataset.json", 300),
    _Conjunto("rag_docs", "RAG documentos", "rag_quality/dataset.json", 180),
    _Conjunto("injecao", "Injeção de prompt", "prompt_injection/dataset.json", 100),
    _Conjunto(
        "rag_imagem",
        "RAG imagem",
        "model_benchmark/imagens/dataset.json",
        120,
        revisao_automatica=True,
    ),
    _Conjunto("rag_banco", "RAG banco", "rag_banco/dataset.json", 80, revisao_automatica=True),
)
_POR_ID = {c.id: c for c in CONJUNTOS}


def _caminho(conjunto: _Conjunto) -> Path:
    return Path(get_settings().eval_dir).resolve() / conjunto.caminho_relativo


def _ler_casos(conjunto: _Conjunto) -> tuple[dict, list[dict]]:
    """Devolve o JSON inteiro e a lista de casos. Conjunto ainda não gerado
    não é erro — vem vazio, e a tela mostra "0 de N" em vez de falhar."""
    caminho = _caminho(conjunto)
    if not caminho.exists():
        return {}, []
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return dados, dados.get("casos", [])


def _status_do_caso(caso: dict, conjunto: _Conjunto) -> str:
    if conjunto.revisao_automatica:
        return "aprovado"
    return (caso.get("revisao") or {}).get("status", "pendente")


class ConjuntoStatus(BaseModel):
    id: str
    nome: str
    meta: int
    total: int
    pendentes: int
    aprovados: int
    corrigidos: int
    descartados: int
    revisao_automatica: bool
    existe: bool


class DatasetsResposta(BaseModel):
    conjuntos: list[ConjuntoStatus]


def _montar_status(conjunto: _Conjunto) -> ConjuntoStatus:
    dados, casos = _ler_casos(conjunto)
    contagem = {s: 0 for s in _STATUS_VALIDOS}
    for caso in casos:
        contagem[_status_do_caso(caso, conjunto)] += 1
    return ConjuntoStatus(
        id=conjunto.id,
        nome=conjunto.nome,
        meta=conjunto.meta,
        total=len(casos),
        pendentes=contagem["pendente"],
        aprovados=contagem["aprovado"],
        corrigidos=contagem["corrigido"],
        descartados=contagem["descartado"],
        revisao_automatica=conjunto.revisao_automatica,
        existe=bool(dados),
    )


@router.get("", response_model=DatasetsResposta, dependencies=[Depends(require_admin)])
async def listar_conjuntos() -> DatasetsResposta:
    """Progresso de revisão dos cinco conjuntos da Estratégia A."""
    return DatasetsResposta(conjuntos=[_montar_status(c) for c in CONJUNTOS])


class ItemRevisao(BaseModel):
    indice: int
    id: str
    status: str
    campos: dict


class ItensResposta(BaseModel):
    conjunto: str
    total: int
    itens: list[ItemRevisao]


@router.get(
    "/{conjunto_id}/itens",
    response_model=ItensResposta,
    dependencies=[Depends(require_admin)],
)
async def listar_itens(
    conjunto_id: str, apenas_pendentes: bool = True, offset: int = 0, limite: int = 20
) -> ItensResposta:
    """Fatia da fila de revisão. `campos` vai cru para a tela montar o
    layout por conjunto — a pergunta e o trecho de origem do RAG não têm o
    mesmo formato da mensagem do roteador."""
    conjunto = _POR_ID.get(conjunto_id)
    if conjunto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Conjunto desconhecido: {conjunto_id}.")

    _, casos = _ler_casos(conjunto)
    selecionados = [
        ItemRevisao(
            indice=i,
            id=str(caso.get("id", i)),
            status=_status_do_caso(caso, conjunto),
            campos={k: v for k, v in caso.items() if k != "revisao"},
        )
        for i, caso in enumerate(casos)
        if not apenas_pendentes or _status_do_caso(caso, conjunto) == "pendente"
    ]
    return ItensResposta(
        conjunto=conjunto_id,
        total=len(selecionados),
        itens=selecionados[offset : offset + limite],
    )


class RevisaoPedido(BaseModel):
    status: StatusRevisao
    campos: dict | None = None


@router.patch(
    "/{conjunto_id}/itens/{indice}",
    response_model=ItemRevisao,
    dependencies=[Depends(require_admin)],
)
async def revisar_item(conjunto_id: str, indice: int, pedido: RevisaoPedido) -> ItemRevisao:
    """Grava a decisão de revisão no próprio `dataset.json`.

    O item fica no arquivo mesmo quando descartado, com
    `revisao.status="descartado"` — os scripts de avaliação filtram por
    status. Apagar perderia o registro de que aquele caso foi considerado e
    rejeitado, que é informação do experimento.
    """
    conjunto = _POR_ID.get(conjunto_id)
    if conjunto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Conjunto desconhecido: {conjunto_id}.")
    if conjunto.revisao_automatica:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{conjunto.nome} tem gabarito exato por construção e não passa por revisão.",
        )

    dados, casos = _ler_casos(conjunto)
    if not 0 <= indice < len(casos):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Item {indice} fora do conjunto.")

    caso = casos[indice]
    if pedido.campos:
        caso.update(pedido.campos)
    caso["revisao"] = {
        "status": pedido.status,
        "em": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    _caminho(conjunto).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("revisao conjunto=%s indice=%s status=%s", conjunto_id, indice, pedido.status)
    return ItemRevisao(
        indice=indice,
        id=str(caso.get("id", indice)),
        status=pedido.status,
        campos={k: v for k, v in caso.items() if k != "revisao"},
    )


# --------------------------------------------------------------------------
# Tarefas longas
# --------------------------------------------------------------------------

# A ingestão dos 97 PDFs leva minutos e a rodada do benchmark leva horas —
# bloquear a requisição até terminar (padrão de `admin_ferramentas`) não
# serve. O processo roda solto e a tela lê o log por polling incremental.
_MAX_LINHAS_LOG = 2000


@dataclass
class _Tarefa:
    id: str
    tipo: str
    comando: list[str]
    estado: str = "rodando"
    iniciada_em: float = field(default_factory=time.time)
    terminada_em: float | None = None
    codigo: int | None = None
    linhas: deque[str] = field(default_factory=lambda: deque(maxlen=_MAX_LINHAS_LOG))
    processo: asyncio.subprocess.Process | None = None


_tarefas: dict[str, _Tarefa] = {}

TAREFAS_DISPONIVEIS: dict[str, tuple[str, list[str]]] = {
    "gerar_rascunho_rag_docs": (
        "Gerar rascunho das 180 perguntas de RAG documentos",
        [".venv/bin/python", "eval/rag_quality/gerar_dataset.py"],
    ),
    "ingerir_corpus": (
        "Ingerir os 97 PDFs no RAG",
        [".venv/bin/python", "scripts/ingerir_corpus_avaliacao.py"],
    ),
    "triagem": (
        "Triagem: roteador + imagem nos 10 candidatos",
        [
            ".venv/bin/python",
            "eval/model_benchmark/run_benchmark.py",
            "--etapas",
            "roteador,imagem",
        ],
    ),
    "rodada_completa": (
        "Rodada completa do benchmark",
        [".venv/bin/python", "eval/model_benchmark/run_benchmark.py"],
    ),
}


class TarefaResumo(BaseModel):
    id: str
    tipo: str
    rotulo: str
    estado: str
    iniciada_em: float
    terminada_em: float | None
    codigo: int | None
    total_linhas: int


class TarefaDetalhe(TarefaResumo):
    linhas: list[str]
    proximo_offset: int


def _resumo(tarefa: _Tarefa) -> TarefaResumo:
    return TarefaResumo(
        id=tarefa.id,
        tipo=tarefa.tipo,
        rotulo=TAREFAS_DISPONIVEIS.get(tarefa.tipo, (tarefa.tipo, []))[0],
        estado=tarefa.estado,
        iniciada_em=tarefa.iniciada_em,
        terminada_em=tarefa.terminada_em,
        codigo=tarefa.codigo,
        total_linhas=len(tarefa.linhas),
    )


async def _acompanhar(tarefa: _Tarefa, raiz: Path) -> None:
    try:
        processo = await asyncio.create_subprocess_exec(
            *tarefa.comando,
            cwd=raiz,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        tarefa.processo = processo
        assert processo.stdout is not None
        async for bruto in processo.stdout:
            tarefa.linhas.append(bruto.decode("utf-8", errors="replace").rstrip())
        await processo.wait()
        tarefa.codigo = processo.returncode
        tarefa.estado = "concluida" if processo.returncode == 0 else "falhou"
    except Exception as exc:  # noqa: BLE001
        tarefa.linhas.append(f"[erro do executor] {type(exc).__name__}: {exc}")
        tarefa.estado = "falhou"
    finally:
        tarefa.terminada_em = time.time()
        logger.info("tarefa %s (%s) terminou: %s", tarefa.id, tarefa.tipo, tarefa.estado)


class IniciarTarefaPedido(BaseModel):
    tipo: str


@router.post("/tarefas", response_model=TarefaResumo, dependencies=[Depends(require_admin)])
async def iniciar_tarefa(pedido: IniciarTarefaPedido) -> TarefaResumo:
    """Dispara uma tarefa longa e devolve logo o identificador.

    Uma por tipo de cada vez: duas ingestões simultâneas escreveriam na
    mesma collection, e dois benchmarks disputariam a mesma GPU.
    """
    if pedido.tipo not in TAREFAS_DISPONIVEIS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Tarefa desconhecida: {pedido.tipo}.")
    if any(t.tipo == pedido.tipo and t.estado == "rodando" for t in _tarefas.values()):
        raise HTTPException(status.HTTP_409_CONFLICT, f"{pedido.tipo} já está rodando.")

    rotulo, comando = TAREFAS_DISPONIVEIS[pedido.tipo]
    raiz = Path(get_settings().eval_dir).resolve().parent
    tarefa = _Tarefa(id=uuid.uuid4().hex[:12], tipo=pedido.tipo, comando=comando)
    _tarefas[tarefa.id] = tarefa
    logger.info("tarefa %s iniciada: %s", tarefa.id, rotulo)
    asyncio.create_task(_acompanhar(tarefa, raiz))
    return _resumo(tarefa)


@router.get("/tarefas", response_model=list[TarefaResumo], dependencies=[Depends(require_admin)])
async def listar_tarefas() -> list[TarefaResumo]:
    ordenadas = sorted(_tarefas.values(), key=lambda t: t.iniciada_em, reverse=True)
    return [_resumo(t) for t in ordenadas]


@router.get(
    "/tarefas/{tarefa_id}", response_model=TarefaDetalhe, dependencies=[Depends(require_admin)]
)
async def detalhar_tarefa(tarefa_id: str, desde: int = 0) -> TarefaDetalhe:
    """Log a partir de `desde` — a tela só pede o que ainda não tem, em vez
    de rebaixar o buffer inteiro a cada polling."""
    tarefa = _tarefas.get(tarefa_id)
    if tarefa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Tarefa desconhecida: {tarefa_id}.")
    linhas = list(tarefa.linhas)[desde:]
    return TarefaDetalhe(
        **_resumo(tarefa).model_dump(),
        linhas=linhas,
        proximo_offset=desde + len(linhas),
    )


@router.post(
    "/tarefas/{tarefa_id}/cancelar",
    response_model=TarefaResumo,
    dependencies=[Depends(require_admin)],
)
async def cancelar_tarefa(tarefa_id: str) -> TarefaResumo:
    """Mata o processo. O benchmark é retomável (grava por etapa e por
    modelo), então cancelar não perde o que já rodou."""
    tarefa = _tarefas.get(tarefa_id)
    if tarefa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Tarefa desconhecida: {tarefa_id}.")
    if tarefa.estado != "rodando" or tarefa.processo is None:
        return _resumo(tarefa)
    tarefa.processo.kill()
    tarefa.estado = "cancelada"
    tarefa.linhas.append("[cancelada pelo painel]")
    return _resumo(tarefa)
