import asyncio
import uuid

from app.rag.crawler_pending import (
    delete_pending_page,
    get_pending_page,
    list_pending_pages,
    upsert_pending_page,
)


async def test_upsert_pending_page_cria_nova_linha(db_session):
    page = await upsert_pending_page(
        db_session,
        url="https://exemplo.com/produtos",
        extracted_text="conteúdo da página",
        domain_proposed="vendas",
        confidence=0.4,
    )

    assert page.url == "https://exemplo.com/produtos"
    assert page.domain_proposed == "vendas"
    assert page.confidence == 0.4


async def test_upsert_pending_page_atualiza_existente_mesma_url(db_session):
    original = await upsert_pending_page(
        db_session,
        url="https://exemplo.com/produtos",
        extracted_text="texto v1",
        domain_proposed="vendas",
        confidence=0.4,
    )

    atualizada = await upsert_pending_page(
        db_session,
        url="https://exemplo.com/produtos",
        extracted_text="texto v2",
        domain_proposed="suporte",
        confidence=0.5,
    )

    assert atualizada.id == original.id
    assert atualizada.extracted_text == "texto v2"
    assert atualizada.domain_proposed == "suporte"
    todas = await list_pending_pages(db_session)
    assert len(todas) == 1


async def test_list_pending_pages_ordenado_mais_recente_primeiro(db_session):
    await upsert_pending_page(
        db_session,
        url="https://exemplo.com/a",
        extracted_text="a",
        domain_proposed="vendas",
        confidence=0.1,
    )
    await asyncio.sleep(1.1)  # Ensure different SQLite second precision
    await upsert_pending_page(
        db_session,
        url="https://exemplo.com/b",
        extracted_text="b",
        domain_proposed="vendas",
        confidence=0.1,
    )

    paginas = await list_pending_pages(db_session)

    assert [p.url for p in paginas] == ["https://exemplo.com/b", "https://exemplo.com/a"]


async def test_get_pending_page_inexistente_retorna_none(db_session):
    assert await get_pending_page(db_session, uuid.uuid4()) is None


async def test_delete_pending_page_remove_e_retorna_true(db_session):
    page = await upsert_pending_page(
        db_session,
        url="https://exemplo.com/a",
        extracted_text="a",
        domain_proposed="vendas",
        confidence=0.1,
    )

    removida = await delete_pending_page(db_session, page.id)

    assert removida is True
    assert await get_pending_page(db_session, page.id) is None


async def test_delete_pending_page_inexistente_retorna_false(db_session):
    assert await delete_pending_page(db_session, uuid.uuid4()) is False
