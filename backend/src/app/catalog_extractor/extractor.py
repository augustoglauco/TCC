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
from pathlib import Path
from typing import Any

import pdfplumber
from PIL import Image

from app.models.catalog_extractor import CatalogPageResult, ExtractedProduct
from app.rag.pdf_extract import _extrair_texto_pagina

logger = logging.getLogger(__name__)

EXTENSOES_TEXTO = (".txt", ".md", ".csv")
TAMANHO_BLOCO_TEXTO = 6000

_CODE_FENCE_RE = re.compile(r"^```(?:\w+)?\s*\n?(.*?)\n?```$", re.DOTALL)

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


def _parse_products_json(raw_text: str) -> list[dict[str, Any]]:
    stripped = raw_text.strip()
    match = _CODE_FENCE_RE.match(stripped)
    if match:
        stripped = match.group(1).strip()
    else:
        # Se contiver ```json em qualquer parte do texto, extrai bloco
        sub_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", stripped, re.DOTALL)
        if sub_match:
            stripped = sub_match.group(1).strip()
        else:
            # Tenta encontrar primeiro '[' e último ']'
            start = stripped.find("[")
            end = stripped.rfind("]")
            if start != -1 and end != -1 and end > start:
                stripped = stripped[start : end + 1]

    try:
        data = json.loads(stripped)
        if isinstance(data, list):
            valid_items = []
            for item in data:
                if isinstance(item, dict) and item.get("nome"):
                    valid_items.append(item)
            return valid_items
        elif isinstance(data, dict) and data.get("nome"):
            return [data]
        return []
    except Exception as exc:
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
        if "-" in chunk:
            parts = chunk.split("-", 1)
            start_str, end_str = parts[0].strip(), parts[1].strip()

            start = int(start_str) if start_str.isdigit() else 1
            end = int(end_str) if end_str.isdigit() else max_pages

            if start > end:
                start, end = end, start

            for p in range(start, end + 1):
                if 1 <= p <= max_pages:
                    pages.add(p)
        elif chunk.isdigit():
            p = int(chunk)
            if 1 <= p <= max_pages:
                pages.add(p)

    return pages


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
    raw_response = getattr(res, "response", getattr(res, "text", str(res)))
    return _parse_products_json(raw_response)


