"""Extração de produtos de catálogos PDF/imagens para a tela /admin/produtos
(além do MVP, decisão de 2026-09-25 em docs/ARCHITECTURE.md §5).

# MVP: processa tudo dentro da própria requisição SSE, sem fila nem
# retomada; o texto de cada página vai ao modelo local e, sem texto ou com
# baixa confiança, a imagem vai ao modelo de visão externo (pago); o
# resultado sempre passa pela conferência humana antes de gravar.
# MVP: arquivos de texto (.txt/.md/.csv) são divididos em blocos de tamanho
# fixo e vão só ao modelo local — não há imagem para o fallback de visão.
"""

import io
import json
import logging
import re
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pdfplumber
from PIL import Image

from app.background_tasks import spawn_background_task
from app.models.catalog_extractor import CatalogPageResult, ExtractedProduct
from app.ocr.image_processor import ImageFormatError, OcrIndisponivelError, extract_text_from_bytes
from app.rag.pdf_extract import _extrair_texto_pagina
from app.services.ai_usage import registrar_uso_ia

logger = logging.getLogger(__name__)

EXTENSOES_TEXTO = (".txt", ".md", ".csv")
TAMANHO_BLOCO_TEXTO = 6000

_CODE_FENCE_RE = re.compile(r"^```(?:\w+)?\s*\n?(.*?)\n?```$", re.DOTALL)


@dataclass(frozen=True)
class _ExtractionConfig:
    """Parâmetros de sessão invariantes durante toda a extração de um catálogo."""

    provider: str
    fallback_external: bool
    temp_dir: Path
    local_client: Any
    vision_client: Any
    session_factory: Any


LOCAL_EXTRACTION_PROMPT = """Você é um assistente especialista em extração de produtos de catálogos e tabelas de fornecedores.
Analise o texto a seguir extraído de uma página de catálogo comercial e extraia todos os produtos identificados.
Responda APENAS com um array JSON no seguinte formato:
[
  {
    "nome": "Nome do produto com modelo/marca",
    "descricao": "Descrição resumida das funcionalidades e aplicação",
    "categoria": "Categoria sugerida (ex: CFTV, Alarmes, Redes, Controle de Acesso, Automação, Geral)",
    "preco_base_fornecedor": 123.45,
    "preco": 199.90,
    "especificacoes_tecnicas": "Especificações chave como resolução, canais, portas, voltagem"
  }
]
Regras:
1. 'preco_base_fornecedor' e 'preco' devem ser números float (ex: 150.0) ou null se não constar. Remova R$, vírgulas e pontos de milhar ao converter.
2. Se nenhum produto for encontrado no texto, responda com [].
3. Não inclua texto explicativo fora do array JSON.

Texto da página:
{texto}
"""  # noqa: E501 — prompt: quebrar as linhas mudaria o texto enviado ao LLM

VISION_EXTRACTION_PROMPT = """Você é um assistente especialista em extrair dados de catálogos e folhetos comerciais.
Analise visualmente a imagem desta página de catálogo e extraia todos os produtos que constam nela.
Responda APENAS com um array JSON no seguinte formato:
[
  {
    "nome": "Nome do produto com modelo/marca",
    "descricao": "Descrição resumida",
    "categoria": "Categoria (CFTV, Alarmes, Redes, Controle de Acesso, Automação, Geral)",
    "preco_base_fornecedor": 123.45,
    "preco": 199.90,
    "especificacoes_tecnicas": "Especificações técnicas resumidas"
  }
]
Regras:
1. 'preco_base_fornecedor' e 'preco' devem ser float (ex: 150.0) ou null se ausentes.
2. Se nenhum produto for encontrado, responda com [].
3. Não inclua texto fora do array JSON.
"""  # noqa: E501 — prompt: quebrar as linhas mudaria o texto enviado ao LLM


def _extrair_json_bruto(text: str) -> str:
    """Isola o fragmento JSON de `text`, removendo cercas de código e texto extra."""
    stripped = text.strip()
    match = _CODE_FENCE_RE.match(stripped)
    if match:
        return match.group(1).strip()
    sub_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", stripped, re.DOTALL)
    if sub_match:
        return sub_match.group(1).strip()
    start = stripped.find("[")
    end = stripped.rfind("]")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]
    return stripped


