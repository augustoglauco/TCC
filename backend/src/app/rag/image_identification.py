"""Identificação de produto por imagem (R6, Fase 3).

Fluxo (ver docs/ARCHITECTURE.md §4 — "Fluxo de identificação de produto"):

1. Catálogo interno (CLIP): busca a imagem em `catalogo_imagens`. Se o melhor
   score >= `internal_confidence`, aceita direto (sem chamar o externo).
2. Visão externa (fallback): consulta um modelo multimodal via OpenRouter
   pedindo JSON estruturado {produto, e_do_portfolio, confianca} sobre o
   portfólio da empresa.
3. Decisão: se for do portfólio E confiança >= `external_confidence`, busca no
   RAG de texto pelo nome (mais o contexto de mensagens recentes, quando
   houver) e devolve os detalhes. Caso contrário, "não identificado".

O serviço é uma função pura sobre os colaboradores (store CLIP, embedder,
cliente de visão, RAG de texto), testável isoladamente com mocks — sem GPU
nem chamada externa real.
"""

import json
import logging
import re
import unicodedata

from pydantic import BaseModel, ValidationError

from app.rag.clip_embedder import ClipEmbedder
from app.rag.image_search import ClipImageStore
from app.router.openrouter_client import VisionModelIndisponivelError
from app.router.rag_client import Document, RAGClient

logger = logging.getLogger(__name__)

# Portfólio da empresa informado ao modelo de visão (ver docs/ARCHITECTURE.md
# §4). Texto curto e fixo — o RAG de texto valida depois se o nome existe no
# catálogo indexado.
PORTFOLIO_DESCRICAO = (
    "produtos de segurança: câmeras, sensores, automação, equipamentos de "
    "rede, catracas eletrônicas, identificadores biométricos e gravadores de "
    "imagem"
)

# Domínio usado para a busca de detalhes no RAG de texto: produtos são do
# domínio de vendas (catálogo). # MVP: domínio fixo — o catálogo de produtos
# vive em 'vendas' (ver docs/ARCHITECTURE.md §4).
_RAG_DOMAIN = "vendas"

_VISION_PROMPT = (
    "Você identifica produtos em imagens para uma empresa cujo portfólio é: "
    f"{PORTFOLIO_DESCRICAO}.\n"
    "Analise a imagem e responda APENAS com um objeto JSON, sem texto "
    "adicional, no formato exato:\n"
    '{{"produto": "<nome do produto ou tipo>", "e_do_portfolio": true/false, '
    '"confianca": <número de 0 a 1>}}\n'
    "- 'e_do_portfolio' deve ser true somente se o produto claramente "
    "pertence ao portfólio acima.\n"
    "- 'confianca' é a sua confiança na identificação (0 a 1)."
)

_CODE_FENCE_RE = re.compile(r"^```(?:\w+)?\s*\n?(.*?)\n?```$", re.DOTALL)


class ImageIdentificationResult(BaseModel):
    """Resultado do fluxo de identificação de produto por imagem.

    status:
    - "encontrado_interno": achado no catálogo CLIP (score >= limiar interno).
    - "encontrado_externo": visão externa confirmou (portfólio + confiança) e
      o RAG de texto trouxe detalhes.
    - "nao_identificado": não é do portfólio, confiança baixa, visão externa
      indisponível, ou nome não encontrado no RAG.
    """

    status: str
    produto: str | None = None
    produto_id: int | None = None
    imagem_url: str | None = None
    fonte: str | None = None
    detalhes: str | None = None
    confianca_interna: float | None = None
    confianca_externa: float | None = None
    mensagem: str | None = None


class _VisionAnswer(BaseModel):
    produto: str
    e_do_portfolio: bool
    confianca: float


def _parse_vision_answer(raw_text: str) -> _VisionAnswer | None:
    stripped = raw_text.strip()
    match = _CODE_FENCE_RE.match(stripped)
    if match:
        stripped = match.group(1)
    try:
        return _VisionAnswer(**json.loads(stripped))
    except (json.JSONDecodeError, ValidationError, TypeError):
        return None


_NAO_IDENTIFICADO_MSG = "Não consegui identificar este produto no nosso portfólio."


