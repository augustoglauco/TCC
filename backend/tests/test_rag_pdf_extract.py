from app.rag.pdf_extract import extract_text_from_pdf


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


def test_extrai_texto_de_pdf_a_partir_de_bytes():
    pdf_bytes = _build_minimal_pdf("Ola RAG")

    texto = extract_text_from_pdf(pdf_bytes)

    assert "Ola RAG" in texto


def test_extrai_texto_de_pdf_a_partir_de_caminho(tmp_path):
    pdf_path = tmp_path / "documento.pdf"
    pdf_path.write_bytes(_build_minimal_pdf("Conteudo em arquivo"))

    texto = extract_text_from_pdf(pdf_path)

    assert "Conteudo em arquivo" in texto