def _parse_products_json(raw_text: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(_extrair_json_bruto(raw_text))
        if isinstance(data, dict) and data.get("nome"):
            return [data]
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict) and item.get("nome")]
        return []
    except json.JSONDecodeError as exc:
        logger.warning(f"Falha ao decodificar JSON de produtos extraídos: {exc}")
        return []


def _parse_page_range(range_str: str | None, max_pages: int) -> set[int] | None:
    """Interpreta string de intervalo de páginas (1-indexadas).
    Formatos aceitos:
      - '1-5' (páginas 1 a 5)
      - '2, 5, 8' (páginas 2, 5 e 8)
      - '3-' (da página 3 até o final do documento)
      - '-4' (da página 1 até a 4)
      - '1-3, 5, 8-10' (combinações de intervalos e páginas avulsas)
    Retorna None se range_str for vazio ou apenas espaços (significando todas as páginas).
    Retorna set[int] com as páginas válidas no intervalo [1, max_pages].
    """
    if not range_str or not range_str.strip():
        return None

    pages: set[int] = set()
    chunks = [c.strip() for c in range_str.split(",") if c.strip()]

    for chunk in chunks:
        pages |= _expand_chunk(chunk, max_pages)
    return pages


def _expand_chunk(chunk: str, max_pages: int) -> set[int]:
    """Expande um único token ('3-5', '3-', '-4', '7') em páginas válidas."""
    if "-" in chunk:
        start_str, end_str = chunk.split("-", 1)
        start = int(start_str) if start_str.isdigit() else 1
        end = int(end_str) if end_str.isdigit() else max_pages
        if start > end:
            start, end = end, start
        return {p for p in range(start, end + 1) if 1 <= p <= max_pages}
    if chunk.isdigit():
        p = int(chunk)
        return {p} if 1 <= p <= max_pages else set()
    return set()


def _blocos_de_texto(content: bytes, max_chars: int = TAMANHO_BLOCO_TEXTO) -> list[str]:
    """Decodifica o arquivo e o divide em blocos de até `max_chars`, quebrando em linhas."""
    try:
        texto = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = content.decode("latin-1")

    blocos: list[str] = []
    atual: list[str] = []
    tamanho = 0
    for linha in texto.splitlines():
        # Linha maior que o bloco (texto sem quebras): fatia no limite.
        while len(linha) > max_chars:
            if atual:
                blocos.append("\n".join(atual))
                atual, tamanho = [], 0
            blocos.append(linha[:max_chars])
            linha = linha[max_chars:]
        if tamanho + len(linha) + 1 > max_chars and atual:
            blocos.append("\n".join(atual))
            atual, tamanho = [], 0
        atual.append(linha)
        tamanho += len(linha) + 1
    if atual:
        blocos.append("\n".join(atual))
    return [b for b in blocos if b.strip()]


async def extract_page_products_local(
    texto: str, local_client: Any, model_name: str | None = None
) -> list[dict[str, Any]]:
    prompt = LOCAL_EXTRACTION_PROMPT.replace("{texto}", texto)
    res = await local_client.generate(prompt)
    spawn_background_task(
        registrar_uso_ia(
            origem="admin",
            ambiente="interno",
            modelo=getattr(res, "model_name", None) or "desconhecido",
            operacao="extracao_catalogo_texto_local",
            tokens_entrada=getattr(res, "prompt_tokens", None),
            tokens_saida=getattr(res, "completion_tokens", None),
            custo_usd=getattr(res, "estimated_cost_usd", None),
            referencia_id=None,
            session=None,
            session_factory=None,
            commit=False,
        )
    )
    raw_response = getattr(res, "response", getattr(res, "text", str(res)))
    return _parse_products_json(raw_response)