async def extract_page_products_vision(
    image_bytes: bytes,
    vision_client: Any,
    prompt: str | None = None,
    source_identifier: str | None = None,
    session: Any = None,
    session_factory: Any = None,
) -> list[dict[str, Any]]:
    used_prompt = prompt or VISION_EXTRACTION_PROMPT
    raw_response = await vision_client.describe_image(image_bytes, used_prompt)

    # Telemetria e auditoria de custo da extração de catálogo por visão
    p_tok = getattr(raw_response, "prompt_tokens", 0) or 0
    c_tok = getattr(raw_response, "completion_tokens", 0) or 0
    c_prompt = getattr(raw_response, "cost_prompt_usd", 0.0) or 0.0
    c_comp = getattr(raw_response, "cost_completion_usd", 0.0) or 0.0
    c_tot = getattr(raw_response, "estimated_cost_usd", 0.0) or (c_prompt + c_comp)
    model = getattr(raw_response, "model_name", None) or getattr(vision_client, "vision_model", None)

    # Garante contabilização de tokens e operação mesmo se o modelo for gratuito ou omitir usage
    if (p_tok + c_tok > 0) or (c_tot > 0) or raw_response:
        if p_tok == 0 and c_tok == 0:
            p_tok = max(1, len(used_prompt) // 4) + 500
            c_tok = max(1, len(str(raw_response)) // 4)

        try:
            from app.services.ingestion_metrics import record_ingestion_cost
            if session is None and session_factory is not None:
                await record_ingestion_cost(
                    source_type="catalog_extractor",
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    cost_prompt_usd=c_prompt,
                    cost_completion_usd=c_comp,
                    total_cost_usd=c_tot,
                    source_identifier=source_identifier,
                    model_name=model,
                    session_factory=session_factory,
                )
            else:
                await record_ingestion_cost(
                    source_type="catalog_extractor",
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    cost_prompt_usd=c_prompt,
                    cost_completion_usd=c_comp,
                    total_cost_usd=c_tot,
                    source_identifier=source_identifier,
                    model_name=model,
                    session=session,
                    commit=True if session is not None else False,
                )
        except Exception as e:
            logger.warning("Falha ao registrar métricas de telemetria de catálogo: %s", e)

    return _parse_products_json(raw_response)


def _extrair_figuras_pagina(page: Any, pil_img: Image.Image, temp_dir: Path) -> list[str]:
    """Detecta, filtra e recorta figuras individuais da página do catálogo."""
    page_w = float(getattr(page, "width", 0) or 1)
    page_h = float(getattr(page, "height", 0) or 1)
    scale_x = pil_img.width / page_w
    scale_y = pil_img.height / page_h

    candidates: list[dict[str, float]] = []
    raw_images = getattr(page, "images", []) or []

    for im in raw_images:
        w = float(im.get("width", 0) or 0)
        h = float(im.get("height", 0) or 0)
        x0 = float(im.get("x0", 0) or 0)
        top = float(im.get("top", 0) or 0)
        x1 = float(im.get("x1", x0 + w) or (x0 + w))
        bottom = float(im.get("bottom", top + h) or (top + h))

        # Ignora elementos minúsculos (ícones de status, marcadores, bullets)
        if w < 32 or h < 32 or (w * h) < 1600:
            continue

        # Ignora linhas e divisores horizontais/verticais estreitos
        if (w / max(h, 1) > 5.5) or (h / max(w, 1) > 5.5):
            continue

        # Ignora fundo de página inteiro (marca d'água / background da página)
        if w >= page_w * 0.92 and h >= page_h * 0.92:
            continue

        # Ignora logos comuns de cabeçalho e rodapé nas margens superior e inferior
        if (top < 38 or bottom > page_h - 38) and (w < 160 and h < 65):
            continue

        # Deduplicação de caixas quase idênticas (ex: sombra projetada ou sobreposição idêntica)
        duplicate = False
        for cand in candidates:
            if (
                abs(cand["x0"] - x0) < 6
                and abs(cand["top"] - top) < 6
                and abs(cand["w"] - w) < 6
                and abs(cand["h"] - h) < 6
            ):
                duplicate = True
                break
        if duplicate:
            continue

        candidates.append({"x0": x0, "top": top, "x1": x1, "bottom": bottom, "w": w, "h": h})

    # Ordena espacialmente por linha visual (top agrupado a cada ~35pt) e
    # depois da esquerda para a direita (x0)
    candidates.sort(key=lambda c: (round(c["top"] / 35.0), c["x0"]))

    figuras_urls: list[str] = []
    for c in candidates:
        pad = 2.5
        px_x0 = max(0, int((c["x0"] - pad) * scale_x))
        px_y0 = max(0, int((c["top"] - pad) * scale_y))
        px_x1 = min(pil_img.width, int((c["x1"] + pad) * scale_x))
        px_y1 = min(pil_img.height, int((c["bottom"] + pad) * scale_y))

        if (px_x1 - px_x0) < 24 or (px_y1 - px_y0) < 24:
            continue

        crop = pil_img.crop((px_x0, px_y0, px_x1, px_y1))

        if crop.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", crop.size, (255, 255, 255))
            if crop.mode == "P":
                crop = crop.convert("RGBA")
            mask = crop.split()[-1] if len(crop.split()) > 3 else None
            bg.paste(crop, mask=mask)
            crop = bg
        elif crop.mode != "RGB":
            crop = crop.convert("RGB")

        crop_name = f"crop_{uuid.uuid4().hex[:12]}.jpg"
        crop_path = temp_dir / crop_name
        crop.save(crop_path, format="JPEG", quality=90)
        figuras_urls.append(f"/api/uploads/produtos/temp/{crop_name}")

    return figuras_urls


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

    # 1. Pré-calcula total de páginas / imagens
    total_paginas = 0
    file_pages_plan: list[
        tuple[str, bytes, str, int, set[int] | None]
    ] = []  # (nome, bytes, tipo, total_do_arquivo, paginas_filtradas)
    for filename, content in files:
        lower = filename.lower()
        if lower.endswith(EXTENSOES_TEXTO):
            blocos = _blocos_de_texto(content)
            total_paginas += len(blocos)
            file_pages_plan.append((filename, content, "text", len(blocos), None))
        elif lower.endswith(".pdf"):
            try:
                with pdfplumber.open(io.BytesIO(content)) as pdf:
                    num_pages = len(pdf.pages)
                    paginas_alvo = _parse_page_range(page_range, num_pages)
                    qtd_processar = len(paginas_alvo) if paginas_alvo is not None else num_pages
                    total_paginas += qtd_processar
                    file_pages_plan.append((filename, content, "pdf", num_pages, paginas_alvo))
            except Exception as e:
                logger.error(f"Erro ao abrir PDF {filename}: {e}")
                file_pages_plan.append((filename, content, "pdf", 0, None))
        else:
            total_paginas += 1
            file_pages_plan.append((filename, content, "image", 1, None))

    pagina_global = 0
    total_produtos_extraidos = 0

    for filename, content, file_type, num_pages, paginas_alvo in file_pages_plan:
        if file_type == "text":
            for num_bloco, bloco in enumerate(_blocos_de_texto(content), start=1):
                pagina_global += 1
                progresso = {
                    "pagina": pagina_global,
                    "total": total_paginas,
                    "status": f"Extraindo {filename} (trecho {num_bloco}/{num_pages})",
                }
                yield f"event: progresso\ndata: {json.dumps(progresso)}\n\n"

                raw_prods: list[dict[str, Any]] = []
                if local_client:
                    try:
                        raw_prods = await extract_page_products_local(bloco, local_client)
                    except Exception as e:
                        logger.warning(f"Erro na extração local do texto {filename}: {e}")

                produtos = [
                    ExtractedProduct(
                        nome=str(item.get("nome", "")),
                        descricao=str(item.get("descricao", "") or ""),
                        categoria=str(item.get("categoria", "") or "Geral"),
                        preco_base_fornecedor=float(item["preco_base_fornecedor"])
                        if item.get("preco_base_fornecedor") is not None
                        else None,
                        preco=float(item["preco"]) if item.get("preco") is not None else None,
                        especificacoes_tecnicas=str(item.get("especificacoes_tecnicas", "") or ""),
                        pagina_origem=num_bloco,
                        confianca=0.85,
                        provider_usado="local",
                    )
                    for item in raw_prods
                ]
                total_produtos_extraidos += len(produtos)
                page_result = CatalogPageResult(
                    pagina=num_bloco,
                    total_paginas=total_paginas,
                    produtos=produtos,
                    provider_usado="local",
                )
                yield f"event: pagina_concluida\ndata: {page_result.model_dump_json()}\n\n"

        elif file_type == "pdf":
            if num_pages == 0:
                continue
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for idx, page in enumerate(pdf.pages):
                    num_pagina_pdf = idx + 1
                    if paginas_alvo is not None and num_pagina_pdf not in paginas_alvo:
                        continue

                    pagina_global += 1
                    # Notifica progresso
                    progresso = {
                        "pagina": pagina_global,
                        "total": total_paginas,
                        "status": f"Extraindo {filename} (página {num_pagina_pdf}/{num_pages})",
                    }
                    yield f"event: progresso\ndata: {json.dumps(progresso)}\n\n"

                    texto_pagina = _extrair_texto_pagina(page)

                    # Renderiza imagem da página para preview e/ou visão
                    temp_img_name = f"cat_{uuid.uuid4().hex[:12]}.jpg"
                    temp_img_path = temp_dir / temp_img_name
                    img_bytes: bytes | None = None
                    pil_img: Image.Image | None = None
                    try:
                        pil_img = page.to_image(resolution=150).original
                        img_buf = io.BytesIO()
                        pil_img.save(img_buf, format="JPEG", quality=85)
                        img_bytes = img_buf.getvalue()
                        temp_img_path.write_bytes(img_bytes)
                        temp_img_url = f"/api/uploads/produtos/temp/{temp_img_name}"
                    except Exception as e:
                        logger.warning(
                            f"Não foi possível renderizar imagem da página {idx + 1} do PDF: {e}"
                        )
                        temp_img_url = None
                        pil_img = None

                    # Extrai figuras/fotos individuais recortadas da página
                    figuras_pagina: list[str] = []
                    if pil_img:
                        try:
                            figuras_pagina = _extrair_figuras_pagina(page, pil_img, temp_dir)
                        except Exception as e:
                            logger.warning(
                                f"Erro ao extrair figuras recortadas da página {idx + 1}: {e}"
                            )

                    provider_usado = provider
                    raw_prods: list[dict[str, Any]] = []
                    erro_pagina: str | None = None

                    if provider == "external":
                        if img_bytes and vision_client:
                            try:
                                raw_prods = await extract_page_products_vision(
                                    img_bytes,
                                    vision_client,
                                    source_identifier=f"{filename}#p{num_pagina_pdf}",
                                    session_factory=session_factory,
                                )
                                provider_usado = "external"
                            except Exception as e:
                                logger.error(f"Erro na visão externa: {e}")
                                erro_pagina = f"Falha ao consultar modelo de visão externo: {e}"
                    else:
                        # Tenta local se houver texto
                        if len(texto_pagina.strip()) >= 30 and local_client:
                            try:
                                raw_prods = await extract_page_products_local(
                                    texto_pagina, local_client
                                )
                                provider_usado = "local"
                            except Exception as e:
                                logger.warning(f"Erro na extração local: {e}")

                        # Fallback se local não retornou nada
                        if not raw_prods and fallback_external and img_bytes and vision_client:
                            try:
                                raw_prods = await extract_page_products_vision(
                                    img_bytes,
                                    vision_client,
                                    source_identifier=f"{filename}#p{num_pagina_pdf}",
                                    session_factory=session_factory,
                                )
                                provider_usado = "external"
                            except Exception as e:
                                logger.error(f"Erro no fallback de visão externa: {e}")
                                erro_pagina = f"Falha ao consultar modelo de visão externo: {e}"

                    # Formata produtos extraídos associando cada um à sua figura
                    # individual recortada
                    produtos: list[ExtractedProduct] = []
                    for i, item in enumerate(raw_prods):
                        foto_produto: str | None = None
                        if figuras_pagina:
                            if i < len(figuras_pagina):
                                foto_produto = figuras_pagina[i]
                            elif len(figuras_pagina) == 1 and len(raw_prods) == 1:
                                foto_produto = figuras_pagina[0]

                        produtos.append(
                            ExtractedProduct(
                                nome=str(item.get("nome", "")),
                                descricao=str(item.get("descricao", "") or ""),
                                categoria=str(item.get("categoria", "") or "Geral"),
                                preco_base_fornecedor=float(item["preco_base_fornecedor"])
                                if item.get("preco_base_fornecedor") is not None
                                else None,
                                preco=float(item["preco"])
                                if item.get("preco") is not None
                                else None,
                                especificacoes_tecnicas=str(
                                    item.get("especificacoes_tecnicas", "") or ""
                                ),
                                imagem_temp_url=foto_produto,
                                fotos_pagina=figuras_pagina,
                                pagina_origem=num_pagina_pdf,
                                confianca=0.95 if provider_usado == "external" else 0.85,
                                provider_usado=provider_usado,
                            )
                        )

                    total_produtos_extraidos += len(produtos)
                    page_result = CatalogPageResult(
                        pagina=num_pagina_pdf,
                        total_paginas=total_paginas,
                        produtos=produtos,
                        provider_usado=provider_usado,
                        imagem_preview_url=temp_img_url,
                        fotos_pagina=figuras_pagina,
                        erro=erro_pagina if not produtos else None,
                    )
                    yield f"event: pagina_concluida\ndata: {page_result.model_dump_json()}\n\n"

        else:
            # Imagem única
            pagina_global += 1
            progresso = {
                "pagina": pagina_global,
                "total": total_paginas,
                "status": f"Extraindo imagem {filename}",
            }
            yield f"event: progresso\ndata: {json.dumps(progresso)}\n\n"

            temp_img_name = f"cat_{uuid.uuid4().hex[:12]}.jpg"
            temp_img_path = temp_dir / temp_img_name
            temp_img_path.write_bytes(content)
            temp_img_url = f"/api/uploads/produtos/temp/{temp_img_name}"

            provider_usado = "external"
            raw_prods: list[dict[str, Any]] = []
            erro_pagina: str | None = None
            if vision_client:
                try:
                    raw_prods = await extract_page_products_vision(
                        content,
                        vision_client,
                        source_identifier=filename,
                        session_factory=session_factory,
                    )
                except Exception as e:
                    logger.error(f"Erro na visão para imagem {filename}: {e}")
                    erro_pagina = f"Falha ao consultar modelo de visão externo: {e}"
            else:
                erro_pagina = "Modelo de visão externo não configurado."

            produtos = []
            for i, item in enumerate(raw_prods):
                produtos.append(
                    ExtractedProduct(
                        nome=str(item.get("nome", "")),
                        descricao=str(item.get("descricao", "") or ""),
                        categoria=str(item.get("categoria", "") or "Geral"),
                        preco_base_fornecedor=float(item["preco_base_fornecedor"])
                        if item.get("preco_base_fornecedor") is not None
                        else None,
                        preco=float(item["preco"]) if item.get("preco") is not None else None,
                        especificacoes_tecnicas=str(item.get("especificacoes_tecnicas", "") or ""),
                        imagem_temp_url=temp_img_url if (len(raw_prods) == 1 or i == 0) else None,
                        fotos_pagina=[temp_img_url],
                        pagina_origem=pagina_global,
                        confianca=0.95,
                        provider_usado=provider_usado,
                    )
                )

            total_produtos_extraidos += len(produtos)
            page_result = CatalogPageResult(
                pagina=pagina_global,
                total_paginas=total_paginas,
                produtos=produtos,
                provider_usado=provider_usado,
                imagem_preview_url=temp_img_url,
                fotos_pagina=[temp_img_url],
                erro=erro_pagina if not produtos else None,
            )
            yield f"event: pagina_concluida\ndata: {page_result.model_dump_json()}\n\n"

    # Evento final
    final = {"total_produtos": total_produtos_extraidos, "total_paginas": total_paginas}
    yield f"event: done\ndata: {json.dumps(final)}\n\n"
