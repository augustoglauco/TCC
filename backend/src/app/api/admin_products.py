"""Endpoints administrativos para gestão de produtos e imagens associadas.

GET    /api/admin/produtos                      — lista com filtros e busca
GET    /api/admin/produtos/{id}                 — detalhe de produto
POST   /api/admin/produtos                      — cadastro manual de produto
PUT    /api/admin/produtos/{id}                 — edição parcial de produto
DELETE /api/admin/produtos/{id}                 — exclusão em cascata (Postgres e CLIP)
POST   /api/admin/produtos/{id}/imagens         — upload de imagem avulsa e vetorização no CLIP
DELETE /api/admin/produtos/{id}/imagens/{img_id}— desassociação de imagem e remoção no CLIP
"""

import logging
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_auth import require_admin
from app.api.rag_dependencies import get_db_session
from app.api.uploads import salvar_imagem_produto
from app.catalog_extractor.extractor import extract_catalog_stream
from app.config import get_settings
from app.db.catalog import (
    adicionar_desconto_volume,
    atualizar_estoque,
    atualizar_produto,
    criar_compatibilidade,
    criar_produto,
    deletar_produto,
    listar_categorias_distintas,
    listar_compatividades_do_produto,
    listar_produtos,
    obter_produto,
    remover_compatibilidade,
    remover_desconto_volume,
)
from app.db.models import ProdutoImagem
from app.models.catalog import (
    PaginatedProdutosOut,
    ProdutoCreate,
    ProdutoImagemOut,
    ProdutoOut,
    ProdutoUpdate,
)
from app.models.catalog_extractor import CatalogConfirmRequest, CatalogConfirmResponse
from app.rag.clip_embedder import ClipEmbedder
from app.rag.image_search import ClipImageStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/produtos", tags=["admin-produtos"])


def _get_clip_store(request: Request) -> ClipImageStore:
    return request.app.state.clip_image_store


def _get_clip_embedder(request: Request) -> ClipEmbedder:
    return request.app.state.clip_embedder


@router.get("", response_model=PaginatedProdutosOut)
async def get_admin_produtos(
    termo: Annotated[str | None, Query(description="Busca por nome, descrição ou specs")] = None,
    categoria: Annotated[str | None, Query(description="Filtro por categoria")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin),
):
    # MVP: paginação em memória (carrega todos os produtos do filtro e fatia).
    todos = await listar_produtos(session, categoria=categoria, termo=termo)
    total = len(todos)
    paginados = todos[offset : offset + limit]
    return PaginatedProdutosOut(
        items=[ProdutoOut.model_validate(p) for p in paginados],
        total=total,
    )


@router.get("/categorias", response_model=list[str])
async def get_admin_categorias(
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin),
):
    return await listar_categorias_distintas(session)


@router.post("/catalogo/extrair/stream")
async def post_extrair_catalogo_stream(
    request: Request,
    files: list[UploadFile] = File(...),
    provider: str = Form("local"),
    fallback_external: bool = Form(True),
    page_range: str | None = Form(None),
    _: None = Depends(require_admin),
):
    settings = get_settings()
    temp_dir = Path(settings.product_images_dir) / "temp"

    file_tuples = []
    for f in files:
        content = await f.read()
        file_tuples.append((f.filename or "arquivo", content))

    local_client = getattr(request.app.state, "local_client", None)
    vision_client = getattr(request.app.state, "external_client", None)
    session_factory = getattr(request.app.state, "db_sessionmaker", None)

    return StreamingResponse(
        extract_catalog_stream(
            files=file_tuples,
            provider=provider,
            fallback_external=fallback_external,
            temp_dir=temp_dir,
            local_client=local_client,
            vision_client=vision_client,
            page_range=page_range,
            session_factory=session_factory,
        ),
        media_type="text/event-stream",
    )


