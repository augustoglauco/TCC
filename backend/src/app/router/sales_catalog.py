"""Orquestrador como integrador do MCP B2B em Vendas (R12, Fase 5) — ver
docs/superpowers/specs/2026-09-24-orquestrador-mcp-b2b-vendas-design.md.

Resolve produto/quantidade/compatibilidade mencionados numa mensagem de
Vendas em duas etapas: busca de candidatos por SQL (`buscar_candidatos`,
este módulo, sem LLM) e desambiguação por LLM entre os candidatos
(`extract_sales_slots`, mesmo módulo) — necessário porque o catálogo real
vai crescer para ~1000 produtos, onde casar nome por substring direto é
ambíguo demais (spec §2). `SalesCatalogClient` chama `app.db.catalog`
diretamente (mesmo processo) — não é um cliente MCP de verdade contra o
processo `mcp-b2b-server` separado (spec §4).

Mesmo padrão de módulo de `app.router.scheduling`: lógica de domínio pura
(sem tipos de streaming SSE), consumida por `app.router.orchestrator`.
"""

import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.db.catalog import (
    calcular_item_cotacao,
    listar_categorias_distintas,
    listar_estoque,
    listar_produtos,
    obter_produto,
    sao_compativeis,
)
from app.db.models import Pedido, Produto
from app.router.classifier import normalize, strip_code_fence
from app.router.llm_client import LLMClient
from app.services.comprovante_evaluator import ComprovanteEvaluator, ParecerComprovante


class CandidatoProduto(BaseModel):
    id: int
    nome: str
    categoria: str


class VendaSlots(BaseModel):
    produto_id: int | None = None
    produto_relacionado_id: int | None = None
    quantidade: int | None = None
    # Consulta genérica por categoria (ex.: "tem geradores no estoque?"): o
    # LLM devolve o nome da categoria em vez de um produto_id único quando o
    # cliente pergunta por um tipo de produto sem escolher um modelo
    # específico. Preenchido só quando `produto_id` fica `None`.
    categoria: str | None = None
    # Consulta totalmente genérica, sem produto nem categoria citados (ex.:
    # "quais produtos vocês têm em estoque?", correção de 2026-09-29—
    # antes esse caso não injetava nenhum dado do catálogo, ver
    # docs/ARCHITECTURE.md §5). Precedência: `produto_id` > `categoria` >
    # `listar_tudo` (aplicada em `extract_sales_slots`).
    listar_tudo: bool = False


class EstoqueCentroDistribuicao(BaseModel):
    centro_distribuicao: str
    quantidade: int


class DadosCatalogoVendas(BaseModel):
    # `produto_id`/`preco`/`imagem_url` (correção de 2026-09-29, Fase 8):
    # usados para montar o card rico de produto/cotação no chat
    # (`orchestrator._construir_card_vendas`) — link para `/produtos/[id]`,
    # preço de tabela e foto. Opcionais (`None` = sem card) para não quebrar
    # os testes de formatação de texto que já construíam este modelo sem
    # eles; `consultar_detalhes` (único caminho de produção) sempre preenche
    # os três a partir do `Produto` já carregado.
    produto_id: int | None = None
    produto_nome: str
    preco: Decimal | None = None
    imagem_url: str | None = None
    estoque_total: int
    # Detalhe por centro de distribuição (correção de 2026-09-29): o resumo
    # do chat só levava o total somado, então "quanto tem no CD-SP?"/"estoque
    # por centro de distribuição?" não tinha como ser respondido de forma
    # precisa — o LLM repetia o total como se fosse o valor de um único CD.
    # O detalhamento (`app.db.catalog.listar_estoque`) já era buscado aqui
    # para calcular `estoque_total`; só não chegava ao bloco do prompt.
    estoque_por_cd: list[EstoqueCentroDistribuicao] = []
    # Ficha do produto (correção de 2026-09-27): sem ela, "quais os dados
    # técnicos?" só tinha estoque e cotação no bloco, e o LLM respondia
    # sobre preço e estoque.
    descricao: str | None = None
    especificacoes_tecnicas: str | None = None
    dimensoes_cm: str | None = None
    peso_kg: Decimal | None = None
    cotacao: tuple[Decimal, Decimal, Decimal] | None = None
    quantidade: int | None = None
    produto_relacionado_nome: str | None = None
    compativel: bool | None = None


