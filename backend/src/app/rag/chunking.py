"""Chunking de texto para ingestão no RAG (R4).

# MVP: divisão por tamanho fixo de caracteres com sobreposição simples,
# preferindo cortar numa quebra de linha quando existir uma dentro da janela
# do chunk (evita partir uma linha de tabela/bullet ao meio — ver
# `app.rag.pdf_extract`, que agora preserva essas quebras de linha como
# separadores de bloco/coluna), mas sem respeitar limites semânticos mais
# finos (frases/parágrafos) nem a tokenização real do modelo de embeddings —
# suficiente para o protótipo, evolução futura fica para um chunking mais
# robusto (ver docs/ARCHITECTURE.md §5, linha "RAG — textos, PDFs, BD e
# sites").
"""

DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 100


def _normalizar_preservando_linhas(text: str) -> str:
    """Colapsa espaços/tabs repetidos dentro de cada linha (como antes), mas
    preserva as quebras de linha entre linhas não vazias — elas viram pontos
    de corte preferenciais em `chunk_text`."""
    linhas = (" ".join(linha.split()) for linha in text.splitlines())
    return "\n".join(linha for linha in linhas if linha)


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Divide `text` em pedaços de até `chunk_size` caracteres, com overlap.

    Espaços/tabs repetidos dentro de uma linha são normalizados para um
    único espaço antes do corte, mas quebras de linha são preservadas e
    usadas como ponto de corte preferencial (o corte só cai exatamente em
    `chunk_size` quando não há nenhuma quebra de linha dentro da janela).
    Retorna lista vazia para texto vazio/só espaços.
    """
    if chunk_size <= overlap:
        raise ValueError("chunk_size deve ser maior que overlap")

    cleaned = _normalizar_preservando_linhas(text)
    if not cleaned:
        return []

    chunks = []
    start = 0
    n = len(cleaned)
    while start < n:
        alvo = start + chunk_size
        end = alvo
        if end < n:
            corte = cleaned.rfind("\n", start, end)
            if corte > start:
                end = corte
        chunks.append(cleaned[start:end])
        if alvo >= n:
            break
        # O próximo `start` é calculado a partir de `alvo` (o corte de
        # tamanho fixo, não o corte ajustado pra quebra de linha) — se
        # usássemos o `end` ajustado, a mesma quebra de linha podia ser
        # "reencontrada" na janela seguinte e travar o avanço em passos de
        # 1 caractere. `min(..., end)` garante que nunca pulamos conteúdo
        # ainda não emitido (nunca começamos depois de onde este chunk
        # terminou); `max(start + 1, ...)` garante progresso mínimo.
        start = max(start + 1, min(alvo - overlap, end))
    return chunks
