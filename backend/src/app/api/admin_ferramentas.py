"""Painel administrativo das ferramentas de inteligência de código do
projeto — Graphify, Repowise e GitNexus — reunidas numa tela só.

As três respondem à mesma pergunta por caminhos diferentes (grafo estático
por AST, wiki viva com busca semântica, e grafo de execução com raio de
impacto), e cada uma tinha a sua própria porta e o seu próprio comando para
abrir. Este módulo expõe o estado das três e serve o artefato do Graphify,
para a tela `/admin/ferramentas` não depender do desenvolvedor lembrar
`localhost:3002` x `localhost:4747` x abrir um HTML na mão.

# MVP: fora do escopo do MVP do TCC (ver docs/ROADMAP.md, "Extra fora do
# MVP — Painel de Ferramentas de Código") — é tela de apoio ao
# desenvolvimento, não parte do assistente. Pedida explicitamente pelo dono
# do projeto em 2026-10-13.
"""

import asyncio
import logging
import shutil
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.api.admin_auth import require_admin
from app.config import get_settings

logger = logging.getLogger("assistente.admin_ferramentas")

router = APIRouter(prefix="/api/admin/ferramentas", tags=["Admin Ferramentas"])

# MVP: timeout curto e fixo — a sondagem é contra `localhost`, então ou a
# ferramenta está no ar e responde em milissegundos, ou não está. Um valor
# maior só faria a tela demorar a dizer "offline".
_TIMEOUT_SONDAGEM_S = 1.5

# MVP: `graphify update .` é AST puro (sem API), leva segundos a poucos
# minutos; o teto evita processo pendurado e o lock impede duas execuções
# simultâneas gravando em `graphify-out/` ao mesmo tempo.
_TIMEOUT_ATUALIZACAO_S = 300
_SAIDA_MAX_CHARS = 4000
_lock_atualizacao = asyncio.Lock()


class FerramentaStatus(BaseModel):
    """Estado de uma das ferramentas de inteligência de código.

    `tipo` distingue as duas naturezas: `"artefato"` é um arquivo gerado no
    repositório (Graphify), que existe ou não; `"servidor"` é um processo
    local que precisa estar no ar (Repowise, GitNexus). `comando` é sempre
    o que o desenvolvedor roda para gerar/subir o que falta — a tela mostra
    isso quando `online` é `False`, em vez de só dizer que falhou.
    """

    id: str
    nome: str
    descricao: str
    tipo: str
    url: str | None
    online: bool
    detalhe: str | None
    comando: str


class AtualizacaoGraphifyResposta(BaseModel):
    sucesso: bool
    saida: str


class FerramentasResposta(BaseModel):
    ferramentas: list[FerramentaStatus]