class ProdutoNaCategoria(BaseModel):
    nome: str
    preco: Decimal
    estoque_total: int


class DadosCatalogoCategoria(BaseModel):
    """Resultado de uma consulta genérica por categoria — lista os produtos
    da categoria com preço e estoque somado entre centros de distribuição,
    para o assistente responder perguntas do tipo "quais geradores vocês têm
    em estoque?" sem precisar que o cliente cite um modelo específico.

    `categoria=None` representa o catálogo completo (correção de
    2026-09-29): quando o cliente pergunta de forma totalmente genérica por
    "produtos"/"itens em estoque" sem citar nenhuma categoria, o mesmo
    formato de resposta é reaproveitado listando todos os produtos em vez de
    filtrar por uma categoria."""

    categoria: str | None
    produtos: list[ProdutoNaCategoria]


# MVP: tokenização simples da mensagem do cliente (etapa 1, spec §2) para
# reduzir o catálogo (potencialmente ~1000 produtos) a um punhado de
# candidatos plausíveis, antes de qualquer chamada LLM — heurística de MVP,
# não NLP de verdade. Reaproveita `app.router.classifier.normalize`
# (minúsculas, sem acentos) em vez de uma terceira implementação de
# normalização de texto no projeto.
# Lista compacta de propósito: sem o `fmt: off`, o formatador poria uma
# palavra por linha.
# fmt: off
_STOPWORDS = frozenset(
    {
        "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas",
        "para", "por", "com", "uma", "um", "uns", "umas", "que", "tem",
        "voces", "voce", "preciso", "queria", "quero", "gostaria", "ola",
        "favor", "obrigado", "obrigada", "bom", "boa", "dia", "tarde",
        "noite", "quanto", "custa", "custam", "sobre", "tenho", "onde",
        "quando", "como", "tudo", "bem", "cotacao", "estoque", "preco",
        "disponivel",
    }
)
# fmt: on

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Etapa 1 (spec §8): teto de candidatos devolvidos por `buscar_candidatos`
# antes da desambiguação por LLM (etapa 2) — nome explícito no módulo por
# ser o mesmo valor citado na spec, não um "10" mágico solto na assinatura.
SALES_CANDIDATOS_LIMITE = 10


def extrair_termos_busca(message: str) -> list[str]:
    """Extrai palavras significativas da mensagem (minúsculas, sem acentos,
    sem pontuação) para a busca de candidatos — descarta palavras com 2
    caracteres ou menos e a stopword list acima.

    # MVP: exceção à regra de tamanho — qualquer token com dígito (ex.: "15"
    # em "GD-15") é mantido mesmo com 2 caracteres ou menos, porque dígito é
    # justamente o que torna um token parecido com código de produto (SKU) e
    # vale a pena preservar para a busca, ao contrário de uma palavra curta
    # qualquer sem dígito.
    """
    termos_normalizados = _TOKEN_RE.findall(normalize(message))
    return [
        termo
        for termo in termos_normalizados
        if (len(termo) > 2 or any(c.isdigit() for c in termo)) and termo not in _STOPWORDS
    ]


