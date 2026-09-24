"""Testes do conector de leitura a BD relacional (R4).

# MVP: somente leitura, sem sincronização incremental (ver
docs/ARCHITECTURE.md §5) — cobre a transformação linha->texto isoladamente e
o fluxo leitura (reflexão de tabela via SQLAlchemy) + ingestão no RAG,
reaproveitando o mesmo `db_session` (SQLite em memória) usado pelos demais
testes de `app.rag`.
"""

from pathlib import Path

import pytest
from sqlalchemy import text

from app.rag.db_connector import read_table_as_text, row_to_text
from app.rag.ingest import ingest_bytes
from tests.conftest import _FakeQdrantRAGClient


def test_row_to_text_formata_colunas_e_ignora_valores_nulos():
    texto = row_to_text(
        {
            "nome": "Gerador Diesel GD-15",
            "descricao": "15 kVA",
            "preco": None,
            "categoria": "geradores",
        }
    )

    assert texto == "nome: Gerador Diesel GD-15\ndescricao: 15 kVA\ncategoria: geradores"


def test_row_to_text_linha_totalmente_nula_retorna_string_vazia():
    assert row_to_text({"a": None, "b": None}) == ""


async def test_read_table_as_text_le_todas_as_colunas_por_reflexao(db_session):
    """A tabela é lida via reflexão (`Table(..., autoload_with=...)`), sem
    nenhum model SQLAlchemy próprio para ela — funciona para qualquer tabela
    do banco, não só a fixture `produtos`."""
    connection = await db_session.connection()
    await connection.execute(
        text(
            "CREATE TABLE produtos_legado (id INTEGER PRIMARY KEY, nome TEXT, "
            "descricao TEXT, preco NUMERIC, categoria TEXT)"
        )
    )
    await connection.execute(
        text(
            "INSERT INTO produtos_legado (nome, descricao, preco, categoria) VALUES "
            "('Gerador Diesel GD-15', 'Potência de 15 kVA', 24900.00, 'geradores'), "
            "('Quadro QTA-100', 'Chaveamento automático', 6200.00, 'acessórios')"
        )
    )

    textos = await read_table_as_text(connection, "produtos_legado")

    assert len(textos) == 2
    assert "nome: Gerador Diesel GD-15" in textos[0]
    assert "categoria: geradores" in textos[0]
    assert "nome: Quadro QTA-100" in textos[1]


async def test_read_table_as_text_restringe_colunas_informadas(db_session):
    connection = await db_session.connection()
    await connection.execute(
        text("CREATE TABLE produtos_legado (id INTEGER PRIMARY KEY, nome TEXT, preco NUMERIC)")
    )
    await connection.execute(
        text("INSERT INTO produtos_legado (nome, preco) VALUES ('Gerador Diesel GD-15', 24900.00)")
    )

    textos = await read_table_as_text(connection, "produtos_legado", columns=["nome"])

    assert textos == ["nome: Gerador Diesel GD-15"]


async def test_read_table_as_text_coluna_invalida_levanta_value_error(db_session):
    connection = await db_session.connection()
    await connection.execute(
        text("CREATE TABLE produtos_legado (id INTEGER PRIMARY KEY, nome TEXT, preco NUMERIC)")
    )

    with pytest.raises(ValueError, match="coluna_que_nao_existe"):
        await read_table_as_text(
            connection, "produtos_legado", columns=["nome", "coluna_que_nao_existe"]
        )


async def test_read_table_as_text_tabela_vazia_retorna_lista_vazia(db_session):
    connection = await db_session.connection()
    await connection.execute(
        text("CREATE TABLE produtos_legado (id INTEGER PRIMARY KEY, nome TEXT)")
    )

    assert await read_table_as_text(connection, "produtos_legado") == []


async def test_leitura_da_tabela_e_ingestao_no_rag_criam_um_documento_por_linha(
    tmp_path: Path, db_session, active_collection, text_embedder
):
    """Fluxo leve de integração: lê a tabela fixture e ingere cada linha
    como um documento no RAG, reaproveitando `ingest_bytes` (mesma lógica de
    chunking/embedding/upsert usada por PDFs/textos e pelo endpoint de
    upload)."""
    connection = await db_session.connection()
    await connection.execute(
        text("CREATE TABLE produtos_legado (id INTEGER PRIMARY KEY, nome TEXT, descricao TEXT)")
    )
    await connection.execute(
        text(
            "INSERT INTO produtos_legado (nome, descricao) VALUES "
            "('Gerador Diesel GD-15', 'Potência de 15 kVA'), "
            "('Gerador Diesel GD-30', 'Potência de 30 kVA')"
        )
    )
    client = _FakeQdrantRAGClient()

    textos = await read_table_as_text(connection, "produtos_legado")
    documentos = [
        await ingest_bytes(
            client,
            text_embedder,
            active_collection,
            tmp_path / "uploads",
            f"produtos_row{indice}.txt",
            texto.encode("utf-8"),
            domain="vendas",
            session=db_session,
            origin="batch_script",
        )
        for indice, texto in enumerate(textos, start=1)
    ]

    assert len(documentos) == 2
    assert {documento.filename for documento in documentos} == {
        "produtos_row1.txt",
        "produtos_row2.txt",
    }
    assert all(documento.domain == "vendas" for documento in documentos)
    assert all(documento.origin == "batch_script" for documento in documentos)
    conteudos_gravados = [chunks[0] for _coll, chunks, _src, _dom, _doc_id in client.upserts]
    assert any("Gerador Diesel GD-15" in conteudo for conteudo in conteudos_gravados)
    assert any("Gerador Diesel GD-30" in conteudo for conteudo in conteudos_gravados)
