from pathlib import Path

from app.rag.ingest import ingest_directory, ingest_file
from tests.test_rag_pdf_extract import _build_minimal_pdf


class _FakeQdrantRAGClient:
    """Dublê de `QdrantRAGClient` — só registra o que seria gravado no Qdrant.

    Evita depender de uma instância real do Qdrant para testar a lógica de
    leitura de arquivo/chunking/inferência de domínio do pipeline de
    ingestão em si (ver docs/CONVENTIONS.md, cobertura de RAG).
    """

    def __init__(self) -> None:
        self.upserts: list[tuple[list[str], str, str]] = []

    async def upsert_chunks(self, chunks: list[str], source: str, domain: str) -> int:
        self.upserts.append((chunks, source, domain))
        return len(chunks)


async def test_ingest_file_le_txt_faz_chunking_e_grava_com_domain_informado(tmp_path: Path):
    arquivo = tmp_path / "catalogo.txt"
    arquivo.write_text("Conteúdo de exemplo sobre o catálogo de produtos.", encoding="utf-8")
    client = _FakeQdrantRAGClient()

    total = await ingest_file(client, arquivo, domain="vendas")

    assert total == 1
    chunks, source, domain = client.upserts[0]
    assert source == "catalogo.txt"
    assert domain == "vendas"
    assert "catálogo de produtos" in chunks[0]


async def test_ingest_file_extrai_texto_de_pdf(tmp_path: Path):
    arquivo = tmp_path / "manual.pdf"
    arquivo.write_bytes(_build_minimal_pdf("Texto do manual em PDF"))
    client = _FakeQdrantRAGClient()

    total = await ingest_file(client, arquivo, domain="suporte")

    assert total == 1
    chunks, _source, _domain = client.upserts[0]
    assert "Texto do manual em PDF" in chunks[0]


async def test_ingest_directory_infere_domain_do_subdiretorio_e_ignora_extensao_nao_suportada(
    tmp_path: Path,
):
    (tmp_path / "vendas").mkdir()
    (tmp_path / "vendas" / "catalogo.txt").write_text("catálogo de vendas", encoding="utf-8")
    (tmp_path / "suporte").mkdir()
    (tmp_path / "suporte" / "manual.txt").write_text("manual de suporte técnico", encoding="utf-8")
    (tmp_path / "suporte" / "planilha.csv").write_text("nao,deveria,entrar", encoding="utf-8")
    client = _FakeQdrantRAGClient()

    total = await ingest_directory(client, tmp_path)

    assert total == 2
    domains_ingeridos = {domain for _chunks, _source, domain in client.upserts}
    assert domains_ingeridos == {"vendas", "suporte"}


async def test_ingest_directory_sem_arquivos_suportados_retorna_zero(tmp_path: Path):
    (tmp_path / "vendas").mkdir()
    (tmp_path / "vendas" / "planilha.csv").write_text("nao,suportado", encoding="utf-8")
    client = _FakeQdrantRAGClient()

    total = await ingest_directory(client, tmp_path)

    assert total == 0
    assert client.upserts == []
