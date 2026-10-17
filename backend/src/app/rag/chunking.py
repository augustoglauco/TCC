"""Chunking recursivo de texto para ingestão no RAG (R4, Fase 10 — Etapa 3).

Divide o texto recursivamente seguindo a hierarquia de separadores
(`"\\n\\n"` → `"\\n"` → `". "` → `" "` → corte duro) e mede `chunk_size` e
`overlap` em **tokens** quando um `tokenizer` é informado (ou em caracteres
quando `tokenizer=None`, preservando compatibilidade com chamadores diretos).
Ver `docs/ARCHITECTURE.md` (decisão de 2026-10-17) e `docs/EVALUATION.md`
Seção 2.1 (Etapa 3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Em **tokens**, não caracteres: desde a Etapa 3 (commit `e5cf918`)
# `ingest_bytes`/`reingest_document` sempre passam o tokenizer da collection
# para `chunk_text`, então todo `chunk_size` que vem de uma collection é
# contado em tokens — é também o que a UI mostra (`CollectionOptionCard`).
# Os 800/100 antigos eram da época em que a contagem era por caractere e
# ficaram para trás; 512/51 é o valor da literatura e o centro da grade 5×3
# da Etapa 3. **Provisório** até a execução oficial sobre as 180 perguntas
# escolher o ponto vencedor — ver `docs/ROADMAP.md`, Fase 10.
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 51

SEPARADORES_RECURSIVOS: tuple[str, ...] = ("\n\n", "\n", ". ", " ", "")


@dataclass(frozen=True)
class _Peca:
    texto: str
    sep_antes: str = ""
    ja_com_overlap: bool = False


def _normalizar_preservando_linhas(text: str) -> str:
    """Colapsa espaços/tabs repetidos dentro de cada linha e remove linhas em
    branco consecutivas."""
    linhas = (" ".join(linha.split()) for linha in text.splitlines())
    return "\n".join(linha for linha in linhas if linha)


def _normalizar_preservando_paragrafos(text: str) -> str:
    """Normaliza espaços/tabs dentro de cada linha, preserva `\\n` entre linhas
    consecutivas do mesmo bloco e colapsa uma ou mais linhas em branco em
    `\\n\\n` (fronteira de parágrafo para o corte recursivo)."""
    paragrafos: list[str] = []
    linhas_atuais: list[str] = []
    for bruta in text.splitlines():
        limpa = " ".join(bruta.split())
        if limpa:
            linhas_atuais.append(limpa)
        elif linhas_atuais:
            paragrafos.append("\n".join(linhas_atuais))
            linhas_atuais = []
    if linhas_atuais:
        paragrafos.append("\n".join(linhas_atuais))
    return "\n\n".join(paragrafos)


def _emitir_chunk(texto: str) -> str:
    """Normaliza quebras de parágrafo internas para `\\n` na string emitida."""
    return re.sub(r"\n{2,}", "\n", texto).strip()


def contar_unidades(texto: str, tokenizer: Any = None) -> int:
    """Conta tokens (se `tokenizer` for fornecido) ou caracteres (se `None`)."""
    limpo = _emitir_chunk(texto)
    if not limpo:
        return 0
    if tokenizer is None:
        return len(limpo)
    if callable(tokenizer) and not hasattr(tokenizer, "encode"):
        return len(tokenizer(limpo))
    fast = getattr(tokenizer, "_tokenizer", None)
    if fast is not None and hasattr(fast, "encode"):
        return len(fast.encode(limpo, add_special_tokens=False).ids)
    return len(tokenizer.encode(limpo, add_special_tokens=False))


def _fatiar_duro(bloco: str, chunk_size: int, overlap: int, tokenizer: Any = None) -> list[_Peca]:
    """Fatia uma sequência sem separadores naturais em janelas de `chunk_size`
    com passo `chunk_size - overlap`."""
    limpo = _emitir_chunk(bloco)
    if not limpo:
        return []
    passo = max(1, chunk_size - overlap)

    if tokenizer is not None and hasattr(tokenizer, "encode") and hasattr(tokenizer, "decode"):
        ids = tokenizer.encode(limpo, add_special_tokens=False)
        if len(ids) <= chunk_size:
            return [_Peca(limpo, ja_com_overlap=True)]
        fatias: list[_Peca] = []
        inicio = 0
        n = len(ids)
        while inicio < n:
            fim = min(n, inicio + chunk_size)
            decodificado = tokenizer.decode(ids[inicio:fim], skip_special_tokens=True).strip()
            if decodificado:
                fatias.append(_Peca(decodificado, ja_com_overlap=True))
            if fim >= n:
                break
            inicio += passo
        return fatias

    fatias_char: list[_Peca] = []
    inicio = 0
    n = len(limpo)
    while inicio < n:
        fim = min(n, inicio + chunk_size)
        fatias_char.append(_Peca(limpo[inicio:fim], ja_com_overlap=True))
        if fim >= n:
            break
        inicio += passo
    return fatias_char


def _dividir_por_separador(bloco: str, sep: str) -> tuple[list[str], str]:
    """Divide `bloco` por `sep` e devolve `(partes, joiner_na_emissao)`."""
    if sep == "\n\n":
        return [p for p in bloco.split("\n\n") if p.strip()], "\n"
    if sep == "\n":
        return [p for p in bloco.split("\n") if p.strip()], "\n"
    if sep == ". ":
        brutas = bloco.split(". ")
        partes = [f"{p}." if i < len(brutas) - 1 else p for i, p in enumerate(brutas)]
        return [p for p in partes if p.strip()], " "
    if sep == " ":
        return [p for p in bloco.split(" ") if p.strip()], " "
    return [bloco], ""


def _decompor_recursivo(
    bloco: str,
    chunk_size: int,
    overlap: int,
    tokenizer: Any,
    separadores: tuple[str, ...],
    sep_entrada: str = "",
) -> list[_Peca]:
    """Decompõe `bloco` em peças atômicas de tamanho `<= chunk_size` seguindo
    a hierarquia `separadores`."""
    if contar_unidades(bloco, tokenizer) <= chunk_size:
        return [_Peca(_emitir_chunk(bloco), sep_antes=sep_entrada)]

    for indice, sep in enumerate(separadores):
        if sep == "":
            fatias = _fatiar_duro(bloco, chunk_size, overlap, tokenizer)
            if fatias and sep_entrada:
                fatias[0] = _Peca(
                    fatias[0].texto,
                    sep_antes=sep_entrada,
                    ja_com_overlap=fatias[0].ja_com_overlap,
                )
            return fatias
        if sep in bloco:
            partes, joiner = _dividir_por_separador(bloco, sep)
            if len(partes) <= 1:
                continue
            restantes = separadores[indice + 1 :]
            pecas: list[_Peca] = []
            for i, parte in enumerate(partes):
                sep_peca = sep_entrada if i == 0 else joiner
                if contar_unidades(parte, tokenizer) <= chunk_size:
                    pecas.append(_Peca(_emitir_chunk(parte), sep_antes=sep_peca))
                else:
                    pecas.extend(
                        _decompor_recursivo(
                            parte,
                            chunk_size,
                            overlap,
                            tokenizer,
                            restantes,
                            sep_entrada=sep_peca,
                        )
                    )
            return pecas

    return _fatiar_duro(bloco, chunk_size, overlap, tokenizer)


def _juntar_pecas(pecas: list[_Peca]) -> str:
    if not pecas:
        return ""
    partes = [pecas[0].texto]
    for peca in pecas[1:]:
        partes.append(f"{peca.sep_antes or ' '}{peca.texto}")
    return "".join(partes)


def _unidades_subnivel_para_overlap(texto: str) -> list[_Peca]:
    """Quebra a última peça de um chunk em unidades naturais finas (`\\n`,
    `. `, `" "`) para extrair um sufixo de overlap quando a peça inteira é
    maior que `overlap`."""
    for sep in ("\n", ". ", " "):
        if sep in texto:
            partes, joiner = _dividir_por_separador(texto, sep)
            if len(partes) > 1:
                return [
                    _Peca(_emitir_chunk(p), sep_antes="" if i == 0 else joiner)
                    for i, p in enumerate(partes)
                ]
    return []


def _calcular_sufixo_overlap(
    atuais: list[_Peca],
    proxima: _Peca,
    chunk_size: int,
    overlap: int,
    tokenizer: Any,
) -> list[_Peca]:
    """Escolhe o maior sufixo de `atuais` com tamanho `<= overlap` que ainda
    permita acomodar `proxima` dentro de `chunk_size`."""
    if overlap <= 0 or not atuais:
        return []

    melhor: list[_Peca] = []
    for i in range(len(atuais) - 1, -1, -1):
        candidato = atuais[i:]
        texto_cand = _juntar_pecas(candidato)
        if contar_unidades(texto_cand, tokenizer) > overlap:
            break
        if contar_unidades(_juntar_pecas([*candidato, proxima]), tokenizer) <= chunk_size:
            melhor = candidato
        else:
            break

    if melhor:
        return melhor

    # Se nem a última peça inteira coube em `overlap`, tenta decompor essa
    # última peça em frases/palavras para preservar overlap de fronteira sem
    # cortar palavras ao meio.
    subpecas = _unidades_subnivel_para_overlap(atuais[-1].texto)
    if not subpecas:
        return []
    for i in range(len(subpecas) - 1, -1, -1):
        candidato = subpecas[i:]
        texto_cand = _juntar_pecas(candidato)
        if contar_unidades(texto_cand, tokenizer) > overlap:
            break
        if contar_unidades(_juntar_pecas([*candidato, proxima]), tokenizer) <= chunk_size:
            melhor = candidato
        else:
            break
    return melhor


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
    *,
    tokenizer: Any = None,
) -> list[str]:
    """Divide `text` recursivamente (`\\n\\n` → `\\n` → `. ` → `" "` → corte
    duro) em chunks de até `chunk_size` unidades, com `overlap`.

    Quando `tokenizer` é informado, `chunk_size` e `overlap` são contados em
    **tokens** desse tokenizer; quando `tokenizer=None`, são contados em
    caracteres. Retorna lista vazia para texto vazio/só espaços.
    """
    if chunk_size <= overlap:
        raise ValueError("chunk_size deve ser maior que overlap")

    normalizado = _normalizar_preservando_paragrafos(text)
    if not normalizado:
        return []

    pecas = _decompor_recursivo(normalizado, chunk_size, overlap, tokenizer, SEPARADORES_RECURSIVOS)
    if not pecas:
        return []

    chunks: list[str] = []
    atuais: list[_Peca] = []

    for peca in pecas:
        if peca.ja_com_overlap:
            if atuais:
                chunks.append(_juntar_pecas(atuais))
                atuais = []
            chunks.append(peca.texto)
            continue

        if not atuais:
            atuais = [peca]
            continue

        candidato = _juntar_pecas([*atuais, peca])
        if contar_unidades(candidato, tokenizer) <= chunk_size:
            atuais.append(peca)
        else:
            chunks.append(_juntar_pecas(atuais))
            sufixo = _calcular_sufixo_overlap(atuais, peca, chunk_size, overlap, tokenizer)
            atuais = [*sufixo, peca]

    if atuais:
        chunks.append(_juntar_pecas(atuais))

    return [c for c in chunks if c]