@router.post(
    "/catalogo/confirmar",
    response_model=CatalogConfirmResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_confirmar_catalogo(
    payload: CatalogConfirmRequest,
    session: AsyncSession = Depends(get_db_session),
    clip_store: ClipImageStore = Depends(_get_clip_store),
    clip_embedder: ClipEmbedder = Depends(_get_clip_embedder),
    _: None = Depends(require_admin),
):
    settings = get_settings()
    temp_dir = Path(settings.product_images_dir) / "temp"
    produtos_criados = []

    for item in payload.produtos:
        prod = await criar_produto(
            session,
            nome=item.nome,
            descricao=item.descricao,
            preco=item.preco,
            categoria=item.categoria,
            especificacoes_tecnicas=item.especificacoes_tecnicas,
            preco_base_fornecedor=item.preco_base_fornecedor,
        )

        if item.imagem_temp_url:
            img_filename = item.imagem_temp_url.split("/")[-1]
            temp_path = temp_dir / img_filename
            if temp_path.exists():
                img_bytes = temp_path.read_bytes()
                def_name = f"prod_{prod.id}_{uuid4().hex[:8]}.jpg"
                def_url, _ = salvar_imagem_produto(img_bytes, def_name, is_temp=False)
                prod.imagem_url = def_url

                clip_id = None
                try:
                    clip_id = await clip_store.upsert_image(
                        embedder=clip_embedder,
                        image_bytes=img_bytes,
                        filename=prod.nome,
                        domain="vendas",
                        produto_id=prod.id,
                        imagem_url=def_url,
                    )
                except Exception as exc:
                    logger.warning(
                        "Falha ao indexar imagem de catálogo no CLIP para produto %d: %s",
                        prod.id,
                        exc,
                    )

                nova_imagem = ProdutoImagem(
                    produto_id=prod.id,
                    imagem_url=def_url,
                    clip_image_id=clip_id,
                )
                session.add(nova_imagem)

        produtos_criados.append(prod)

    await session.commit()
    produtos_finais = []
    for p in produtos_criados:
        prod_completo = await obter_produto(session, p.id)
        if prod_completo:
            produtos_finais.append(ProdutoOut.model_validate(prod_completo))

    return CatalogConfirmResponse(
        criados=len(produtos_finais),
        produtos=produtos_finais,
    )


@router.post("/upload-temp")
async def upload_temp_imagem_catalogo(
    file: UploadFile = File(...),
    _: None = Depends(require_admin),
):
    """Permite upload avulso de imagem temporária para a conferência prévia do catálogo."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")
    rel_url, _ = salvar_imagem_produto(content, file.filename or "upload.jpg", is_temp=True)
    return {"imagem_temp_url": rel_url}


@router.get("/{produto_id}", response_model=ProdutoOut)
async def get_admin_produto(
    produto_id: int,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin),
):
    produto = await obter_produto(session, produto_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return ProdutoOut.model_validate(produto)


@router.post("", response_model=ProdutoOut, status_code=status.HTTP_201_CREATED)
async def post_admin_produto(
    payload: ProdutoCreate,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin),
):
    produto = await criar_produto(
        session,
        nome=payload.nome,
        descricao=payload.descricao,
        preco=payload.preco,
        categoria=payload.categoria,
        especificacoes_tecnicas=payload.especificacoes_tecnicas,
        dimensoes_cm=payload.dimensoes_cm,
        peso_kg=payload.peso_kg,
        preco_promocional=payload.preco_promocional,
        promocao_valida_ate=payload.promocao_valida_ate,
        preco_base_fornecedor=payload.preco_base_fornecedor,
        imagem_url=payload.imagem_url,
    )
    return ProdutoOut.model_validate(produto)


@router.put("/{produto_id}", response_model=ProdutoOut)
async def put_admin_produto(
    produto_id: int,
    payload: ProdutoUpdate,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin),
):
    updates = payload.model_dump(exclude_unset=True)
    produto = await atualizar_produto(session, produto_id, updates)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return ProdutoOut.model_validate(produto)


@router.delete("/{produto_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_admin_produto(
    produto_id: int,
    session: AsyncSession = Depends(get_db_session),
    clip_store: ClipImageStore = Depends(_get_clip_store),
    _: None = Depends(require_admin),
):
    produto = await obter_produto(session, produto_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    # Remove vetores do CLIP para todas as imagens associadas por produto_id
    try:
        await clip_store.delete_images_by_product_id(produto_id)
    except Exception as exc:
        logger.warning(
            "Falha ao expurgar vetores CLIP do produto %s por produto_id: %s", produto_id, exc
        )

    for img in produto.imagens:
        if img.clip_image_id:
            try:
                await clip_store.delete_image(img.clip_image_id)
            except Exception as exc:
                logger.warning("Falha ao expurgar vetor CLIP %s: %s", img.clip_image_id, exc)
        if img.imagem_url:
            try:
                await clip_store.delete_images_by_url(img.imagem_url)
            except Exception as exc:
                logger.warning("Falha ao expurgar vetor CLIP por URL %s: %s", img.imagem_url, exc)

    await deletar_produto(session, produto_id)
    return None


@router.post(
    "/{produto_id}/imagens", response_model=ProdutoImagemOut, status_code=status.HTTP_201_CREATED
)
async def upload_imagem_produto(
    produto_id: int,
    file: UploadFile = File(...),
    is_principal: bool = Form(True),
    session: AsyncSession = Depends(get_db_session),
    clip_store: ClipImageStore = Depends(_get_clip_store),
    clip_embedder: ClipEmbedder = Depends(_get_clip_embedder),
    _: None = Depends(require_admin),
):
    produto = await obter_produto(session, produto_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")

    rel_url, _ = salvar_imagem_produto(content, file.filename or "imagem.png")

    # Gera vetor visual no CLIP
    clip_image_id = None
    try:
        clip_image_id = await clip_store.upsert_image(
            embedder=clip_embedder,
            image_bytes=content,
            filename=produto.nome,
            domain="vendas",
            produto_id=produto.id,
            imagem_url=rel_url,
        )
    except Exception as exc:
        logger.warning("Falha ao gerar embedding CLIP para produto %s: %s", produto_id, exc)

    nova_imagem = ProdutoImagem(
        produto_id=produto.id,
        imagem_url=rel_url,
        clip_image_id=clip_image_id,
        is_principal=is_principal,
    )
    session.add(nova_imagem)
    if is_principal:
        produto.imagem_url = rel_url
    await session.commit()
    await session.refresh(nova_imagem)
    return ProdutoImagemOut.model_validate(nova_imagem)


@router.delete("/{produto_id}/imagens/{img_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_imagem_produto(
    produto_id: int,
    img_id: int,
    session: AsyncSession = Depends(get_db_session),
    clip_store: ClipImageStore = Depends(_get_clip_store),
    _: None = Depends(require_admin),
):
    stmt = select(ProdutoImagem).where(
        ProdutoImagem.id == img_id, ProdutoImagem.produto_id == produto_id
    )
    result = await session.execute(stmt)
    imagem = result.scalar_one_or_none()
    if not imagem:
        raise HTTPException(status_code=404, detail="Imagem não encontrada.")

    if imagem.clip_image_id:
        try:
            await clip_store.delete_image(imagem.clip_image_id)
        except Exception as exc:
            logger.warning("Falha ao expurgar vetor CLIP %s: %s", imagem.clip_image_id, exc)

    if imagem.imagem_url:
        try:
            await clip_store.delete_images_by_url(imagem.imagem_url)
        except Exception as exc:
            logger.warning("Falha ao expurgar vetor CLIP por URL %s: %s", imagem.imagem_url, exc)

    await session.execute(delete(ProdutoImagem).where(ProdutoImagem.id == img_id))

    # Se era a imagem principal, atualiza produto.imagem_url
    produto = await obter_produto(session, produto_id)
    if produto and produto.imagem_url == imagem.imagem_url:
        # Pega outra imagem se houver
        outro_stmt = (
            select(ProdutoImagem)
            .where(ProdutoImagem.produto_id == produto_id, ProdutoImagem.id != img_id)
            .limit(1)
        )
        outro_res = await session.execute(outro_stmt)
        outra_img = outro_res.scalar_one_or_none()
        produto.imagem_url = outra_img.imagem_url if outra_img else None

    await session.commit()
    return None


class EstoqueUpdatePayload(BaseModel):
    centro_distribuicao: str
    quantidade: int


class DescontoVolumePayload(BaseModel):
    quantidade_minima: int
    percentual_desconto: float


class CompatibilidadePayload(BaseModel):
    compativel_com_id: int


@router.post("/{produto_id}/estoque", response_model=ProdutoOut)
async def post_atualizar_estoque(
    produto_id: int,
    payload: EstoqueUpdatePayload,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin),
):
    prod = await obter_produto(session, produto_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    await atualizar_estoque(session, produto_id, payload.centro_distribuicao, payload.quantidade)
    session.expire_all()
    prod_atualizado = await obter_produto(session, produto_id)
    return ProdutoOut.model_validate(prod_atualizado)


@router.post("/{produto_id}/descontos-volume", response_model=ProdutoOut)
async def post_adicionar_desconto_volume(
    produto_id: int,
    payload: DescontoVolumePayload,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin),
):
    prod = await obter_produto(session, produto_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    from decimal import Decimal

    await adicionar_desconto_volume(
        session, produto_id, payload.quantidade_minima, Decimal(str(payload.percentual_desconto))
    )
    session.expire_all()
    prod_atualizado = await obter_produto(session, produto_id)
    return ProdutoOut.model_validate(prod_atualizado)


@router.delete("/{produto_id}/descontos-volume/{desconto_id}", response_model=ProdutoOut)
async def delete_desconto_volume(
    produto_id: int,
    desconto_id: str,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin),
):
    from uuid import UUID

    try:
        uid = UUID(desconto_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de desconto inválido.") from None
    prod = await obter_produto(session, produto_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    await remover_desconto_volume(session, produto_id, uid)
    session.expire_all()
    prod_atualizado = await obter_produto(session, produto_id)
    return ProdutoOut.model_validate(prod_atualizado)


@router.get("/{produto_id}/compatibilidades")
async def get_compatividades_produto(
    produto_id: int,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin),
):
    prod = await obter_produto(session, produto_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return await listar_compatividades_do_produto(session, produto_id)


@router.post("/{produto_id}/compatibilidades")
async def post_criar_compatividade(
    produto_id: int,
    payload: CompatibilidadePayload,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin),
):
    prod = await obter_produto(session, produto_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    outro = await obter_produto(session, payload.compativel_com_id)
    if not outro:
        raise HTTPException(status_code=404, detail="Produto compatível não encontrado.")
    await criar_compatibilidade(session, produto_id, payload.compativel_com_id)
    return await listar_compatividades_do_produto(session, produto_id)


@router.delete("/{produto_id}/compatibilidades/{compativel_com_id}")
async def delete_compatividade(
    produto_id: int,
    compativel_com_id: int,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin),
):
    prod = await obter_produto(session, produto_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    await remover_compatibilidade(session, produto_id, compativel_com_id)
    return await listar_compatividades_do_produto(session, produto_id)
