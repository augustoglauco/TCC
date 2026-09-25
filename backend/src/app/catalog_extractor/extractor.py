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
"""

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
"""


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


async def extract_page_products_local(
    texto: str, local_client: Any, model_name: str | None = None
) -> list[dict[str, Any]]:
    prompt = LOCAL_EXTRACTION_PROMPT.replace("{texto}", texto)
    res = await local_client.generate(prompt)
    raw_response = getattr(res, "response", getattr(res, "text", str(res)))
    return _parse_products_json(raw_response)


async def extract_page_products_vision(
    image_bytes: bytes, vision_client: Any, prompt: str | None = None
) -> list[dict[str, Any]]:
    used_prompt = prompt or VISION_EXTRACTION_PROMPT
    raw_response = await vision_client.describe_image(image_bytes, used_prompt)
    return _parse_products_json(raw_response)


async def extract_catalog_stream(
    files: list[tuple[str, bytes]],
    provider: str,
    fallback_external: bool,
    temp_dir: Path,
    local_client: Any,
    vision_client: Any,
) -> AsyncGenerator[str, None]:
    """Itera sobre documentos ou imagens e gera stream de eventos SSE."""
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 1. Pré-calcula total de páginas / imagens
    total_paginas = 0
    file_pages_plan: list[tuple[str, bytes, str, int]] = []  # (nome, bytes, tipo, total_do_arquivo)
    for filename, content in files:
        lower = filename.lower()
        if lower.endswith(".pdf"):
            try:
                with pdfplumber.open(io.BytesIO(content)) as pdf:
                    num_pages = len(pdf.pages)
                    total_paginas += num_pages
                    file_pages_plan.append((filename, content, "pdf", num_pages))
            except Exception as e:
                logger.error(f"Erro ao abrir PDF {filename}: {e}")
                file_pages_plan.append((filename, content, "pdf", 0))
        else:
            total_paginas += 1
            file_pages_plan.append((filename, content, "image", 1))

    pagina_global = 0
    total_produtos_extraidos = 0

    for filename, content, file_type, num_pages in file_pages_plan:
        if file_type == "pdf":
            if num_pages == 0:
                continue
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for idx, page in enumerate(pdf.pages):
                    pagina_global += 1
                    # Notifica progresso
                    yield f"event: progresso\ndata: {json.dumps({'pagina': pagina_global, 'total': total_paginas, 'status': f'Extraindo {filename} (página {idx+1}/{num_pages})'})}\n\n"

                    texto_pagina = _extrair_texto_pagina(page)
                    
                    # Renderiza imagem da página para preview e/ou visão
                    temp_img_name = f"cat_{uuid.uuid4().hex[:12]}.jpg"
                    temp_img_path = temp_dir / temp_img_name
                    img_bytes: bytes | None = None
                    try:
                        pil_img = page.to_image(resolution=150).original
                        img_buf = io.BytesIO()
                        pil_img.save(img_buf, format="JPEG", quality=85)
                        img_bytes = img_buf.getvalue()
                        temp_img_path.write_bytes(img_bytes)
                        temp_img_url = f"/api/uploads/produtos/temp/{temp_img_name}"
                    except Exception as e:
                        logger.warning(f"Não foi possível renderizar imagem da página {idx+1} do PDF: {e}")
                        temp_img_url = None

                    provider_usado = provider
                    raw_prods: list[dict[str, Any]] = []

                    if provider == "external":
                        if img_bytes and vision_client:
                            try:
                                raw_prods = await extract_page_products_vision(img_bytes, vision_client)
                                provider_usado = "external"
                            except Exception as e:
                                logger.error(f"Erro na visão externa: {e}")
                    else:
                        # Tenta local se houver texto
                        if len(texto_pagina.strip()) >= 30 and local_client:
                            try:
                                raw_prods = await extract_page_products_local(texto_pagina, local_client)
                                provider_usado = "local"
                            except Exception as e:
                                logger.warning(f"Erro na extração local: {e}")

                        # Fallback se local não retornou nada
                        if not raw_prods and fallback_external and img_bytes and vision_client:
                            try:
                                raw_prods = await extract_page_products_vision(img_bytes, vision_client)
                                provider_usado = "external"
                            except Exception as e:
                                logger.error(f"Erro no fallback de visão externa: {e}")

                    # Formata produtos extraídos
                    produtos: list[ExtractedProduct] = []
                    for item in raw_prods:
                        produtos.append(
                            ExtractedProduct(
                                nome=str(item.get("nome", "")),
                                descricao=str(item.get("descricao", "") or ""),
                                categoria=str(item.get("categoria", "") or "Geral"),
                                preco_base_fornecedor=float(item["preco_base_fornecedor"]) if item.get("preco_base_fornecedor") is not None else None,
                                preco=float(item["preco"]) if item.get("preco") is not None else None,
                                especificacoes_tecnicas=str(item.get("especificacoes_tecnicas", "") or ""),
                                imagem_temp_url=temp_img_url,
                                pagina_origem=pagina_global,
                                confianca=0.95 if provider_usado == "external" else 0.85,
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
                    )
                    yield f"event: pagina_concluida\ndata: {page_result.model_dump_json()}\n\n"

        else:
            # Imagem única
            pagina_global += 1
            yield f"event: progresso\ndata: {json.dumps({'pagina': pagina_global, 'total': total_paginas, 'status': f'Extraindo imagem {filename}'})}\n\n"

            temp_img_name = f"cat_{uuid.uuid4().hex[:12]}.jpg"
            temp_img_path = temp_dir / temp_img_name
            temp_img_path.write_bytes(content)
            temp_img_url = f"/api/uploads/produtos/temp/{temp_img_name}"

            provider_usado = "external"
            raw_prods: list[dict[str, Any]] = []
            if vision_client:
                try:
                    raw_prods = await extract_page_products_vision(content, vision_client)
                except Exception as e:
                    logger.error(f"Erro na visão para imagem {filename}: {e}")

            produtos = []
            for item in raw_prods:
                produtos.append(
                    ExtractedProduct(
                        nome=str(item.get("nome", "")),
                        descricao=str(item.get("descricao", "") or ""),
                        categoria=str(item.get("categoria", "") or "Geral"),
                        preco_base_fornecedor=float(item["preco_base_fornecedor"]) if item.get("preco_base_fornecedor") is not None else None,
                        preco=float(item["preco"]) if item.get("preco") is not None else None,
                        especificacoes_tecnicas=str(item.get("especificacoes_tecnicas", "") or ""),
                        imagem_temp_url=temp_img_url,
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
            )
            yield f"event: pagina_concluida\ndata: {page_result.model_dump_json()}\n\n"

    # Evento final
    yield f"event: done\ndata: {json.dumps({'total_produtos': total_produtos_extraidos, 'total_paginas': total_paginas})}\n\n"
