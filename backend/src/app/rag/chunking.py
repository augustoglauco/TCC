"""Chunking de texto para ingestão no RAG (R4).

# MVP: divisão por tamanho fixo de caracteres com sobreposição simples, sem
# respeitar limites semânticos (frases/parágrafos) nem a tokenização real do
# modelo de embeddings — suficiente para o protótipo, evolução futura fica
# para um chunking mais robusto (ver docs/ARCHITECTURE.md §5, linha "RAG —
# textos, PDFs, BD e sites").
"""

DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 100


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Divide `text` em pedaços de até `chunk_size` caracteres, com overlap.

    Espaços em branco (incluindo quebras de linha) são normalizados para um
    único espaço antes do corte. Retorna lista vazia para texto vazio/só
    espaços.
    """
    if chunk_size <= overlap:
        raise ValueError("chunk_size deve ser maior que overlap")

    cleaned = " ".join(text.split())
    if not cleaned:
        return []

    chunks = []
    start = 0
    while start < len(cleaned):
        end = start + chunk_size
        chunks.append(cleaned[start:end])
        if end >= len(cleaned):
            break
        start = end - overlap
    return chunks
