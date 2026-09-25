import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.catalog import criar_produto, obter_produto, deletar_produto
from app.db.models import ProdutoImagem

@pytest.mark.asyncio
async def test_criar_produto_com_preco_fornecedor_e_imagem(db_session: AsyncSession):
    produto = await criar_produto(
        db_session,
        nome="Câmera IP Teste",
        descricao="Câmera para testes",
        preco=Decimal("299.90"),
        categoria="CFTV",
        preco_base_fornecedor=Decimal("180.00"),
        imagem_url="/api/uploads/produtos/camera.png",
    )
    assert produto.id is not None
    assert produto.preco_base_fornecedor == Decimal("180.00")
    assert produto.imagem_url == "/api/uploads/produtos/camera.png"

    produto_id = produto.id
    # Adiciona imagem filha em produto_imagens
    img = ProdutoImagem(
        produto_id=produto_id,
        imagem_url="/api/uploads/produtos/camera.png",
        clip_image_id="clip-uuid-123",
        is_principal=True,
    )
    db_session.add(img)
    await db_session.commit()
    db_session.expire_all()

    consultado = await obter_produto(db_session, produto_id)
    assert consultado is not None
    assert len(consultado.imagens) == 1
    assert consultado.imagens[0].clip_image_id == "clip-uuid-123"

    # Deletar produto deve deletar imagens em cascata
    deleted = await deletar_produto(db_session, produto_id)
    assert deleted is True
    assert await obter_produto(db_session, produto_id) is None
