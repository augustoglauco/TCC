"""Backend único de dados de catálogo/estoque/preços (R12, Fase 5).

Camada de acesso a dados sobre `Produto`/`ProdutoEstoque`/
`ProdutoDescontoVolume` (`app.db.models`) — reaproveitada tanto pelo RAG
(R4, via leitura genérica em `app.rag.db_connector`, que continua
funcionando sem mudanças por ser baseada em reflexão de tabela) quanto pelo
futuro servidor MCP B2B (recursos de leitura + ferramentas transacionais,
itens seguintes desta mesma fase — ver `docs/ARCHITECTURE.md` §6). Só a
camada de dados e CRUD básico nesta etapa: nenhuma ferramenta MCP é exposta
aqui ainda.

Mesmo padrão de funções livres recebendo `AsyncSession` já usado em
`app.router.tone_monitor` (`criar_escalonamento`/`listar_escalonamentos`),
em vez de um repositório em classe — mais simples de testar isoladamente
(`docs/CONVENTIONS.md`).

# MVP: sem tratamento de concorrência em reservas/pedidos nem trilha de
auditoria — evolução futura explícita registrada em `docs/ARCHITECTURE.md`
§6 ("Governança e segurança"), não antecipada aqui. `atualizar_estoque` faz
um simples upsert (ler, depois escrever) sem lock otimista/pessimista; sob
concorrência real duas escritas simultâneas podem se sobrepor — aceitável
neste protótipo porque a ferramenta de reserva/pedido que de fato disputaria
esse recurso ainda não existe (item futuro desta fase).
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Produto, ProdutoDescontoVolume, ProdutoEstoque


def _produto_query():
    return select(Produto).options(
        selectinload(Produto.estoques), selectinload(Produto.descontos_volume)
    )


async def criar_produto(
    session: AsyncSession,
    *,
    nome: str,
    descricao: str,
    preco: Decimal,
    categoria: str,
    especificacoes_tecnicas: str | None = None,
    dimensoes_cm: str | None = None,
    peso_kg: Decimal | None = None,
    preco_promocional: Decimal | None = None,
    promocao_valida_ate: datetime | None = None,
) -> Produto:
    produto = Produto(
        nome=nome,
        descricao=descricao,
        preco=preco,
        categoria=categoria,
        especificacoes_tecnicas=especificacoes_tecnicas,
        dimensoes_cm=dimensoes_cm,
        peso_kg=peso_kg,
        preco_promocional=preco_promocional,
        promocao_valida_ate=promocao_valida_ate,
    )
    session.add(produto)
    await session.commit()
    await session.refresh(produto, attribute_names=["estoques", "descontos_volume"])
    return produto


async def obter_produto(session: AsyncSession, produto_id: int) -> Produto | None:
    result = await session.execute(_produto_query().where(Produto.id == produto_id))
    return result.scalars().first()


async def listar_produtos(session: AsyncSession, categoria: str | None = None) -> list[Produto]:
    query = _produto_query().order_by(Produto.id)
    if categoria is not None:
        query = query.where(Produto.categoria == categoria)
    result = await session.execute(query)
    return list(result.scalars().unique().all())


async def atualizar_produto(
    session: AsyncSession, produto_id: int, updates: dict[str, object]
) -> Produto | None:
    """Atualização parcial — só os campos presentes em `updates` são
    alterados (inclusive para `None`, ex.: limpar `preco_promocional`).
    Espera-se que o chamador monte `updates` com
    `ProdutoUpdate.model_dump(exclude_unset=True)` (mesmo padrão de
    `PUT /api/admin/runtime-settings`, ver `app.api.runtime_settings`), para
    distinguir "campo não enviado" de "campo enviado como null". Devolve
    `None` se o produto não existe.
    """
    produto = await obter_produto(session, produto_id)
    if produto is None:
        return None
    for campo, valor in updates.items():
        setattr(produto, campo, valor)
    await session.commit()
    await session.refresh(produto, attribute_names=["estoques", "descontos_volume"])
    return produto


async def deletar_produto(session: AsyncSession, produto_id: int) -> bool:
    """Remove o produto e os registros filhos (estoque/descontos). Os filhos
    são apagados por `DELETE` explícito em vez de depender só do
    `cascade="all, delete-orphan"` do relationship — mais robusto contra o
    caso de a coleção `produto.estoques`/`descontos_volume` não estar
    carregada na identity map da sessão no momento da exclusão."""
    produto = await obter_produto(session, produto_id)
    if produto is None:
        return False
    await session.execute(delete(ProdutoEstoque).where(ProdutoEstoque.produto_id == produto_id))
    await session.execute(
        delete(ProdutoDescontoVolume).where(ProdutoDescontoVolume.produto_id == produto_id)
    )
    await session.delete(produto)
    await session.commit()
    return True


async def atualizar_estoque(
    session: AsyncSession,
    produto_id: int,
    centro_distribuicao: str,
    quantidade: int,
) -> ProdutoEstoque:
    """Upsert da quantidade em estoque de `produto_id` no centro de
    distribuição informado — cria a linha se ainda não existir, atualiza a
    quantidade se já existir."""
    result = await session.execute(
        select(ProdutoEstoque).where(
            ProdutoEstoque.produto_id == produto_id,
            ProdutoEstoque.centro_distribuicao == centro_distribuicao,
        )
    )
    estoque = result.scalars().first()
    if estoque is None:
        estoque = ProdutoEstoque(
            produto_id=produto_id,
            centro_distribuicao=centro_distribuicao,
            quantidade=quantidade,
        )
        session.add(estoque)
    else:
        estoque.quantidade = quantidade
    await session.commit()
    await session.refresh(estoque)
    return estoque


async def listar_estoque(session: AsyncSession, produto_id: int) -> list[ProdutoEstoque]:
    result = await session.execute(
        select(ProdutoEstoque)
        .where(ProdutoEstoque.produto_id == produto_id)
        .order_by(ProdutoEstoque.centro_distribuicao)
    )
    return list(result.scalars().all())


async def adicionar_desconto_volume(
    session: AsyncSession,
    produto_id: int,
    quantidade_minima: int,
    percentual_desconto: Decimal,
) -> ProdutoDescontoVolume:
    desconto = ProdutoDescontoVolume(
        produto_id=produto_id,
        quantidade_minima=quantidade_minima,
        percentual_desconto=percentual_desconto,
    )
    session.add(desconto)
    await session.commit()
    await session.refresh(desconto)
    return desconto


async def listar_descontos_volume(
    session: AsyncSession, produto_id: int
) -> list[ProdutoDescontoVolume]:
    result = await session.execute(
        select(ProdutoDescontoVolume)
        .where(ProdutoDescontoVolume.produto_id == produto_id)
        .order_by(ProdutoDescontoVolume.quantidade_minima)
    )
    return list(result.scalars().all())