async def identify_product_by_image(
    image_bytes: bytes,
    *,
    clip_store: ClipImageStore,
    clip_embedder: ClipEmbedder,
    vision_client,  # OpenRouterClient (duck-typed: describe_image)
    rag_client: RAGClient,
    internal_confidence: float,
    external_confidence: float,
    recent_messages: list[str] | None = None,
) -> ImageIdentificationResult:
    """Executa o fluxo de identificação de produto por imagem.

    `vision_client` é duck-typed (precisa de `describe_image(bytes, prompt)`)
    para facilitar mock nos testes. Erros de infraestrutura do RAG
    (`RAGConnectionError`) propagam; falha da visão externa
    (`VisionModelIndisponivelError`) é tratada como "não identificado".
    """
    recent_messages = recent_messages or []

    # 1) Catálogo interno (CLIP).
    internos = await clip_store.search_by_image(clip_embedder, image_bytes, domain=_RAG_DOMAIN)
    if internos and internos[0].score >= internal_confidence:
        melhor = internos[0]
        detalhes = await _buscar_detalhes(
            rag_client, melhor.filename, recent_messages, produto_id=melhor.produto_id
        )
        return ImageIdentificationResult(
            status="encontrado_interno",
            produto=melhor.filename,
            produto_id=melhor.produto_id,
            imagem_url=melhor.imagem_url,
            fonte="catalogo_imagens",
            detalhes=detalhes,
            confianca_interna=melhor.score,
        )

    # 2) Visão externa (fallback).
    try:
        raw = await vision_client.describe_image(image_bytes, _VISION_PROMPT)
    except VisionModelIndisponivelError:
        logger.info("identify_image vision_indisponivel -> nao_identificado")
        return ImageIdentificationResult(status="nao_identificado", mensagem=_NAO_IDENTIFICADO_MSG)

    answer = _parse_vision_answer(raw)
    # 3) Decisão sobre a resposta do externo.
    if answer is None or not answer.e_do_portfolio or answer.confianca < external_confidence:
        return ImageIdentificationResult(status="nao_identificado", mensagem=_NAO_IDENTIFICADO_MSG)

    detalhes = await _buscar_detalhes(rag_client, answer.produto, recent_messages)
    return ImageIdentificationResult(
        status="encontrado_externo",
        produto=answer.produto,
        fonte="visao_externa+rag_texto",
        detalhes=detalhes,
        confianca_externa=answer.confianca,
    )


def _remover_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def _documento_relevante_para_produto(
    doc: Document, nome_produto: str, produto_id: int | None = None
) -> bool:
    content_lower = doc.content.lower()
    nome_lower = nome_produto.lower().strip()

    # 1) Bate pelo produto_id no conteúdo (ex.: "id: 2")
    if produto_id is not None and (
        f"id: {produto_id}" in content_lower or f"id:{produto_id}" in content_lower
    ):
        return True

    # 2) Bate pelo nome completo do produto no texto
    if nome_lower and nome_lower in content_lower:
        return True

    # 3) Bate por normalização sem acentos / tokens principais
    content_clean = _remover_acentos(content_lower)
    nome_clean = _remover_acentos(nome_lower)

    if nome_clean in content_clean:
        return True

    stop_words = {"de", "para", "com", "sem", "em", "do", "da", "dos", "das", "um", "uma", "produto"}
    tokens_nome = [
        t for t in re.split(r"[\s\-_,\.]+", nome_clean) if len(t) >= 3 and t not in stop_words
    ]
    if tokens_nome and any(t in content_clean for t in tokens_nome):
        return True

    return False


async def _buscar_detalhes(
    rag_client: RAGClient,
    nome_produto: str,
    recent_messages: list[str],
    produto_id: int | None = None,
) -> str | None:
    """Busca detalhes do produto no RAG de texto pelo nome (+ contexto recente).

    Concatena o nome identificado ao contexto de mensagens recentes do
    usuário (ex.: o que ele pediu antes de enviar a imagem), como decidido
    em docs/ARCHITECTURE.md §4. Filtra apenas os documentos que realmente
    correspondem ao produto identificado, evitando retornar vizinhos vetoriais
    não relacionados. Devolve os `content` concatenados ou None se a busca não
    trouxe nenhum documento relevante.
    """
    query = "\n".join([*recent_messages, nome_produto]) if recent_messages else nome_produto
    documentos: list[Document] = await rag_client.search(query, _RAG_DOMAIN)
    if not documentos:
        return None

    relevantes = [
        d for d in documentos if _documento_relevante_para_produto(d, nome_produto, produto_id)
    ]
    if not relevantes:
        return None

    return "\n\n".join(d.content for d in relevantes)