async def extract_page_products_vision(
    image_bytes: bytes,
    vision_client: Any,
    prompt: str | None = None,
    source_identifier: str | None = None,
    session: Any = None,
    session_factory: Any = None,
    *,
    ambiente: str,
) -> list[dict[str, Any]]:
    """Extrai produtos de uma imagem de página de catálogo via modelo de visão.

    Nota sobre `session`/`session_factory`: esta função sempre chama
    `registrar_uso_ia(..., commit=False)` — quando o chamador passa
    `session_factory`, o registro abre sua própria transação e comita
    sozinho; quando o chamador passa `session` diretamente (sem
    `session_factory`), o evento só é dado como `flush`, não commit, e
    depende do caminho de chamada comitar essa sessão depois — se a
    transação nunca for comitada, o evento é perdido silenciosamente. Hoje
    nenhum chamador em produção passa `session` diretamente (só
    `session_factory`, vindo de `backend/src/app/api/admin_products.py`),
    então isso não é um bug observável — é só uma armadilha a evitar se um
    novo chamador vier a passar `session` sem garantir o commit.
    """
    used_prompt = prompt or VISION_EXTRACTION_PROMPT
    raw_response = await vision_client.describe_image(image_bytes, used_prompt)

    # Telemetria da extração de catálogo por visão — registrada no ledger
    # unificado (app.services.ai_usage), não mais em IngestionCostEvent
    # (decisão do usuário, 2026-10-08: migração sem dual-write; a
    # estimativa de tokens por tamanho de texto que existia aqui, nesta
    # função, foi removida de propósito — fabricava um número quando a API
    # não reportava uso real, contrariando a semântica None=não-capturado
    # do ledger novo). Isso remove só a estimativa LOCAL desta função: a
    # API de visão externa (OpenRouterClient.describe_image, em
    # app/router/openrouter_client.py) ainda pode fabricar
    # prompt_tokens/completion_tokens por tamanho de texto quando a
    # resposta não reporta uso real — gap conhecido, não corrigido aqui
    # (é compartilhado com image_identification.py/comprovante_evaluator.py
    # do item B, fora do escopo deste item), candidato a revisão no item E
    # ou em follow-up dedicado.
    p_tok = getattr(raw_response, "prompt_tokens", None)
    c_tok = getattr(raw_response, "completion_tokens", None)
    c_prompt = getattr(raw_response, "cost_prompt_usd", None)
    c_comp = getattr(raw_response, "cost_completion_usd", None)
    c_tot = getattr(raw_response, "estimated_cost_usd", None)
    if c_tot is None and c_prompt is not None and c_comp is not None:
        c_tot = c_prompt + c_comp
    model = getattr(raw_response, "model_name", None) or getattr(
        vision_client, "vision_model", None
    )

    spawn_background_task(
        registrar_uso_ia(
            origem="admin",
            ambiente=ambiente,
            modelo=model or "desconhecido",
            operacao=(
                "extracao_catalogo_visao_interna"
                if ambiente == "interno"
                else "extracao_catalogo_visao_externa"
            ),
            tokens_entrada=p_tok,
            tokens_saida=c_tok,
            custo_usd=c_tot,
            referencia_id=source_identifier,
            session=session,
            session_factory=session_factory,
            commit=False,
        )
    )

    return _parse_products_json(raw_response)


def _figura_pequena_ou_alongada(w: float, h: float) -> bool:
    """Ícone/bullet (pequeno demais) ou divisor/filete (proporção > 5.5:1)."""
    if w < 32 or h < 32 or (w * h) < 1600:
        return True
    return (w / max(h, 1) > 5.5) or (h / max(w, 1) > 5.5)


def _figura_de_fundo(w: float, h: float, page_w: float, page_h: float) -> bool:
    """Imagem que cobre quase a página inteira (plano de fundo)."""
    return w >= page_w * 0.92 and h >= page_h * 0.92


def _logo_na_borda(w: float, h: float, margem_sup: float, margem_inf: float) -> bool:
    """Figura pequena encostada no topo/rodapé da página (logo, selo, numeração)."""
    na_borda = margem_sup < 38 or margem_inf < 38
    return na_borda and w < 160 and h < 65


def _figura_valida(
    im: dict[str, Any], page_w: float, page_h: float, candidates: list[dict[str, float]]
) -> bool:
    """Retorna True se a figura deve ser incluída (não é ruído, divisor, fundo ou duplicata)."""
    w = float(im.get("width", 0) or 0)
    h = float(im.get("height", 0) or 0)
    x0 = float(im.get("x0", 0) or 0)
    top = float(im.get("top", 0) or 0)
    bottom = float(im.get("bottom", top + h) or (top + h))

    descartada = (
        _figura_pequena_ou_alongada(w, h)
        or _figura_de_fundo(w, h, page_w, page_h)
        or _logo_na_borda(w, h, top, page_h - bottom)
        or any(_is_duplicate_figure(c, x0, top, w, h) for c in candidates)
    )
    return not descartada


