import pytest

from app.rag.chunking import chunk_text, contar_unidades


def test_texto_vazio_retorna_lista_vazia():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_texto_menor_que_chunk_size_vira_um_unico_chunk():
    chunks = chunk_text("um texto curto", chunk_size=100, overlap=10)

    assert chunks == ["um texto curto"]


def test_texto_maior_que_chunk_size_e_dividido_em_varios_chunks_com_overlap():
    texto = "a" * 250
    chunks = chunk_text(texto, chunk_size=100, overlap=20)

    assert len(chunks) == 3
    # Overlap: o fim de um chunk se repete no início do próximo.
    assert chunks[0][-20:] == chunks[1][:20]
    assert chunks[1][-20:] == chunks[2][:20]
    # Nenhum caractere original é perdido.
    assert "".join(chunks[0]) + chunks[1][20:] + chunks[2][20:] == texto


def test_espacos_dentro_da_linha_sao_normalizados_mas_quebra_de_linha_e_preservada():
    chunks = chunk_text("linha um\n\n  linha   dois \t linha três", chunk_size=100, overlap=10)

    # Espaços/tabs repetidos dentro de uma linha viram um único espaço, e
    # linhas vazias somem — mas a quebra de linha ENTRE "linha um" e "linha
    # dois" é preservada (não vira mais um espaço): sem isso, o corte por
    # tamanho fixo pode misturar o fim de uma linha de tabela/bullet com o
    # começo da próxima (ver docstring do módulo).
    assert chunks == ["linha um\nlinha dois linha três"]


def test_corte_prefere_quebra_de_linha_e_nao_trava_em_passos_de_1_caractere():
    # Duas linhas de 90 chars cada: sem preferência por quebra de linha, o
    # corte em 100 caracteres misturaria os 10 primeiros "B" no chunk da
    # linha 1. Também é um caso adversarial pro bug corrigido: overlap
    # grande o bastante pra mesma quebra de linha reaparecer em janelas
    # consecutivas, se o próximo `start` for calculado a partir do corte
    # ajustado (errado) em vez do corte de tamanho fixo original (correto)
    # — o que travaria o avanço em passos de 1 caractere.
    linha1 = "A" * 90
    linha2 = "B" * 90
    texto = f"{linha1}\n{linha2}"

    chunks = chunk_text(texto, chunk_size=100, overlap=20)

    assert chunks[0] == linha1
    assert not chunks[0].endswith("B")
    assert len(chunks) < 10  # nunca deveria degenerar em dezenas de chunks
    # Nenhum caractere original é perdido (overlap pode duplicar, nunca
    # perder — por isso ">=", não "==").
    assert "".join(chunks).replace("\n", "").count("A") >= 90
    assert "".join(chunks).replace("\n", "").count("B") >= 90


def test_chunk_size_menor_ou_igual_a_overlap_levanta_erro():
    with pytest.raises(ValueError):
        chunk_text("qualquer texto", chunk_size=10, overlap=10)


def test_corte_recursivo_prefere_paragrafo_antes_de_quebra_de_linha():
    """Hierarquia recursiva (`\\n\\n` → `\\n` → `. ` → ` `): se cabe cortar na
    fronteira de parágrafo (`\\n\\n`), não deve invadir a primeira linha do
    parágrafo seguinte só porque ela ainda caberia na janela."""
    p1 = "Linha 1A\nLinha 1B"
    p2 = "Linha 2A\nLinha 2B"
    texto = f"{p1}\n\n{p2}"

    chunks = chunk_text(texto, chunk_size=28, overlap=4)

    assert chunks[0] == p1
    assert "Linha 2A" not in chunks[0]
    assert "Linha 2A" in chunks[1]
    assert "Linha 2B" in chunks[1]


def test_corte_recursivo_prefere_fim_de_frase_antes_de_espaco():
    """Quando uma linha única excede `chunk_size`, o corte deve preferir `. `
    (preservando o ponto final na frase) em vez de cortar no meio da frase
    seguinte em um espaço."""
    texto = "Primeira frase curta. Segunda frase curta. Terceira frase longa."

    chunks = chunk_text(texto, chunk_size=48, overlap=6)

    assert chunks[0] == "Primeira frase curta. Segunda frase curta."
    assert chunks[1].endswith("Terceira frase longa.")


