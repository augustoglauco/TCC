from app.router.rag_client import NullRAGClient


async def test_null_rag_client_always_returns_empty_list():
    client = NullRAGClient()

    result = await client.search("qualquer coisa", "vendas")

    assert result == []