def _is_duplicate_figure(cand: dict[str, float], x0: float, top: float, w: float, h: float) -> bool:
    return (
        abs(cand["x0"] - x0) < 6
        and abs(cand["top"] - top) < 6
        and abs(cand["w"] - w) < 6
        and abs(cand["h"] - h) < 6
    )


def _normalizar_modo_imagem(crop: Image.Image) -> Image.Image:
    """Converte crop para RGB com fundo branco, se necessário."""
    if crop.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", crop.size, (255, 255, 255))
        if crop.mode == "P":
            crop = crop.convert("RGBA")
        mask = crop.split()[-1] if len(crop.split()) > 3 else None
        bg.paste(crop, mask=mask)
        return bg
    if crop.mode != "RGB":
        return crop.convert("RGB")
    return crop


def _coord(im: dict[str, Any], key: str, fallback: float) -> float:
    """Lê coordenada de um dict de imagem pdfplumber, tratando None/0 como `fallback`."""
    return float(im.get(key, fallback) or fallback)


def _filtrar_candidatos(
    raw_images: list[Any], page_w: float, page_h: float
) -> list[dict[str, float]]:
    """Filtra e ordena as imagens brutas da página em candidatos válidos."""
    candidates: list[dict[str, float]] = []
    for im in raw_images:
        w = _coord(im, "width", 0.0)
        h = _coord(im, "height", 0.0)
        x0 = _coord(im, "x0", 0.0)
        top = _coord(im, "top", 0.0)
        x1 = _coord(im, "x1", x0 + w)
        bottom = _coord(im, "bottom", top + h)
        if not _figura_valida(im, page_w, page_h, candidates):
            continue
        candidates.append({"x0": x0, "top": top, "x1": x1, "bottom": bottom, "w": w, "h": h})
    # Ordena espacialmente por linha visual (top agrupado a cada ~35pt) e
    # depois da esquerda para a direita (x0)
    candidates.sort(key=lambda c: (round(c["top"] / 35.0), c["x0"]))
    return candidates


def _extrair_figuras_pagina(page: Any, pil_img: Image.Image, temp_dir: Path) -> list[str]:
    """Detecta, filtra e recorta figuras individuais da página do catálogo."""
    page_w = float(getattr(page, "width", 0) or 1)
    page_h = float(getattr(page, "height", 0) or 1)
    scale_x = pil_img.width / page_w
    scale_y = pil_img.height / page_h

    candidates = _filtrar_candidatos(getattr(page, "images", []) or [], page_w, page_h)

    figuras_urls: list[str] = []
    for c in candidates:
        pad = 2.5
        px_x0 = max(0, int((c["x0"] - pad) * scale_x))
        px_y0 = max(0, int((c["top"] - pad) * scale_y))
        px_x1 = min(pil_img.width, int((c["x1"] + pad) * scale_x))
        px_y1 = min(pil_img.height, int((c["bottom"] + pad) * scale_y))

        if (px_x1 - px_x0) < 24 or (px_y1 - px_y0) < 24:
            continue

        crop = _normalizar_modo_imagem(pil_img.crop((px_x0, px_y0, px_x1, px_y1)))
        crop_name = f"crop_{uuid.uuid4().hex[:12]}.jpg"
        crop_path = temp_dir / crop_name
        crop.save(crop_path, format="JPEG", quality=90)
        figuras_urls.append(f"/api/uploads/produtos/temp/{crop_name}")

    return figuras_urls


def _montar_produto(
    item: dict[str, Any],
    *,
    pagina_origem: int,
    provider_usado: str,
    confianca: float,
    imagem_temp_url: str | None = None,
    fotos_pagina: list[str] | None = None,
) -> ExtractedProduct:
    return ExtractedProduct(
        nome=str(item.get("nome", "")),
        descricao=str(item.get("descricao", "") or ""),
        categoria=str(item.get("categoria", "") or "Geral"),
        preco_base_fornecedor=float(item["preco_base_fornecedor"])
        if item.get("preco_base_fornecedor") is not None
        else None,
        preco=float(item["preco"]) if item.get("preco") is not None else None,
        especificacoes_tecnicas=str(item.get("especificacoes_tecnicas", "") or ""),
        imagem_temp_url=imagem_temp_url,
        fotos_pagina=fotos_pagina,
        pagina_origem=pagina_origem,
        confianca=confianca,
        provider_usado=provider_usado,
    )


