"""Extração de texto de PDF para ingestão no RAG (R4).

# MVP: extração via `pdfplumber`, com uma heurística de detecção de layout
# em 2 colunas: procura um corredor vertical sem nenhuma palavra na faixa
# central da página e, se achar, extrai cada coluna separadamente — evita
# embaralhar a ordem de leitura entre produtos/blocos lado a lado, comum em
# catálogos (ver docs/ARCHITECTURE.md §5, decisão registrada 2026-09-17).
# A heurística cobre só 2 colunas e só quando existe um corredor "limpo"
# (sem nenhuma palavra) atravessando toda a altura da página — layouts com
# 3+ colunas, ou com rótulos/cabeçalhos posicionados fora do padrão (ex. um
# título de seção lateral que invade a faixa onde o corredor ficaria), caem
# no fallback de extrair a página inteira normalmente. Esse fallback ainda
# preserva a ordem de leitura melhor do que a extração anterior via `pypdf`
# (testado nos PDFs reais do projeto) — não há regressão nos casos que a
# heurística não cobre, só a ausência do ganho extra do split por coluna.
# Sem OCR para PDFs escaneados/baseados em imagem (isso é R6, Fase 3).
"""

from io import BytesIO
from pathlib import Path

import pdfplumber

# Ignora a faixa dos 15% mais próximos de cada margem lateral ao procurar o
# corredor — evita falso positivo com margens/sangria de design, que quase
# sempre estão vazias e não são um corredor entre colunas de conteúdo.
MARGEM_RELATIVA = 0.15
# Corredor precisa ter pelo menos 2% da largura da página E pelo menos 15pt
# em valor absoluto — só o critério relativo deixava passar falso positivo
# em páginas com pouco texto (o espaçamento natural entre 2-3 palavras já
# passava de 2% de uma página pequena). 15pt é bem menor que um corredor
# real entre colunas (tipicamente 20-40pt+), mas maior que o espaçamento
# entre palavras de um mesmo bloco de texto.
LARGURA_MIN_GAP_RELATIVA = 0.02
LARGURA_MIN_GAP_ABSOLUTA = 15.0


class PdfExtractionError(Exception):
    """Levantado quando o PDF não pode ser aberto ou processado."""


def _detectar_gap_coluna(page: pdfplumber.page.Page) -> float | None:
    """Procura o maior corredor vertical sem nenhuma palavra dentro da
    faixa central da página. Retorna o x do meio do corredor (ponto de
    corte para dividir a página em coluna esquerda/direita), ou `None` se
    não achar nenhum corredor largo o suficiente.
    """
    words = page.extract_words()
    if not words:
        return None

    largura = page.width
    faixa_min = largura * MARGEM_RELATIVA
    faixa_max = largura * (1 - MARGEM_RELATIVA)

    intervalos = sorted(
        (word["x0"], word["x1"])
        for word in words
        if word["x1"] > faixa_min and word["x0"] < faixa_max
    )
    if not intervalos:
        return None

    cursor = faixa_min
    melhor_gap: tuple[float, float] | None = None
    for x0, x1 in intervalos:
        if x0 > cursor:
            gap = (cursor, x0)
            if melhor_gap is None or (gap[1] - gap[0]) > (melhor_gap[1] - melhor_gap[0]):
                melhor_gap = gap
        cursor = max(cursor, x1)
    if cursor < faixa_max:
        gap = (cursor, faixa_max)
        if melhor_gap is None or (gap[1] - gap[0]) > (melhor_gap[1] - melhor_gap[0]):
            melhor_gap = gap

    if melhor_gap is None:
        return None
    largura_gap = melhor_gap[1] - melhor_gap[0]
    limite = max(largura * LARGURA_MIN_GAP_RELATIVA, LARGURA_MIN_GAP_ABSOLUTA)
    if largura_gap >= limite:
        return (melhor_gap[0] + melhor_gap[1]) / 2
    return None


def _extrair_texto_pagina(page: pdfplumber.page.Page) -> str:
    gap_x = _detectar_gap_coluna(page)
    if gap_x is None:
        return page.extract_text() or ""

    coluna_esquerda = page.crop((0, 0, gap_x, page.height))
    coluna_direita = page.crop((gap_x, 0, page.width, page.height))
    texto_esquerda = coluna_esquerda.extract_text() or ""
    texto_direita = coluna_direita.extract_text() or ""
    return "\n".join(texto for texto in (texto_esquerda, texto_direita) if texto)


def extract_text_from_pdf(source: bytes | str | Path) -> str:
    """Extrai o texto de um PDF a partir de bytes ou de um caminho de arquivo.

    Detecta páginas em layout de 2 colunas (comum em catálogos com produtos
    lado a lado) e extrai cada coluna separadamente para preservar a ordem
    de leitura por bloco; páginas de coluna única são extraídas normalmente.
    Levanta `PdfExtractionError` se o PDF não puder ser aberto/processado.
    """
    try:
        with pdfplumber.open(BytesIO(source) if isinstance(source, bytes) else source) as pdf:
            pages_text = [_extrair_texto_pagina(page) for page in pdf.pages]
    except Exception as exc:  # pdfplumber/pdfminer levantam tipos variados
        raise PdfExtractionError(f"Falha ao processar PDF: {exc}") from exc
    return "\n".join(pages_text)
