import pytest

from app.rag.chunking import chunk_text


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


def test_espacos_e_quebras_de_linha_sao_normalizados():
    chunks = chunk_text("linha um\n\n  linha   dois \t linha três", chunk_size=100, overlap=10)

    assert chunks == ["linha um linha dois linha três"]


def test_chunk_size_menor_ou_igual_a_overlap_levanta_erro():
    with pytest.raises(ValueError):
        chunk_text("qualquer texto", chunk_size=10, overlap=10)