def _eventos_sse(progresso: dict[str, Any], page_result: CatalogPageResult) -> tuple[str, str]:
    """Serializa o par de eventos SSE (progresso, pagina_concluida) de uma página."""
    return (
        f"event: progresso\ndata: {json.dumps(progresso)}\n\n",
        f"event: pagina_concluida\ndata: {page_result.model_dump_json()}\n\n",
    )


async def _extrair_local_seguro(
    texto: str, local_client: Any, descricao: str
) -> list[dict[str, Any]]:
    """Extração local best-effort: falha do modelo vira lista vazia (log em `descricao`)."""
    try:
        return await extract_page_products_local(texto, local_client)
    except Exception as e:  # fronteira de isolamento: o stream segue para a próxima etapa
        logger.warning(f"{descricao}: {e}")
        return []


async def _visao_externa_segura(
    img_bytes: bytes,
    cfg: _ExtractionConfig,
    *,
    source_identifier: str,
    descricao: str,
) -> tuple[list[dict[str, Any]], str | None]:
    """Visão externa best-effort. Retorna (raw_prods, erro_pagina)."""
    try:
        raw_prods = await extract_page_products_vision(
            img_bytes,
            cfg.vision_client,
            source_identifier=source_identifier,
            session_factory=cfg.session_factory,
            ambiente="externo",
        )
        return raw_prods, None
    except Exception as e:  # fronteira de isolamento: o erro vai ao resultado da página
        logger.error(f"{descricao}: {e}")
        return [], f"Falha ao consultar modelo de visão externo: {e}"


async def _processar_bloco_texto(
    bloco: str,
    num_bloco: int,
    num_blocos_total: int,
    pagina_global: int,
    total_paginas: int,
    filename: str,
    local_client: Any,
) -> tuple[str, str]:  # (sse_progresso, sse_pagina_concluida)
    progresso = {
        "pagina": pagina_global,
        "total": total_paginas,
        "status": f"Extraindo {filename} (trecho {num_bloco}/{num_blocos_total})",
    }
    raw_prods: list[dict[str, Any]] = []
    if local_client:
        raw_prods = await _extrair_local_seguro(
            bloco, local_client, f"Erro na extração local do texto {filename}"
        )
    produtos = [
        _montar_produto(
            item,
            pagina_origem=num_bloco,
            provider_usado="local",
            confianca=0.85,
            fotos_pagina=[],
        )
        for item in raw_prods
    ]
    page_result = CatalogPageResult(
        pagina=num_bloco,
        total_paginas=total_paginas,
        produtos=produtos,
        provider_usado="local",
    )
    return _eventos_sse(progresso, page_result)


async def _extrair_pdf_local_com_fallback(
    *,
    texto_pagina: str,
    img_bytes: bytes | None,
    filename: str,
    num_pagina_pdf: int,
    cfg: _ExtractionConfig,
) -> tuple[str, list[dict[str, Any]], str | None]:
    """Tenta extração local por texto e, se vazio, fallback externo por visão."""
    provider_usado = "local"
    raw_prods: list[dict[str, Any]] = []
    erro_pagina: str | None = None

    if len(texto_pagina.strip()) >= 30 and cfg.local_client:
        raw_prods = await _extrair_local_seguro(
            texto_pagina, cfg.local_client, "Erro na extração local"
        )

    pode_usar_fallback_externo = (
        not raw_prods and cfg.fallback_external and bool(img_bytes) and bool(cfg.vision_client)
    )
    if pode_usar_fallback_externo:
        raw_prods, erro_pagina = await _visao_externa_segura(
            img_bytes,  # type: ignore[arg-type]
            cfg,
            source_identifier=f"{filename}#p{num_pagina_pdf}",
            descricao="Erro no fallback de visão externa",
        )
        if erro_pagina is None:
            provider_usado = "external"

    return provider_usado, raw_prods, erro_pagina