async def sondar_servidor(url: str) -> tuple[bool, str | None]:
    """Sonda um servidor local das ferramentas. Devolve `(online, detalhe)`.

    Função de módulo (e não um método) para os testes substituírem a
    sondagem sem subir servidor nenhum. Qualquer resposta HTTP conta como
    online, inclusive 404: a ferramenta pode não servir nada na raiz, mas
    está no ar — o que a tela precisa saber é se vale a pena embutir o
    iframe.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SONDAGEM_S) as cliente:
            resposta = await cliente.get(url)
        return True, f"HTTP {resposta.status_code}"
    except httpx.HTTPError as exc:
        return False, f"Sem resposta em {url} ({type(exc).__name__})"


def _caminho_grafo_graphify() -> Path:
    settings = get_settings()
    return (Path(settings.graphify_out_dir) / "graph.html").resolve()


def _status_graphify() -> FerramentaStatus:
    caminho = _caminho_grafo_graphify()
    existe = caminho.is_file()
    if existe:
        tamanho_mb = caminho.stat().st_size / (1024 * 1024)
        detalhe = f"{caminho} ({tamanho_mb:.1f} MB)"
    else:
        detalhe = f"Arquivo não encontrado em {caminho}"
    return FerramentaStatus(
        id="graphify",
        nome="Graphify",
        descricao=(
            "Grafo estrutural por AST do repositório — nós, comunidades e "
            "dependências. Artefato estático versionado em graphify-out/."
        ),
        tipo="artefato",
        # O HTML é servido pelo próprio backend (endpoint abaixo) porque o
        # arquivo mora fora de `frontend/public/` e tem 3 MB — copiá-lo
        # para o build do Next a cada `graphify update` seria pior.
        url="/api/admin/ferramentas/graphify/grafo" if existe else None,
        online=existe,
        detalhe=detalhe,
        comando="graphify update .",
    )


@router.get("", response_model=FerramentasResposta, dependencies=[Depends(require_admin)])
async def listar_ferramentas() -> FerramentasResposta:
    """Estado das três ferramentas, para a tela decidir o que embutir."""
    settings = get_settings()

    repowise_online, repowise_detalhe = await sondar_servidor(settings.repowise_web_url)
    gitnexus_online, gitnexus_detalhe = await sondar_servidor(settings.gitnexus_web_url)

    return FerramentasResposta(
        ferramentas=[
            _status_graphify(),
            FerramentaStatus(
                id="repowise",
                nome="Repowise",
                descricao=(
                    "Wiki viva do código com busca semântica, cartões de "
                    "triagem e detecção de código morto."
                ),
                tipo="servidor",
                url=settings.repowise_web_url,
                online=repowise_online,
                detalhe=repowise_detalhe,
                comando="repowise serve",
            ),
            FerramentaStatus(
                id="gitnexus",
                nome="GitNexus",
                descricao=(
                    "Grafo de chamadas e fluxos de execução, com análise de "
                    "raio de impacto antes de editar um símbolo."
                ),
                tipo="servidor",
                url=settings.gitnexus_web_url,
                online=gitnexus_online,
                detalhe=gitnexus_detalhe,
                comando="node .gitnexus/run.cjs serve",
            ),
        ]
    )


@router.get(
    "/graphify/grafo",
    response_class=HTMLResponse,
    dependencies=[Depends(require_admin)],
)
async def obter_grafo_graphify() -> HTMLResponse:
    """Serve `graphify-out/graph.html` para o iframe da tela.

    `require_admin` aceita `?token=`, então o iframe autentica pela própria
    URL — mesmo caminho já usado por `GET /api/rag/documents/{id}/download`
    (ver docs/ARCHITECTURE.md §7). Sem isso não haveria como autenticar um
    iframe, que não manda cabeçalho `Authorization`.
    """
    caminho = _caminho_grafo_graphify()
    if not caminho.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Grafo do Graphify não encontrado. Rode `graphify update .` na "
                "raiz do repositório para gerá-lo."
            ),
        )
    return HTMLResponse(content=caminho.read_text(encoding="utf-8"))


@router.post(
    "/graphify/atualizar",
    response_model=AtualizacaoGraphifyResposta,
    dependencies=[Depends(require_admin)],
)
async def atualizar_graphify() -> AtualizacaoGraphifyResposta:
    """Roda `graphify update .` na raiz do repositório e devolve a saída.

    A raiz é o pai de `graphify_out_dir`. Falha do comando não é erro HTTP:
    devolve `200` com `sucesso: false` e a saída, que a tela mostra.
    """
    executavel = shutil.which("graphify")
    if executavel is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CLI `graphify` não encontrada no PATH do backend.",
        )
    if _lock_atualizacao.locked():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe uma atualização do Graphify em andamento.",
        )

    raiz = Path(get_settings().graphify_out_dir).resolve().parent
    async with _lock_atualizacao:
        processo = await asyncio.create_subprocess_exec(
            executavel,
            "update",
            ".",
            cwd=raiz,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            bruto, _ = await asyncio.wait_for(
                processo.communicate(), timeout=_TIMEOUT_ATUALIZACAO_S
            )
        except TimeoutError:
            processo.kill()
            await processo.wait()
            return AtualizacaoGraphifyResposta(
                sucesso=False,
                saida=f"Tempo esgotado após {_TIMEOUT_ATUALIZACAO_S}s.",
            )

    saida = bruto.decode("utf-8", errors="replace").strip()[-_SAIDA_MAX_CHARS:]
    logger.info("graphify update terminou com código %s", processo.returncode)
    return AtualizacaoGraphifyResposta(sucesso=processo.returncode == 0, saida=saida)