# MVP: chama `app.db.catalog` diretamente, no mesmo processo — não abre uma
# conexão MCP real contra o `mcp-b2b-server` separado (spec §4).
class SalesCatalogClient:
    """Injetado em `handle_message` (mesmo padrão opcional de
    `calendar_client`/`scheduling_config`) — construído uma vez em
    `app.main` a partir do `db_sessionmaker` já existente, igual a
    `create_b2b_mcp_server(session_factory, ...)`."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def buscar_candidatos(
        self, termos: list[str], limite: int = SALES_CANDIDATOS_LIMITE
    ) -> list[CandidatoProduto]:
        """`OR` de `ILIKE '%termo%'` contra `Produto.nome`/`Produto.categoria`
        por termo, `LIMIT limite`. Sem ranking por relevância — a
        desambiguação de verdade é a etapa 2 (LLM, `extract_sales_slots`),
        que só recebe esta lista já reduzida."""
        if not termos:
            return []
        condicoes = [
            condicao
            for termo in termos
            for condicao in (
                Produto.nome.ilike(f"%{termo}%"),
                Produto.categoria.ilike(f"%{termo}%"),
            )
        ]
        async with self._session_factory() as session:
            result = await session.execute(
                select(Produto.id, Produto.nome, Produto.categoria)
                .where(or_(*condicoes))
                .order_by(Produto.id)
                .limit(limite)
            )
            return [
                CandidatoProduto(id=linha.id, nome=linha.nome, categoria=linha.categoria)
                for linha in result.all()
            ]

    async def consultar_detalhes(
        self, produto_id: int, produto_relacionado_id: int | None, quantidade: int | None
    ) -> DadosCatalogoVendas | None:
        """Traz o estoque total (soma entre centros de distribuição) e o
        detalhamento por CD (correção de 2026-09-29 — antes só a soma ia
        para o bloco do chat, e "quanto tem no CD-SP?" não tinha como ser
        respondido corretamente), cotação (só se `quantidade` veio) e
        compatibilidade (só se `produto_relacionado_id` veio e existir).
        Devolve `None` se `produto_id` não existir."""
        async with self._session_factory() as session:
            produto = await obter_produto(session, produto_id)
            if produto is None:
                return None
            estoques = await listar_estoque(session, produto_id)
            estoque_total = sum(estoque.quantidade for estoque in estoques)
            estoque_por_cd = [
                EstoqueCentroDistribuicao(
                    centro_distribuicao=estoque.centro_distribuicao,
                    quantidade=estoque.quantidade,
                )
                for estoque in estoques
            ]
            cotacao = None
            # MVP: quantidade do LLM usada sem faixa de sanidade (valor
            # não-numérico já é descartado inteiro em extract_sales_slots,
            # via ValidationError, antes de chegar aqui; valores <=0 ou muito
            # grandes não são validados).
            if quantidade is not None and quantidade > 0:
                cotacao = calcular_item_cotacao(produto, quantidade)
            produto_relacionado_nome = None
            compativel = None
            if produto_relacionado_id is not None:
                relacionado = await obter_produto(session, produto_relacionado_id)
                if relacionado is not None:
                    produto_relacionado_nome = relacionado.nome
                    compativel = await sao_compativeis(session, produto_id, produto_relacionado_id)
            return DadosCatalogoVendas(
                produto_id=produto.id,
                produto_nome=produto.nome,
                preco=produto.preco,
                imagem_url=produto.imagem_url,
                estoque_total=estoque_total,
                estoque_por_cd=estoque_por_cd,
                descricao=produto.descricao,
                especificacoes_tecnicas=produto.especificacoes_tecnicas,
                dimensoes_cm=produto.dimensoes_cm,
                peso_kg=produto.peso_kg,
                cotacao=cotacao,
                quantidade=quantidade,
                produto_relacionado_nome=produto_relacionado_nome,
                compativel=compativel,
            )

    async def listar_categorias(self) -> list[str]:
        """Categorias distintas do catálogo, passadas ao LLM em
        `extract_sales_slots` para ele classificar uma pergunta genérica
        ("quais geradores vocês têm?") numa categoria real, em vez de tentar
        escolher um produto único."""
        async with self._session_factory() as session:
            return await listar_categorias_distintas(session)

    async def consultar_categoria(self, categoria: str) -> DadosCatalogoCategoria | None:
        """Lista os produtos de uma categoria com preço e estoque somado
        entre centros de distribuição — atende consultas genéricas ("quais
        geradores vocês têm?") em que o cliente não cita um modelo
        específico. Devolve `None` se a categoria não tiver nenhum produto
        (ex.: o LLM devolveu uma categoria que não existe no catálogo)."""
        async with self._session_factory() as session:
            produtos = await listar_produtos(session, categoria=categoria)
            if not produtos:
                return None
            itens = [
                ProdutoNaCategoria(
                    nome=produto.nome,
                    preco=produto.preco,
                    # `produto.estoques` já vem carregado por selectinload em
                    # `listar_produtos` (_produto_query), sem query extra por
                    # produto.
                    estoque_total=sum(estoque.quantidade for estoque in produto.estoques),
                )
                for produto in produtos
            ]
        return DadosCatalogoCategoria(categoria=categoria, produtos=itens)

    async def listar_todos_produtos(self) -> DadosCatalogoCategoria | None:
        """Lista todo o catálogo com preço e estoque somado entre centros de
        distribuição — atende consultas totalmente genéricas ("quais
        produtos vocês têm em estoque?") em que o cliente não cita produto
        nem categoria (correção de 2026-09-29, ver docs/ARCHITECTURE.md §5).
        Mesmo formato de `consultar_categoria`, com `categoria=None`.
        Devolve `None` se o catálogo estiver vazio."""
        async with self._session_factory() as session:
            produtos = await listar_produtos(session)
            if not produtos:
                return None
            itens = [
                ProdutoNaCategoria(
                    nome=produto.nome,
                    preco=produto.preco,
                    estoque_total=sum(estoque.quantidade for estoque in produto.estoques),
                )
                for produto in produtos
            ]
        return DadosCatalogoCategoria(categoria=None, produtos=itens)


_EXTRACTION_PROMPT_TEMPLATE = """\
Você está ajudando um cliente numa conversa de vendas. A partir da lista de \
produtos candidatos abaixo (já filtrada do catálogo da empresa), identifique \
qual produto o cliente está perguntando, se houver um segundo produto \
mencionado para checar compatibilidade, e a quantidade desejada.

Produtos candidatos (escolha o ID de um deles, ou null se nenhum corresponder \
ao que o cliente pediu):
{candidatos}

Categorias disponíveis no catálogo (use no campo "categoria" APENAS quando o \
cliente pergunta genericamente por um TIPO de produto listado acima, sem \
escolher um modelo específico — ex.: "quais produtos da categoria X vocês \
têm?", substituindo X por uma das categorias acima. Se o cliente perguntar \
de forma totalmente genérica por "produtos"/"itens em estoque" sem citar \
nenhuma categoria da lista, deixe "categoria" null — não infira uma \
categoria específica):
{categorias}

Se o cliente pedir para ver o catálogo/estoque disponível de forma ampla, \
sem mencionar nenhum produto nem categoria específica da lista acima (ex.: \
"quais produtos vocês têm em estoque?", "pode me mostrar tudo que vocês têm \
disponível?", "quero ver o catálogo de vocês"), preencha "listar_tudo": true \
e deixe "produto_id" e "categoria" null.

Contexto recente da conversa:
{contexto}

Mensagem atual do cliente: {mensagem}

Responda APENAS com JSON no formato: {{"produto_id": <id ou null>, \
"produto_relacionado_id": <id ou null>, "quantidade": <número ou null>, \
"categoria": <nome exato de uma categoria acima ou null>, \
"listar_tudo": <true ou false>}}. \
"produto_id" e "produto_relacionado_id" DEVEM ser um dos IDs listados acima \
(nunca invente um ID que não está na lista); use null se o cliente não \
mencionar um segundo produto para checar compatibilidade, ou nenhum produto \
da lista corresponder ao pedido. \
Preencha "categoria" (e deixe "produto_id" null) quando o cliente pergunta \
por um tipo/categoria de produto em geral em vez de um modelo específico; \
caso contrário deixe "categoria" null. \
"listar_tudo" só é true quando nem um produto específico nem uma categoria \
da lista acima foram mencionados; caso contrário deixe "listar_tudo": false."""


def _formatar_candidatos(candidatos: list[CandidatoProduto]) -> str:
    if not candidatos:
        return "(nenhum)"
    return "\n".join(
        f"- id={candidato.id}: {candidato.nome} (categoria: {candidato.categoria})"
        for candidato in candidatos
    )


def _parse_extraction(raw_text: str) -> VendaSlots:
    parsed = json.loads(strip_code_fence(raw_text))
    return VendaSlots(**parsed)


async def extract_sales_slots(
    message: str,
    recent_messages: list[str],
    candidatos: list[CandidatoProduto],
    llm_client: LLMClient,
    categorias_disponiveis: list[str] | None = None,
) -> VendaSlots:
    """Uma chamada LLM: recebe a mensagem do cliente junto com a lista de
    candidatos já filtrada (etapa 1, `SalesCatalogClient.buscar_candidatos`)
    e escolhe o `produto_id` certo entre eles — copiar um ID de uma lista
    real e pequena é uma tarefa muito mais confiável para o LLM do que
    inventar um nome livre que depois precisa ser casado (spec §2). Quando o
    cliente pergunta genericamente por um TIPO de produto listado em
    `categorias_disponiveis` (ex.: "quais produtos da categoria X vocês
    têm?"), em vez de um `produto_id` único, o LLM devolve essa `categoria`
    (validada contra a lista no retorno). Correção de 2026-09-29: o exemplo
    do prompt citava uma categoria fixa ("geradores"), enviesando o LLM a
    inferir essa categoria mesmo em perguntas totalmente genéricas
    ("quais produtos vocês têm em estoque?"); o exemplo agora usa um
    placeholder genérico e instrui a deixar "categoria" null quando nenhuma
    categoria específica é citada. Mesmo padrão de
    `app.router.scheduling.extract_booking_slots`: prompt → JSON → parse com
    `ValidationError`/`JSONDecodeError` tratado, fallback pra `VendaSlots()`
    vazio em qualquer falha de parsing (não quebra o turno)."""
    contexto = "\n".join(recent_messages) if recent_messages else "(nenhum)"
    categorias = categorias_disponiveis or []
    prompt = _EXTRACTION_PROMPT_TEMPLATE.format(
        candidatos=_formatar_candidatos(candidatos),
        categorias="\n".join(f"- {categoria}" for categoria in categorias) or "(nenhuma)",
        contexto=contexto,
        mensagem=message,
    )
    response = await llm_client.generate(prompt)
    try:
        slots = _parse_extraction(response.text)
    except json.JSONDecodeError, ValidationError, TypeError:
        return VendaSlots()

    ids_validos = {candidato.id for candidato in candidatos}
    if slots.produto_id is not None and slots.produto_id not in ids_validos:
        slots.produto_id = None
    if slots.produto_relacionado_id is not None and slots.produto_relacionado_id not in ids_validos:
        slots.produto_relacionado_id = None
    # Categoria só vale se for uma das disponíveis (comparação sem acento/
    # caixa, mesma normalização do resto do módulo) e se nenhum produto
    # específico foi identificado — produto único tem precedência sobre a
    # listagem genérica por categoria.
    if slots.categoria is not None:
        categorias_norm = {normalize(categoria): categoria for categoria in categorias}
        categoria_real = categorias_norm.get(normalize(slots.categoria))
        slots.categoria = None if slots.produto_id is not None else categoria_real
    # "listar_tudo" só vale quando nem produto nem categoria foram
    # resolvidos — produto único e categoria específica têm precedência
    # (mesmo espírito da precedência categoria > produto_id acima).
    if slots.produto_id is not None or slots.categoria is not None:
        slots.listar_tudo = False
    return slots


def _texto_contem_evidencia_transacional(t: str) -> bool:
    """Heurística combinada: indícios de DADO real de transação (autenticação,
    código, favorecido) junto de valor/moeda — diferente de só mencionar a
    palavra "comprovante"/"pagamento" numa frase qualquer."""
    return ("autentica" in t or "transa" in t or "favorecido" in t) and (
        "r$" in t or "valor" in t or "pix" in t
    )


def detectar_intencao_comprovante(message: str) -> bool:
    """Identifica se a mensagem contém ou referencia o envio de um comprovante de pagamento.

    Propositalmente sensível (inclui frases que só ANUNCIAM a intenção, ex.:
    "quero enviar o comprovante") — é o que decide se entramos no fluxo de
    conversão de reserva em venda. Não decide sozinho se há conteúdo de fato
    para validar: ver `texto_parece_conteudo_de_comprovante` para essa
    distinção (achado de 2026-10-05: sem ela, uma frase de intenção sem
    anexo e sem dado real de transação era mandada para o avaliador de IA
    como se fosse o próprio comprovante, que sempre reprovava).
    """
    if not message:
        return False
    t = message.lower()
    if "[texto extraído da imagem]" in t:
        return True
    palavras_chave = (
        "comprovante",
        "recibo",
        "pagamento realizado",
        "paguei",
        "transferência realizada",
        "transferencia realizada",
        "pix realizado",
        "segue o pix",
        "segue comprovante",
        "envio o comprovante",
        "anexo o comprovante",
        "comprovante do pix",
        "comprovante de transferência",
        "comprovante de pagamento",
    )
    if any(p in t for p in palavras_chave):
        return True
    return _texto_contem_evidencia_transacional(t)


def texto_parece_conteudo_de_comprovante(message: str) -> bool:
    """Diferente de `detectar_intencao_comprovante`: aqui verificamos se o
    TEXTO EM SI parece conter dados reais de uma transação (colados pelo
    cliente, ou extraídos por OCR de uma imagem — ver marcador `[Texto
    extraído da imagem]` concatenado em `app.api.chat`), e não apenas
    anunciar a intenção de enviar um comprovante (ex.: "quero enviar o
    comprovante"). Usado para decidir se vale a pena mandar o texto para o
    avaliador de IA — uma frase de intenção pura sempre reprovaria, de forma
    confusa para o cliente."""
    if not message:
        return False
    t = message.lower()
    if "[texto extraído da imagem]" in t:
        return True
    return _texto_contem_evidencia_transacional(t)


async def buscar_reserva_ativa(
    session: AsyncSession,
    conversation_id: str | None = None,
    user_email: str | None = None,
    pedido_id: str | None = None,
) -> Pedido | None:
    """Busca a reserva mais recente com status 'reservado' ou 'pagamento_divergente'.

    Tenta, em ordem, pedido_id -> conversation_id -> user_email, só
    avançando para o próximo critério se o anterior não achar nada (achado
    de 2026-10-05: antes era um `if/elif` que escolhia só UM critério pela
    prioridade de qual parâmetro foi passado, não por qual realmente
    encontra algo — como toda mensagem de chat tem um `conversation_id`,
    `user_email` nunca era tentado quando o cliente confirma o pagamento
    numa conversa NOVA, diferente daquela em que fez o pedido).
    """
    base_stmt = (
        select(Pedido)
        .options(selectinload(Pedido.itens))
        .where(Pedido.status.in_(["reservado", "pagamento_divergente"]))
        .order_by(Pedido.criado_em.desc())
        .limit(1)
    )

    if pedido_id:
        try:
            uuid_obj = UUID(pedido_id)
        except ValueError, TypeError:
            uuid_obj = None
        if uuid_obj is not None:
            result = await session.execute(base_stmt.where(Pedido.id == uuid_obj))
            pedido = result.scalar_one_or_none()
            if pedido is not None:
                return pedido

    if conversation_id:
        result = await session.execute(base_stmt.where(Pedido.conversation_id == conversation_id))
        pedido = result.scalar_one_or_none()
        if pedido is not None:
            return pedido

    if user_email:
        result = await session.execute(base_stmt.where(Pedido.user_email == user_email))
        pedido = result.scalar_one_or_none()
        if pedido is not None:
            return pedido

    return None


async def processar_conversao_comprovante(
    session: AsyncSession,
    pedido: Pedido,
    texto_comprovante: str,
    llm_client: Any = None,
    comprovante_bytes: bytes | None = None,
    nome_arquivo: str | None = None,
    vision_client: Any = None,
    local_vision_client: Any = None,
) -> tuple[bool, str, ParecerComprovante]:
    """Avalia o comprovante de pagamento via ComprovanteEvaluator e converte o status do pedido.

    `local_vision_client`/`vision_client` (achado de 2026-10-06, religado
    aqui — antes só o fluxo administrativo passava visão): sem eles, uma
    foto de comprovante malfeita (ângulo/luz, comum vindo do celular do
    cliente) que o OCR não consegue ler nunca tinha nenhuma tentativa de
    visão no chat.
    """
    valor_devido = sum(
        (item.preco_unitario * item.quantidade for item in pedido.itens),
        Decimal("0.00"),
    )
    evaluator = ComprovanteEvaluator(
        llm_client=llm_client, vision_client=vision_client, local_vision_client=local_vision_client
    )

    filename_safe = None
    if comprovante_bytes:
        ext = Path(nome_arquivo or "comprovante.png").suffix or ".png"
        filename_safe = f"{pedido.id}_comprovante{ext}"
        upload_dir = Path("uploads/comprovantes")
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / filename_safe
        file_path.write_bytes(comprovante_bytes)
        pedido.comprovante_url = f"/uploads/comprovantes/{filename_safe}"

    # Achado de 2026-10-05: a ordem aqui importa. Texto só vai para o
    # avaliador de IA quando PARECE conter dado real de transação
    # (`texto_parece_conteudo_de_comprovante`) — cobre tanto o comprovante
    # colado como texto literal quanto o OCR de imagem já concatenado pelo
    # `app.api.chat` (marcador `[Texto extraído da imagem]`). Uma frase que
    # só ANUNCIA a intenção de enviar (ex.: "quero enviar o comprovante",
    # sem anexo e sem dado real) nunca tinha conteúdo nenhum para validar —
    # mandá-la para o avaliador sempre reprovava de forma confusa para o
    # cliente. Se não há texto com conteúdo mas há um arquivo anexado
    # (`comprovante_bytes`), avalia o arquivo; sem nenhum dos dois, pede o
    # anexo explicitamente, sem marcar a reserva como divergente (nada foi
    # de fato submetido para já haver uma divergência a registrar).
    if texto_comprovante and texto_parece_conteudo_de_comprovante(texto_comprovante):
        parecer = await evaluator.avaliar_texto(
            texto=texto_comprovante,
            valor_devido=valor_devido,
            reserva_id=str(pedido.id),
            nome_comprador=pedido.user_email or "Cliente",
        )
    elif comprovante_bytes:
        parecer = await evaluator.avaliar_documento(
            conteudo=comprovante_bytes,
            nome_arquivo=filename_safe or "comprovante.png",
            valor_devido=valor_devido,
            reserva_id=str(pedido.id),
            nome_comprador=pedido.user_email or "Cliente",
        )
    else:
        mensagem_resposta = (
            f"Para confirmar o pagamento da sua reserva ({pedido.id}), por favor envie uma foto "
            f"ou um arquivo legível do comprovante (PIX, TED ou transferência) no valor de "
            f"R$ {valor_devido:.2f}."
        )
        parecer_vazio = ParecerComprovante(
            valido=False,
            valor_pago=Decimal("0.00"),
            divergencia=-valor_devido,
            justificativa=(
                "Nenhum conteúdo de comprovante foi fornecido; apenas intenção de envio detectada."
            ),
        )
        return False, mensagem_resposta, parecer_vazio

    # Conversão genérica via chat para qualquer reserva emitida
    tipo_conversao = "auto_chat"

    if parecer.valido and abs(parecer.divergencia) <= Decimal("0.01"):
        pedido.status = "venda_concluida"
        pedido.tipo_conversao = tipo_conversao
        pedido.convertido_em = datetime.now(UTC)
        pedido.convertido_por = "sistema_llm"
        pedido.llm_parecer = parecer.to_json()
        await session.commit()

        tx_info = f" (Transação: {parecer.codigo_transacao})" if parecer.codigo_transacao else ""
        mensagem_resposta = (
            f"Seu pagamento foi confirmado com sucesso! O comprovante no valor de "
            f"R$ {parecer.valor_pago:.2f} foi validado com êxito{tx_info}. Sua reserva "
            f"({pedido.id}) foi convertida em venda concluída."
        )
        return True, mensagem_resposta, parecer
    else:
        pedido.status = "pagamento_divergente"
        pedido.llm_parecer = parecer.to_json()
        await session.commit()

        if parecer.valor_pago > Decimal("0.00") and abs(parecer.divergencia) > Decimal("0.01"):
            mensagem_resposta = (
                f"Identificamos uma divergência no seu comprovante. O valor devido "
                f"para a sua reserva é de R$ {valor_devido:.2f}, mas o comprovante "
                f"aponta R$ {parecer.valor_pago:.2f} "
                f"(diferença de R$ {abs(parecer.divergencia):.2f}). "
                f"Por favor, verifique e envie o comprovante com o valor correto "
                f"para concluirmos sua compra."
            )
        else:
            mensagem_resposta = (
                f"Não foi possível validar o seu comprovante de pagamento: "
                f"{parecer.justificativa}. Por favor, envie um comprovante legível "
                f"(PIX, TED ou transferência) com o valor integral da sua reserva "
                f"(R$ {valor_devido:.2f})."
            )
        return False, mensagem_resposta, parecer