async def _extrair_produtos_pagina_pdf(
    *,
    texto_pagina: str,
    img_bytes: bytes | None,
    filename: str,
    num_pagina_pdf: int,
    cfg: _ExtractionConfig,
) -> tuple[str, list[dict[str, Any]], str | None]:  # (provider_usado, raw_prods, erro)
    """Despacha para local ou externo e retorna (provider_usado, raw_prods, erro_pagina)."""
    if cfg.provider == "external":
        raw_prods: list[dict[str, Any]] = []
        erro_pagina: str | None = None
        if img_bytes and cfg.vision_client:
            raw_prods, erro_pagina = await _visao_externa_segura(
                img_bytes,
                cfg,
                source_identifier=f"{filename}#p{num_pagina_pdf}",
                descricao="Erro na visão externa",
            )
        return cfg.provider, raw_prods, erro_pagina

    return await _extrair_pdf_local_com_fallback(
        texto_pagina=texto_pagina,
        img_bytes=img_bytes,
        filename=filename,
        num_pagina_pdf=num_pagina_pdf,
        cfg=cfg,
    )


def _atribuir_foto_produto(idx: int, figuras: list[str], total_prods: int) -> str | None:
    """Retorna a URL da figura a associar ao produto de índice `idx`."""
    if not figuras:
        return None
    if idx < len(figuras):
        return figuras[idx]
    if len(figuras) == 1 and total_prods == 1:
        return figuras[0]
    return None


def _renderizar_pagina_pdf(
    page: Any, num_pagina_pdf: int, temp_dir: Path
) -> tuple[bytes | None, Image.Image | None, str | None]:
    """Renderiza a página como JPEG. Retorna (img_bytes, pil_img, temp_img_url)."""
    temp_img_name = f"cat_{uuid.uuid4().hex[:12]}.jpg"
    temp_img_path = temp_dir / temp_img_name
    try:
        pil_img = page.to_image(resolution=150).original
        img_buf = io.BytesIO()
        pil_img.save(img_buf, format="JPEG", quality=85)
        img_bytes = img_buf.getvalue()
        temp_img_path.write_bytes(img_bytes)
        return img_bytes, pil_img, f"/api/uploads/produtos/temp/{temp_img_name}"
    except Exception as e:
        logger.warning(f"Não foi possível renderizar imagem da página {num_pagina_pdf} do PDF: {e}")
        return None, None, None


async def _processar_pagina_pdf(
    page: Any,
    idx: int,
    num_pages: int,
    pagina_global: int,
    total_paginas: int,
    filename: str,
    cfg: _ExtractionConfig,
) -> tuple[str, str]:  # (sse_progresso, sse_pagina_concluida)
    num_pagina_pdf = idx + 1
    progresso = {
        "pagina": pagina_global,
        "total": total_paginas,
        "status": f"Extraindo {filename} (página {num_pagina_pdf}/{num_pages})",
    }

    texto_pagina = _extrair_texto_pagina(page)
    img_bytes, pil_img, temp_img_url = _renderizar_pagina_pdf(page, num_pagina_pdf, cfg.temp_dir)

    figuras_pagina: list[str] = []
    if pil_img:
        try:
            figuras_pagina = _extrair_figuras_pagina(page, pil_img, cfg.temp_dir)
        except Exception as e:
            logger.warning(f"Erro ao extrair figuras recortadas da página {num_pagina_pdf}: {e}")

    provider_usado, raw_prods, erro_pagina = await _extrair_produtos_pagina_pdf(
        texto_pagina=texto_pagina,
        img_bytes=img_bytes,
        filename=filename,
        num_pagina_pdf=num_pagina_pdf,
        cfg=cfg,
    )

    produtos: list[ExtractedProduct] = [
        _montar_produto(
            item,
            pagina_origem=num_pagina_pdf,
            provider_usado=provider_usado,
            confianca=0.95 if provider_usado == "external" else 0.85,
            imagem_temp_url=_atribuir_foto_produto(i, figuras_pagina, len(raw_prods)),
            fotos_pagina=figuras_pagina,
        )
        for i, item in enumerate(raw_prods)
    ]

    page_result = CatalogPageResult(
        pagina=num_pagina_pdf,
        total_paginas=total_paginas,
        produtos=produtos,
        provider_usado=provider_usado,
        imagem_preview_url=temp_img_url,
        fotos_pagina=figuras_pagina,
        erro=erro_pagina if not produtos else None,
    )
    return _eventos_sse(progresso, page_result)


