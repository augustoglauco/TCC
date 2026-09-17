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
