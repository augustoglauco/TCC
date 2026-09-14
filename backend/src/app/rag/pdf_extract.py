"""Extração de texto de PDF para ingestão no RAG (R4).

# MVP: extração via `pypdf` (texto simples por página, concatenado) — sem
# OCR para PDFs baseados em imagem/escaneados (isso é R6, Fase 3) e sem
# preservar layout/tabelas (ver docs/ARCHITECTURE.md §5).
"""

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader


def extract_text_from_pdf(source: bytes | str | Path) -> str:
    """Extrai o texto de um PDF a partir de bytes ou de um caminho de arquivo."""
    reader = PdfReader(BytesIO(source) if isinstance(source, bytes) else source)
    pages_text = (page.extract_text() or "" for page in reader.pages)
    return "\n".join(pages_text)