async def _tentar_extracao_local_imagem(
    content: bytes,
    filename: str,
    local_client: Any,
    session_factory: Any,
) -> tuple[list[dict[str, Any]], str]:
    """Tenta OCR→local e depois visão local. Retorna (raw_prods, provider_usado)."""
    raw_prods: list[dict[str, Any]] = []
    provider_usado = "local"

    texto_ocr = ""
    try:
        texto_ocr = extract_text_from_bytes(content)
    except (ImageFormatError, OcrIndisponivelError) as e:
        logger.warning(f"OCR indisponível/falhou para imagem {filename}: {e}")

    if len(texto_ocr.strip()) >= 30:
        raw_prods = await _extrair_local_seguro(
            texto_ocr, local_client, f"Erro na extração local (OCR) da imagem {filename}"
        )

    if not raw_prods:
        try:
            raw_prods = await extract_page_products_vision(
                content,
                local_client,
                source_identifier=filename,
                session_factory=session_factory,
                ambiente="interno",
            )
        except Exception as e:
            logger.warning(f"Erro na visão local da imagem {filename}: {e}")

    return raw_prods, provider_usado


async def _tentar_extracao_externa_imagem(
    content: bytes,
    filename: str,
    cfg: _ExtractionConfig,
) -> tuple[list[dict[str, Any]], str, str | None]:
    """Tenta visão externa. Retorna (raw_prods, provider_usado, erro_pagina)."""
    raw_prods, erro = await _visao_externa_segura(
        content,
        cfg,
        source_identifier=filename,
        descricao=f"Erro na visão externa para imagem {filename}",
    )
    return raw_prods, "external", erro


def _salvar_imagem_temp(content: bytes, temp_dir: Path) -> str:
    """Grava a imagem enviada em `temp_dir` e devolve a URL temporária pública."""
    temp_img_name = f"cat_{uuid.uuid4().hex[:12]}.jpg"
    (temp_dir / temp_img_name).write_bytes(content)
    return f"/api/uploads/produtos/temp/{temp_img_name}"


def _erro_sem_resultado(raw_prods: list[dict[str, Any]]) -> str | None:
    """Mensagem de erro genérica quando nenhuma etapa da cascata achou produtos."""
    if raw_prods:
        return None
    return (
        "Nenhum produto detectado (OCR, visão local e visão externa "
        "indisponíveis ou sem resultado)."
    )


async def _extrair_produtos_imagem(
    filename: str, content: bytes, cfg: _ExtractionConfig
) -> tuple[list[dict[str, Any]], str, str | None]:
    """Cascata local (OCR→visão) → externo. Retorna (raw_prods, provider_usado, erro)."""
    provider_usado = "external"
    raw_prods: list[dict[str, Any]] = []
    erro_pagina: str | None = None

    if cfg.provider != "external" and cfg.local_client:
        raw_prods, provider_usado = await _tentar_extracao_local_imagem(
            content, filename, cfg.local_client, cfg.session_factory
        )

    deve_tentar_externo = not raw_prods and (cfg.provider == "external" or cfg.fallback_external)
    if deve_tentar_externo and cfg.vision_client:
        raw_prods, provider_usado, erro_pagina = await _tentar_extracao_externa_imagem(
            content, filename, cfg
        )

    return raw_prods, provider_usado, erro_pagina or _erro_sem_resultado(raw_prods)


async def _processar_imagem_avulsa(
    filename: str,
    content: bytes,
    pagina_global: int,
    total_paginas: int,
    cfg: _ExtractionConfig,
) -> tuple[str, str]:  # (sse_progresso, sse_pagina_concluida)
    progresso = {
        "pagina": pagina_global,
        "total": total_paginas,
        "status": f"Extraindo imagem {filename}",
    }
    temp_img_url = _salvar_imagem_temp(content, cfg.temp_dir)
    raw_prods, provider_usado, erro_pagina = await _extrair_produtos_imagem(filename, content, cfg)

    produtos = [
        _montar_produto(
            item,
            pagina_origem=pagina_global,
            provider_usado=provider_usado,
            confianca=0.95,
            imagem_temp_url=temp_img_url if (len(raw_prods) == 1 or i == 0) else None,
            fotos_pagina=[temp_img_url],
        )
        for i, item in enumerate(raw_prods)
    ]
    page_result = CatalogPageResult(
        pagina=pagina_global,
        total_paginas=total_paginas,
        produtos=produtos,
        provider_usado=provider_usado,
        imagem_preview_url=temp_img_url,
        fotos_pagina=[temp_img_url],
        erro=erro_pagina if not produtos else None,
    )
    return _eventos_sse(progresso, page_result)


