"""Conector de leitura a um banco de dados relacional para o RAG (R4).

# MVP: somente leitura, sem sincronização incremental (ver
docs/ARCHITECTURE.md §5) — lê uma tabela sob demanda (via
`backend/scripts/ingest_db_table.py`), sem escrever no banco de origem nem
observar mudanças; reingerir a mesma tabela significa rodar o script de novo,
o que duplica registros/pontos no Qdrant (mesma limitação já aceita em
`app.rag.ingest`/`app.rag.qdrant_client.upsert_chunks`).

Reaproveita o mesmo Postgres já provisionado para a aplicação
(`docker-compose.yml`, `POSTGRES_DSN`) — decisão registrada em
`docs/ARCHITECTURE.md` §5 de não introduzir infraestrutura nova só para este
conector. A tabela fixture de exemplo é `produtos`
(`backend/migrations/versions/0003_produtos_fixture.py`), mas a leitura aqui
é genérica via reflexão de tabela do SQLAlchemy (`Table(..., autoload_with=
...)`) — funciona para qualquer tabela do banco, informando seu nome (e,
opcionalmente, um subconjunto de colunas), não só `produtos`.
"""

from sqlalchemy import MetaData, Table, select
from sqlalchemy.ext.asyncio import AsyncConnection


def row_to_text(row: dict[str, object]) -> str:
    """Transforma uma linha (dict coluna -> valor) em texto plano, pronto
    para chunking/embeddings — uma linha `coluna: valor` por par, ignorando
    colunas nulas."""
    linhas = [f"{coluna}: {valor}" for coluna, valor in row.items() if valor is not None]
    return "\n".join(linhas)


async def read_table_as_text(
    connection: AsyncConnection,
    table_name: str,
    columns: list[str] | None = None,
) -> list[str]:
    """Lê todas as linhas de `table_name` e devolve uma lista de textos (um
    por linha, via `row_to_text`).

    A tabela é lida por reflexão (`Table(..., autoload_with=...)`), não por
    um model SQLAlchemy fixo — o conector não fica acoplado a uma única
    tabela do sistema. `columns`, se informado, restringe as colunas lidas.
    """
    metadata = MetaData()
    table = await connection.run_sync(
        lambda sync_conn: Table(table_name, metadata, autoload_with=sync_conn)
    )
    colunas_selecionadas = (
        [table.c[nome] for nome in columns] if columns is not None else list(table.c)
    )
    result = await connection.execute(select(*colunas_selecionadas))
    return [row_to_text(dict(row._mapping)) for row in result]
