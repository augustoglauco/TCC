"""Backend único de dados de catálogo/estoque/preços (R12, Fase 5).

Camada de acesso a dados sobre `Produto`/`ProdutoEstoque`/
`ProdutoDescontoVolume`/`ProdutoCompatibilidade`/`Pedido`/`PedidoItem`
(`app.db.models`) — reaproveitada tanto pelo RAG (R4, via leitura genérica em
`app.rag.db_connector`, que continua funcionando sem mudanças por ser
baseada em reflexão de tabela) quanto pelo servidor MCP B2B
(`app.mcp_server.b2b`), que expõe os 4 recursos de leitura como resources e
as 4 ferramentas transacionais (compatibilidade, frete, cotação, reserva/
pedido) como tools sobre estas mesmas funções — ver `docs/ARCHITECTURE.md`
§6.

Mesmo padrão de funções livres recebendo `AsyncSession` já usado em
`app.router.tone_monitor` (`criar_escalonamento`/`listar_escalonamentos`),
em vez de um repositório em classe — mais simples de testar isoladamente
(`docs/CONVENTIONS.md`).

# MVP: sem tratamento de concorrência em reservas/pedidos nem trilha de
auditoria — evolução futura explícita registrada em `docs/ARCHITECTURE.md`
§6 ("Governança e segurança"), não antecipada aqui. `atualizar_estoque` e
`criar_pedido` fazem um simples upsert/decremento (ler, depois escrever) sem
lock otimista/pessimista; sob concorrência real, duas reservas simultâneas
do mesmo item podem sobre-reservar entre si (`criar_pedido` só evita
inconsistência *dentro* de uma única chamada com vários itens, ver seu
docstring — não entre chamadas concorrentes).
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Pedido,
    PedidoItem,
    Produto,
    ProdutoCompatibilidade,
    ProdutoDescontoVolume,
    ProdutoEstoque,
    ProdutoImagem,
)


class EstoqueInsuficienteError(Exception):
    """Levantada por `criar_pedido` quando algum item da reserva pede mais
    quantidade do que o disponível no centro de distribuição informado —
    nenhum item do pedido é gravado (checagem de todos os itens acontece
    antes de qualquer escrita, ver `criar_pedido`)."""


class ProdutoInexistenteError(Exception):
    """Levantada por `criar_pedido` quando um `produto_id` referenciado num
    item não existe no catálogo."""


def _produto_query():
    # `app.mcp_server.b2b` (resources de catálogo/estoque) acessa
    # `produto.estoques`/`.descontos_volume` DEPOIS de fechar a sessão que
    # chamou `obter_produto`/`listar_produtos` — só funciona sem
    # `MissingGreenlet` porque o `selectinload` abaixo já carregou as
    # coleções em memória durante a query. Se este `selectinload` for
    # removido, os handlers do MCP B2B quebram também, não só quem chama
    # direto por aqui.
    return select(Produto).options(
        selectinload(Produto.estoques),
        selectinload(Produto.descontos_volume),
        selectinload(Produto.imagens),
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
    preco_base_fornecedor: Decimal | None = None,
    imagem_url: str | None = None,
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
        preco_base_fornecedor=preco_base_fornecedor,
        imagem_url=imagem_url,
    )
    session.add(produto)
    await session.commit()
    # Achado no code-review (2026-09-24): tentei remover este refresh
    # supondo que um objeto recém-criado já começaria com as coleções de
    # relationship vazias em memória, sem I/O — verificado empiricamente
    # que NÃO é o caso aqui (`MissingGreenlet` ao acessar `produto.estoques`
    # sem ele, `lazy="select"` tenta carregar de verdade mesmo pós-commit).
    # Mantido — ao contrário de `atualizar_produto`/`deletar_produto`
    # abaixo, que reaproveitam um `produto` já carregado com
    # `selectinload` via `obter_produto`, este é o único ponto do módulo
    # que precisa do refresh de verdade.
    await session.refresh(produto, attribute_names=["estoques", "descontos_volume", "imagens"])
    return produto


async def obter_produto(session: AsyncSession, produto_id: int) -> Produto | None:
    result = await session.execute(_produto_query().where(Produto.id == produto_id))
    return result.scalars().first()


async def listar_produtos(
    session: AsyncSession,
    categoria: str | None = None,
    termo: str | None = None,
) -> list[Produto]:
    query = _produto_query().order_by(Produto.id)
    if categoria is not None and categoria.strip():
        cats = [c.strip() for c in categoria.split(",") if c.strip()]
        if len(cats) == 1:
            query = query.where(Produto.categoria.ilike(cats[0]))
        elif len(cats) > 1:
            query = query.where(or_(*(Produto.categoria.ilike(c) for c in cats)))
    if termo is not None and termo.strip():
        padrao = f"%{termo.strip()}%"
        query = query.where(
            or_(
                Produto.nome.ilike(padrao),
                Produto.descricao.ilike(padrao),
                Produto.especificacoes_tecnicas.ilike(padrao),
            )
        )
    result = await session.execute(query)
    return list(result.scalars().unique().all())


async def listar_categorias_distintas(session: AsyncSession) -> list[str]:
    """Retorna lista alfabética das categorias únicas existentes no catálogo."""
    stmt = select(Produto.categoria).where(Produto.categoria.isnot(None)).distinct()
    res = await session.execute(stmt)
    return sorted(list({c.strip() for c in res.scalars().all() if c and c.strip()}))



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
    # Achado no code-review (2026-09-24): `obter_produto` já carrega
    # `estoques`/`descontos_volume` via `selectinload` (`_produto_query()`)
    # e `updates` nunca toca essas coleções (só colunas escalares) — o
    # refresh delas aqui era uma query supérflua a cada atualização.
    return produto


async def deletar_produto(session: AsyncSession, produto_id: int) -> bool:
    """Remove o produto e os registros filhos (estoque/descontos/
    compatibilidades/itens de pedido). Os filhos são apagados por `DELETE`
    explícito em vez de depender só do `cascade="all, delete-orphan"` do
    relationship — mais robusto contra o caso de a coleção
    `produto.estoques`/`descontos_volume` não estar carregada na identity
    map da sessão no momento da exclusão.

    Achado no code-review (2026-09-24): cheguei a remover os `DELETE`s
    explícitos supondo que o cascade bastaria, já que `obter_produto`
    sempre carrega as coleções via `selectinload` — verificado
    empiricamente que NÃO basta (os filhos sobreviviam à exclusão do pai
    nos testes). Mantidos.

    Achado no code-review (2026-09-24, item das ferramentas MCP B2B): as
    duas tabelas novas desta mesma fase (`ProdutoCompatibilidade`,
    `PedidoItem`) referenciam `produtos.id` por FK sem `ondelete=CASCADE` e
    sem relationship/cascade do lado do `Produto` — sem os `DELETE`s abaixo,
    excluir um produto com par de compatibilidade cadastrado (a fixture da
    migração 0009 cadastra vários) ou com item de pedido associado
    levantaria `IntegrityError` no Postgres real (a violação passa
    despercebida no SQLite dos testes, que não aplica FK por padrão) — mesma
    limitação de "sem soft-delete/arquivamento" já aceita para
    estoque/descontos acima, agora estendida às duas tabelas novas.
    `ProdutoCompatibilidade` é direcional na escrita (ver seu docstring) —
    apaga nos dois sentidos (`produto_id` OU `compativel_com_id`).
    """
    produto = await obter_produto(session, produto_id)
    if produto is None:
        return False
    await session.execute(delete(ProdutoEstoque).where(ProdutoEstoque.produto_id == produto_id))
    await session.execute(
        delete(ProdutoDescontoVolume).where(ProdutoDescontoVolume.produto_id == produto_id)
    )
    await session.execute(delete(ProdutoImagem).where(ProdutoImagem.produto_id == produto_id))
    await session.execute(
        delete(ProdutoCompatibilidade).where(
            or_(
                ProdutoCompatibilidade.produto_id == produto_id,
                ProdutoCompatibilidade.compativel_com_id == produto_id,
            )
        )
    )
    await session.execute(delete(PedidoItem).where(PedidoItem.produto_id == produto_id))
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


# --- Ferramenta 1: validação de compatibilidade ------------------------------


async def criar_compatibilidade(
    session: AsyncSession, produto_id: int, compativel_com_id: int
) -> ProdutoCompatibilidade:
    """Cadastra um par de produtos compatíveis (escrita direcional — a
    consulta em `sao_compativeis` cobre os dois sentidos). Usado hoje só pela
    fixture da migração `0009` e pelos testes; a ferramenta MCP de
    compatibilidade só lê (`sao_compativeis`)."""
    compatibilidade = ProdutoCompatibilidade(
        produto_id=produto_id, compativel_com_id=compativel_com_id
    )
    session.add(compatibilidade)
    await session.commit()
    await session.refresh(compatibilidade)
    return compatibilidade


async def sao_compativeis(session: AsyncSession, produto_id: int, outro_produto_id: int) -> bool:
    """Verifica se dois produtos são compatíveis, nos dois sentidos (par
    cadastrado como A->B ou B->A conta igual, ver `ProdutoCompatibilidade`)."""
    result = await session.execute(
        select(ProdutoCompatibilidade.id).where(
            or_(
                and_(
                    ProdutoCompatibilidade.produto_id == produto_id,
                    ProdutoCompatibilidade.compativel_com_id == outro_produto_id,
                ),
                and_(
                    ProdutoCompatibilidade.produto_id == outro_produto_id,
                    ProdutoCompatibilidade.compativel_com_id == produto_id,
                ),
            )
        )
    )
    return result.scalars().first() is not None


# --- Ferramenta 3: cotação automática (reaproveitada pela ferramenta 4) -----


def preco_vigente(produto: Produto, agora: datetime | None = None) -> Decimal:
    """Preço efetivo de um produto no momento: `preco_promocional` se a
    campanha estiver vigente (`promocao_valida_ate` definido e ainda não
    vencido), senão `preco` "de tabela". `promocao_valida_ate=None` conta
    como "sem campanha vigente" mesmo com `preco_promocional` preenchido —
    exige uma data de validade explícita para considerar a promoção ativa.
    Não aplica desconto por volume (ver `calcular_item_cotacao` para isso) —
    é o preço unitário "base" reaproveitado tanto pela cotação quanto pela
    reserva/pedido (preço gravado em `pedido_itens.preco_unitario`).

    # MVP: SQLite (usado nos testes de unidade, ver `docs/CONVENTIONS.md`)
    # não preserva timezone em `DateTime(timezone=True)` — devolve
    # `promocao_valida_ate` como naive mesmo quando gravado como aware; o
    # Postgres real (produção) preserva. Normalizado para UTC aqui (em vez
    # de deixar `TypeError: can't compare offset-naive and offset-aware
    # datetimes` vazar) para a função funcionar igual nos dois dialetos.
    """
    agora = agora or datetime.now(UTC)
    promocao_valida_ate = produto.promocao_valida_ate
    if promocao_valida_ate is not None and promocao_valida_ate.tzinfo is None:
        promocao_valida_ate = promocao_valida_ate.replace(tzinfo=UTC)
    if (
        produto.preco_promocional is not None
        and promocao_valida_ate is not None
        and promocao_valida_ate >= agora
    ):
        return produto.preco_promocional
    return produto.preco


def calcular_item_cotacao(
    produto: Produto, quantidade: int, agora: datetime | None = None
) -> tuple[Decimal, Decimal, Decimal]:
    """Calcula `(preco_unitario_base, percentual_desconto_aplicado, subtotal)`
    de um item de cotação: preço vigente (`preco_vigente`) com a maior faixa
    de `produto_descontos_volume` cuja `quantidade_minima` a `quantidade`
    atinge (0% se nenhuma faixa é atingida) — "maior faixa" = maior
    `quantidade_minima` entre as atingidas, não maior percentual (mais fiel
    à leitura de "a maior faixa... atinge" da decisão de arquitetura, mesmo
    que na prática, com faixas cadastradas de forma crescente, dê o mesmo
    resultado que escolher o maior percentual)."""
    preco_base = preco_vigente(produto, agora)
    percentual = Decimal("0")
    maior_faixa_atingida = -1
    for desconto in produto.descontos_volume:
        atinge_faixa = quantidade >= desconto.quantidade_minima
        if atinge_faixa and desconto.quantidade_minima > maior_faixa_atingida:
            maior_faixa_atingida = desconto.quantidade_minima
            percentual = desconto.percentual_desconto
    preco_com_desconto = preco_base * (Decimal("1") - percentual / Decimal("100"))
    subtotal = preco_com_desconto * quantidade
    # Arredonda para centavos (2 casas) — a divisão por 100 acima produz
    # mais casas decimais do que o `Numeric(10, 2)` de `preco`/
    # `preco_promocional` tem, mesmo quando o resultado matematicamente
    # "fecha" em centavos (ex.: 100.00 * 0.90 = 90.0000).
    subtotal = subtotal.quantize(Decimal("0.01"))
    return preco_base, percentual, subtotal


# --- Ferramenta 4: reserva/pedido --------------------------------------------


async def criar_pedido(session: AsyncSession, itens: list[tuple[int, int, str]]) -> Pedido:
    """Cria um pedido/reserva com os itens informados
    (`[(produto_id, quantidade, centro_distribuicao), ...]`) e decrementa o
    estoque de cada um.

    Valida a disponibilidade de TODOS os itens antes de gravar qualquer
    coisa (inclusive antes de decrementar o primeiro item) — decisão de
    implementação desta função, não coberta literalmente pela decisão de
    arquitetura: evita reservar parcialmente um pedido com vários itens
    quando só um deles não tem estoque suficiente. Não é lock otimista/
    pessimista (duas chamadas concorrentes a `criar_pedido` ainda podem
    sobre-reservar entre si, MVP aceito) — só evita o caso mais simples de
    inconsistência dentro de uma única chamada.

    Levanta `ProdutoInexistenteError` se algum `produto_id` não existe, e
    `EstoqueInsuficienteError` se a soma das quantidades pedidas para o
    mesmo par (produto, centro de distribuição) — mesmo em itens separados
    da lista — exceder o disponível.

    Achado no security-review (2026-09-24): a checagem original validava
    cada item da lista contra `disponivel`, mas repetia a mesma leitura
    "crua" do estoque para cada ocorrência de um par (produto_id,
    centro_distribuicao) repetido — dois itens de 6 unidades cada contra um
    estoque de 10 passavam individualmente (6 < 10) e o estoque final ficava
    negativo (10 - 6 - 6 = -2), apesar do docstring já prometer validar
    "TODOS os itens antes de gravar". `reservado_no_pedido` abaixo acumula a
    quantidade pedida por chave DENTRO desta mesma chamada antes de comparar
    com o disponível — resolve isso sem mexer na limitação de concorrência
    ENTRE chamadas (essa continua aceita como MVP).
    """
    produtos: dict[int, Produto] = {}
    estoques: dict[tuple[int, str], ProdutoEstoque | None] = {}
    reservado_no_pedido: dict[tuple[int, str], int] = {}
    for produto_id, quantidade, centro_distribuicao in itens:
        # Achado no code-review (2026-09-24): a validação de `quantidade > 0`
        # já existe no schema Pydantic da ferramenta MCP (`Field(gt=0)`), mas
        # esta função é reaproveitável por qualquer chamador (ver docstring
        # do módulo) — sem essa guarda aqui, uma `quantidade` negativa
        # nunca fazia `reservado_no_pedido[chave] > disponivel` ficar
        # verdadeiro (negativo nunca é maior), e a escrita
        # `estoque.quantidade -= quantidade` AUMENTAVA o estoque em vez de
        # falhar; `quantidade == 0` para um produto sem linha de estoque
        # (`estoque is None`) passava a checagem (0 > 0 é falso) e só
        # quebrava depois, com um `AssertionError` cru, em vez do erro
        # documentado.
        if quantidade <= 0:
            raise ValueError(
                f"Quantidade inválida para o produto {produto_id}: {quantidade} (deve ser > 0)."
            )
        if produto_id not in produtos:
            produto = await obter_produto(session, produto_id)
            if produto is None:
                raise ProdutoInexistenteError(f"Produto {produto_id} não encontrado no catálogo.")
            produtos[produto_id] = produto
        chave = (produto_id, centro_distribuicao)
        if chave not in estoques:
            result = await session.execute(
                select(ProdutoEstoque).where(
                    ProdutoEstoque.produto_id == produto_id,
                    ProdutoEstoque.centro_distribuicao == centro_distribuicao,
                )
            )
            estoques[chave] = result.scalars().first()
        estoque = estoques[chave]
        disponivel = estoque.quantidade if estoque is not None else 0
        reservado_no_pedido[chave] = reservado_no_pedido.get(chave, 0) + quantidade
        if reservado_no_pedido[chave] > disponivel:
            raise EstoqueInsuficienteError(
                f"Estoque insuficiente do produto {produto_id} em "
                f"{centro_distribuicao}: disponível {disponivel}, "
                f"pedido {reservado_no_pedido[chave]}."
            )

    pedido = Pedido()
    session.add(pedido)
    for produto_id, quantidade, centro_distribuicao in itens:
        produto = produtos[produto_id]
        preco_unitario = preco_vigente(produto)
        session.add(
            PedidoItem(
                pedido=pedido,
                produto_id=produto_id,
                centro_distribuicao=centro_distribuicao,
                quantidade=quantidade,
                preco_unitario=preco_unitario,
            )
        )
        estoque = estoques[(produto_id, centro_distribuicao)]
        assert estoque is not None  # garantido pela checagem de disponibilidade acima
        estoque.quantidade -= quantidade

    await session.commit()
    await session.refresh(pedido, attribute_names=["itens"])
    return pedido