def _page_result_do_sse(sse_page: str) -> CatalogPageResult:
    """Relê o `CatalogPageResult` que acabou de ser serializado no evento SSE."""
    return CatalogPageResult.model_validate_json(sse_page.split("data: ", 1)[1].rstrip())


@dataclass(frozen=True)
class _ArquivoPlano:
    """Um arquivo do lote já classificado, com o que a extração precisa saber dele."""

    filename: str
    content: bytes
    file_type: str  # "text" | "pdf" | "image"
    num_pages: int
    paginas_alvo: set[int] | None


async def _processar_arquivo_stream(
    arquivo: _ArquivoPlano,
    pagina_global_start: int,
    total_paginas: int,
    cfg: _ExtractionConfig,
) -> AsyncGenerator[tuple[str, str]]:
    """Gera pares (sse_progresso, sse_pagina_concluida) para um único arquivo."""
    filename, content, num_pages = arquivo.filename, arquivo.content, arquivo.num_pages
    file_type, paginas_alvo = arquivo.file_type, arquivo.paginas_alvo
    pagina_global = pagina_global_start

    if file_type == "text":
        for num_bloco, bloco in enumerate(_blocos_de_texto(content), start=1):
            pagina_global += 1
            yield await _processar_bloco_texto(
                bloco,
                num_bloco,
                num_pages,
                pagina_global,
                total_paginas,
                filename,
                cfg.local_client,
            )

    elif file_type == "pdf":
        if num_pages == 0:
            return
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for idx, page in enumerate(pdf.pages):
                if paginas_alvo is not None and (idx + 1) not in paginas_alvo:
                    continue
                pagina_global += 1
                yield await _processar_pagina_pdf(
                    page, idx, num_pages, pagina_global, total_paginas, filename, cfg
                )

    else:
        pagina_global += 1
        yield await _processar_imagem_avulsa(filename, content, pagina_global, total_paginas, cfg)


async def extract_catalog_stream(
    files: list[tuple[str, bytes]],
    provider: str,
    fallback_external: bool,
    temp_dir: Path,
    local_client: Any = None,
    vision_client: Any = None,
    page_range: str | None = None,
    session_factory: Any = None,
) -> AsyncGenerator[str]:
    """Itera sobre documentos ou imagens e gera stream de eventos SSE."""
    temp_dir.mkdir(parents=True, exist_ok=True)
    cfg = _ExtractionConfig(
        provider=provider,
        fallback_external=fallback_external,
        temp_dir=temp_dir,
        local_client=local_client,
        vision_client=vision_client,
        session_factory=session_factory,
    )

    # Pré-calcula total de páginas / imagens
    total_paginas = 0
    file_pages_plan: list[_ArquivoPlano] = []
    for filename, content in files:
        lower = filename.lower()
        if lower.endswith(EXTENSOES_TEXTO):
            blocos = _blocos_de_texto(content)
            total_paginas += len(blocos)
            file_pages_plan.append(_ArquivoPlano(filename, content, "text", len(blocos), None))
        elif lower.endswith(".pdf"):
            try:
                with pdfplumber.open(io.BytesIO(content)) as pdf:
                    num_pages = len(pdf.pages)
                    paginas_alvo = _parse_page_range(page_range, num_pages)
                    qtd = len(paginas_alvo) if paginas_alvo is not None else num_pages
                    total_paginas += qtd
                    file_pages_plan.append(
                        _ArquivoPlano(filename, content, "pdf", num_pages, paginas_alvo)
                    )
            except Exception as e:
                logger.error(f"Erro ao abrir PDF {filename}: {e}")
                file_pages_plan.append(_ArquivoPlano(filename, content, "pdf", 0, None))
        else:
            total_paginas += 1
            file_pages_plan.append(_ArquivoPlano(filename, content, "image", 1, None))

    pagina_global = 0
    total_produtos_extraidos = 0

    for arquivo in file_pages_plan:
        pages_yielded = 0
        async for sse_prog, sse_page in _processar_arquivo_stream(
            arquivo, pagina_global, total_paginas, cfg
        ):
            yield sse_prog
            total_produtos_extraidos += len(_page_result_do_sse(sse_page).produtos)
            yield sse_page
            pages_yielded += 1
        pagina_global += pages_yielded

    final = {"total_produtos": total_produtos_extraidos, "total_paginas": total_paginas}
    yield f"event: done\ndata: {json.dumps(final)}\n\n"
