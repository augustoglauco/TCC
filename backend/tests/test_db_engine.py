from sqlalchemy import select

from app.db.models import RagDocument


async def test_db_session_permite_inserir_e_consultar_rag_document(db_session):
    db_session.add(
        RagDocument(
            filename="a.txt",
            domain="vendas",
            chunk_count=1,
            embedding_model="modelo-teste",
            chunk_size=800,
            chunk_overlap=100,
            origin="upload",
        )
    )
    await db_session.commit()

    result = await db_session.execute(select(RagDocument))
    rows = result.scalars().all()

    assert len(rows) == 1
    assert rows[0].filename == "a.txt"
    assert rows[0].id is not None
    assert rows[0].created_at is not None