def test_corte_recursivo_prefere_espaco_antes_de_partir_palavra():
    """Sem `\\n\\n`, `\\n` nem `. `, corta no espaço entre palavras em vez de
    partir uma palavra ao meio."""
    texto = "controlador biometrico facial integrado"

    chunks = chunk_text(texto, chunk_size=25, overlap=5)

    assert chunks[0] == "controlador biometrico"
    assert all(
        palavra in " ".join(chunks).split()
        for palavra in ("controlador", "biometrico", "facial", "integrado")
    )


class _TokenizerPorPalavra:
    """Dublê de tokenizer estilo HuggingFace onde cada palavra equivale a 1 token."""

    def encode(self, text: str, add_special_tokens: bool = False) -> list[int]:
        assert add_special_tokens is False
        palavras = text.split()
        self._vocab = {i: p for i, p in enumerate(palavras)}
        return list(range(len(palavras)))


def test_chunk_text_conta_tokens_pelo_tokenizer_e_respeita_overlap():
    """Etapa 3 (`docs/ARCHITECTURE.md` / `docs/EVALUATION.md` Seção 2.1):
    quando `tokenizer` é passado, `chunk_size` e `overlap` são medidos em
    tokens (não em caracteres)."""
    # 6 frases de 3 palavras (tokens) cada = 18 tokens (~130 caracteres).
    # Com chunk_size=6 tokens e overlap=3 tokens:
    # - chunk 0: frases 1 e 2 (6 tokens)
    # - chunk 1: frase 2 (overlap de 3 tokens) + frase 3 (total 6 tokens)
    frases = [f"frase numero {i}." for i in range(1, 7)]
    texto = " ".join(frases)
    tokenizer = _TokenizerPorPalavra()

    chunks = chunk_text(texto, chunk_size=6, overlap=3, tokenizer=tokenizer)

    assert len(chunks) >= 4
    for c in chunks:
        assert len(tokenizer.encode(c, add_special_tokens=False)) <= 6
    # A segunda frase ("frase numero 2.") aparece no fim do primeiro chunk e
    # no início do segundo por causa do overlap de 3 tokens.
    assert chunks[0].endswith("frase numero 2.")
    assert chunks[1].startswith("frase numero 2.")


class _TokenizerCaractereIds:
    """Dublê de tokenizer com `.encode` e `.decode` (para testar fatia dura por
    IDs de token quando uma sequência sem separadores excede `chunk_size`)."""

    def encode(self, text: str, add_special_tokens: bool = False) -> list[int]:
        assert add_special_tokens is False
        return [ord(ch) for ch in text]

    def decode(self, ids: list[int], skip_special_tokens: bool = True) -> str:
        assert skip_special_tokens is True
        return "".join(chr(i) for i in ids)


def test_chunk_text_com_tokenizer_fatia_sequencia_sem_separador_por_tokens():
    texto = "x" * 25
    tokenizer = _TokenizerCaractereIds()

    chunks = chunk_text(texto, chunk_size=10, overlap=2, tokenizer=tokenizer)

    assert chunks == ["x" * 10, "x" * 10, "x" * 9]


class _BackendRapidoComTruncacao:
    """Imita `tokenizers.Tokenizer` do MiniLM: `encode` trunca em 128 tokens."""

    truncation = {"max_length": 128}

    def encode(self, texto, add_special_tokens=False):
        ids = list(range(len(texto.split())))[:128]
        return type("Enc", (), {"ids": ids})()


class _TokenizerMiniLM:
    """Wrapper HF: `_tokenizer` com truncação ativa; o `encode` do wrapper não trunca."""

    _tokenizer = _BackendRapidoComTruncacao()

    def encode(self, texto, add_special_tokens=False):
        return list(range(len(texto.split())))


def test_contagem_de_tokens_nao_e_truncada_pela_truncacao_do_tokenizer():
    texto = " ".join(f"w{i}" for i in range(1000))
    assert contar_unidades(texto, _TokenizerMiniLM()) == 1000
    chunks = chunk_text(texto, chunk_size=200, overlap=25, tokenizer=_TokenizerMiniLM())
    assert len(chunks) > 4
