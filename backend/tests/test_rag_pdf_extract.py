import pytest
from fpdf import FPDF

from app.rag.pdf_extract import PdfExtractionError, extract_text_from_pdf


def _build_minimal_pdf(text: str) -> bytes:
    """Monta um PDF de uma página válido, só com o texto dado — sem depender
    de nenhuma lib de geração de PDF (não é dependência de produção)."""
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/Resources<</Font<</F1 4 0 R>>>>"
        b"/MediaBox[0 0 200 200]/Contents 5 0 R>>",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    stream = f"BT /F1 24 Tf 10 100 Td ({text}) Tj ET".encode()
    objects.append(
        b"<</Length " + str(len(stream)).encode() + b">>\nstream\n" + stream + b"\nendstream"
    )

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj".encode() + b"\n" + obj + b"\nendobj\n"

    xref_start = len(out)
    n = len(objects) + 1
    out += f"xref\n0 {n}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += b"trailer<</Size " + str(n).encode() + b"/Root 1 0 R>>\nstartxref\n"
    out += str(xref_start).encode() + b"\n%%EOF"
    return bytes(out)


def _build_two_column_pdf() -> bytes:
    """PDF A4 com duas colunas lado a lado (esquerda ~15-90mm, corredor
    vazio ~90-120mm, direita ~120-195mm) — simula um catálogo com dois
    produtos lado a lado, cada um com título + bullets em várias linhas."""
    pdf = FPDF(format="A4")
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)

    coluna_esquerda = ["PRODUTO A", "bullet a1", "bullet a2", "bullet a3"]
    coluna_direita = ["PRODUTO B", "bullet b1", "bullet b2", "bullet b3"]

    y = 20
    for linha in coluna_esquerda:
        pdf.set_xy(15, y)
        pdf.cell(w=70, h=8, text=linha)
        y += 8

    y = 20
    for linha in coluna_direita:
        pdf.set_xy(120, y)
        pdf.cell(w=70, h=8, text=linha)
        y += 8

    return bytes(pdf.output())


def _build_single_column_pdf() -> bytes:
    """PDF A4 com um único parágrafo largo (quase toda a largura da
    página) — simula uma página de texto corrido comum (manual/relatório),
    sem nenhum corredor vertical vazio."""
    pdf = FPDF(format="A4")
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    pdf.set_xy(15, 20)
    pdf.multi_cell(
        w=180,
        h=8,
        text=(
            "Este e um paragrafo de texto corrido que ocupa quase toda a "
            "largura da pagina, sem nenhuma divisao em colunas, tipico de "
            "um manual de instrucoes ou relatorio tecnico comum."
        ),
    )
    return bytes(pdf.output())


def test_extrai_texto_de_pdf_a_partir_de_bytes():
    pdf_bytes = _build_minimal_pdf("Ola RAG")

    texto = extract_text_from_pdf(pdf_bytes)

    assert "Ola RAG" in texto


def test_extrai_texto_de_pdf_a_partir_de_caminho(tmp_path):
    pdf_path = tmp_path / "documento.pdf"
    pdf_path.write_bytes(_build_minimal_pdf("Conteudo em arquivo"))

    texto = extract_text_from_pdf(pdf_path)

    assert "Conteudo em arquivo" in texto


def test_pdf_de_duas_colunas_nao_mistura_os_produtos():
    texto = extract_text_from_pdf(_build_two_column_pdf())

    # A coluna esquerda (PRODUTO A) precisa aparecer inteira antes de
    # qualquer linha da coluna direita (PRODUTO B) — sem entrelaçamento.
    pos_a = texto.index("PRODUTO A")
    pos_ultimo_bullet_a = texto.index("bullet a3")
    pos_b = texto.index("PRODUTO B")

    assert pos_a < pos_ultimo_bullet_a < pos_b
    # Nenhum bullet da coluna B aparece entre o título e o último bullet de A.
    trecho_coluna_a = texto[pos_a:pos_ultimo_bullet_a]
    assert "bullet b" not in trecho_coluna_a


def test_pdf_de_coluna_unica_nao_e_dividido_ao_meio():
    texto = extract_text_from_pdf(_build_single_column_pdf())

    # O parágrafo sai inteiro e legível, sem quebras artificiais no meio de
    # palavras (o que aconteceria se a heurística de coluna dividisse essa
    # página ao meio por engano).
    assert "paragrafo de texto corrido" in texto
    assert "manual de instrucoes" in texto


def test_pdf_invalido_levanta_pdf_extraction_error():
    with pytest.raises(PdfExtractionError):
        extract_text_from_pdf(b"isto nao e um pdf valido")
