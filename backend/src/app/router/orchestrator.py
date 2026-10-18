import asyncio
import logging
import re
import time
import unicodedata
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from functools import partial
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.background_tasks import spawn_background_task
from app.db.models import Agendamento, RagCollection, RagDocument
from app.mcp_client.google_calendar import CalendarClient, GoogleCalendarConnectionError
from app.models.chat import (
    CardAgendamento,
    CardCotacao,
    CardDocumentoDownload,
    CardGrafico,
    CardProduto,
    ChatCard,
    RagChunkMetric,
)
from app.models.runtime_settings import (
    DEFAULT_INTENT_ROUTER_PROVIDER,
    DEFAULT_TONE_MONITOR_PROVIDER,
)
from app.router.classifier import Domain, classify
from app.router.llm_client import LLMClient, LLMStreamChunk
from app.router.playbooks import build_system_prompt
from app.router.prompt_safety import detectar_tentativa_injecao, wrap_untrusted
from app.router.rag_client import Document, RAGClient
from app.router.sales_catalog import (
    SALES_CANDIDATOS_LIMITE,
    DadosCatalogoCategoria,
    DadosCatalogoVendas,
    SalesCatalogClient,
    extract_sales_slots,
    extrair_termos_busca,
)
from app.router.scheduling import (
    DURACAO_VISITA,
    MSG_ERRO_MCP,
    BookingSlots,
    HorarioInvalidoError,
    SchedulingConfig,
    clear_booking_slots,
    extract_booking_slots,
    get_booking_slots,
    mensagem_campos_faltando,
    mensagem_pedir_confirmacao,
    mensagem_sucesso,
    merge_slots,
    set_booking_slots,
    validar_expediente,
)
from app.router.tone_monitor import ToneResult, analyze_tone, ja_escalada, marcar_escalada
from app.services.ai_usage import registrar_uso_ia
from app.user_profile.classificacao import DOMINIOS_POS_VENDA

logger = logging.getLogger(__name__)

# MVP: simplificações conscientes desta fase (ver docs/ROADMAP.md e
# docs/superpowers/specs/2026-09-05-roteador-basico-design.md §6):
# - os documentos devolvidos pelo RAG são usados como sinal de roteamento
#   (vazio x não-vazio) E, desde o RAG real (Qdrant, Fase 2), como contexto
#   injetado no prompt do LLM — decisão registrada em docs/ARCHITECTURE.md
#   §5 (nota após a tabela de escopo); a lógica de decisão local x externo
#   em si não muda;
# - o prompt de sistema por domínio (playbook, Fase 3) é anteposto ao prompt
#   quando há um playbook para o domínio classificado (ver
#   app/router/playbooks.py); `fora_escopo` não tem playbook;
# - não há persistência das decisões do roteador em banco — a tabela
#   `router_logs` é da Fase 6; por ora só o log estruturado;
# - o texto completo da resposta do LLM vai para o log estruturado em nível
#   INFO. Aceitável neste protótipo, mas é uma simplificação deliberada
#   (risco de PII/volume em produção) a revisitar antes de qualquer uso real.


def _build_prompt(
    message: str,
    documentos: list[Document],
    domain: Domain,
    dados_catalogo: str | None = None,
    resumo_conversa: str | None = None,
    pedir_email_pos_venda: bool = False,
    ultima_troca: tuple[str, str] | None = None,
    dados_cliente: str | None = None,
    contexto_conversa_anterior: str | None = None,
    usuario_autenticado: bool = False,
) -> str:
    """Monta o prompt final: prompt de sistema do domínio (playbook) +
    dados do cliente/compras (quando houver, R10 Fase 6/7) +
    contexto da conversa anterior (quando houver) +
    resumo da conversa atual até aqui (quando houver, R9 Fase 6) + dados do
    catálogo de Vendas (quando houver, R12 Fase 5) + contexto de RAG (quando
    houver) + mensagem do cliente.

    # MVP: concatenação simples dos `content` dos documentos, sem
    # sumarização/priorização por score além da ordem já devolvida pelo RAG,
    # e sem truncar por limite de tokens do modelo (ver docs/ARCHITECTURE.md
    # §5). O playbook do domínio (ver app/router/playbooks.py) é anteposto
    # quando existe; `fora_escopo` não tem playbook.
    """
    system_prompt = build_system_prompt(domain, usuario_autenticado=usuario_autenticado)
    partes: list[str] = []
    if system_prompt is not None:
        partes.append(system_prompt)

    if dados_cliente is not None:
        partes.append(dados_cliente)

    if contexto_conversa_anterior:
        partes.append(
            "Contexto da conversa anterior do cliente (use como histórico prévio do cliente; "
            "se a conversa atual tratar de algo novo, priorize o contexto atual):\n"
            f"{wrap_untrusted('entrada_cliente', contexto_conversa_anterior)}"
        )

    if resumo_conversa:
        # O prompt não leva as mensagens anteriores; o resumo periódico é o
        # que dá ao LLM o contexto da conversa (ex.: de que produto se fala).
        partes.append(
            "Resumo da conversa até aqui (use como contexto; se a mensagem "
            f"atual disser algo diferente, ela vale):\n"
            f"{wrap_untrusted('entrada_cliente', resumo_conversa)}"
        )

    if ultima_troca:
        # O resumo só existe a cada 6 mensagens; a troca anterior é o que
        # resolve referências como "o produto acima" ou "e esse?".
        cliente, assistente = ultima_troca
        partes.append(
            "Troca anterior da conversa (use para entender referências como "
            "'o produto acima' ou 'esse'):\n"
            f"Cliente: {wrap_untrusted('entrada_cliente', cliente[:_ULTIMA_RESPOSTA_MAX_CHARS])}\n"
            f"Assistente: {assistente[:_ULTIMA_RESPOSTA_MAX_CHARS]}"
        )

    if dados_catalogo is not None:
        partes.append(dados_catalogo)

    if documentos:
        contexto = "\n\n".join(f"- {documento.content}" for documento in documentos)
        partes.append(
            "Use as informações a seguir, recuperadas da base de conhecimento "
            "da empresa, para responder à mensagem do cliente. Se as "
            "informações não forem suficientes, responda com o que souber, sem "
            "inventar dados específicos (preços, prazos, números de série).\n\n"
            f"Informações recuperadas:\n{wrap_untrusted('contexto_rag', contexto)}"
        )

    if pedir_email_pos_venda and domain in DOMINIOS_POS_VENDA:
        # R10 (Fase 6): identidade pelo e-mail, pedida só no momento natural
        # — no pós-venda, para localizar a compra.
        partes.append(
            "Ainda não sabemos o e-mail do cliente. Se fizer sentido para "
            "localizar a compra dele, peça educadamente, uma única vez, o "
            "e-mail usado na compra."
        )

    partes.append(f"Mensagem do cliente: {wrap_untrusted('entrada_cliente', message)}")
    return "\n\n".join(partes)


_STOP_WORDS_PRODUTO = frozenset(
    {"de", "para", "com", "sem", "em", "do", "da", "dos", "das", "um", "uma", "produto"}
)


def _extrair_produtos_do_contexto(message: str, recent_messages: list[str]) -> list[str]:
    """Extrai nomes/códigos de produtos citados no histórico recente ou na
    mensagem (ex. 'Identifiquei: RC 4102g2.')."""
    texto_total = "\n".join([*recent_messages, message])
    produtos = []
    for m in re.finditer(
        r"(?:Identifiquei|produto|modelo|item):\s*([^\n\.\,\;]+)", texto_total, re.IGNORECASE
    ):
        prod = m.group(1).strip()
        if prod:
            produtos.append(prod)
    return produtos


def _filtrar_documentos_relevantes_ao_contexto(
    documentos: list[Document], message: str, recent_messages: list[str]
) -> list[Document]:
    produtos_contexto = _extrair_produtos_do_contexto(message, recent_messages)
    if not produtos_contexto:
        return documentos

    relevantes = []
    for doc in documentos:
        content_lower = doc.content.lower()
        content_clean = "".join(
            c
            for c in unicodedata.normalize("NFD", content_lower)
            if unicodedata.category(c) != "Mn"
        )
        for prod in produtos_contexto:
            prod_clean = "".join(
                c
                for c in unicodedata.normalize("NFD", prod.lower())
                if unicodedata.category(c) != "Mn"
            )
            if prod_clean in content_clean:
                relevantes.append(doc)
                break
            tokens = [
                t
                for t in re.split(r"[\s\-_,\.]+", prod_clean)
                if len(t) >= 3 and t not in _STOP_WORDS_PRODUTO
            ]
            if tokens and any(t in content_clean for t in tokens):
                relevantes.append(doc)
                break

    return relevantes


# Palavras com que o cliente aponta para algo da troca anterior ("o produto
# acima", "e esse?", "detalhes dele"). Com uma delas, a busca no RAG usa
# também a última resposta, que traz o nome do produto (correção de
# 2026-09-27: sem isso, a busca só pela frase trazia o manual de outro
# produto).
_REFERENCIA_ANTERIOR_RE = re.compile(
    r"\b(acima|anterior|esse|essa|este|esta|desse|dessa|deste|desta|nesse|"
    r"nessa|neste|nesta|dele|dela|isso|disso|mesmo produto)\b",
    re.IGNORECASE,
)
# Quanto da última resposta entra na busca e no prompt.
_ULTIMA_RESPOSTA_MAX_CHARS = 600


def e_referencia_anterior(message: str) -> bool:
    return _REFERENCIA_ANTERIOR_RE.search(message) is not None


async def _buscar_documentos_rag(
    message: str,
    recent_messages: list[str],
    domain: str,
    rag_client: RAGClient,
    ultima_resposta: str | None = None,
    top_k: int = 3,
    score_threshold: float = 0.35,
) -> list[Document]:
    termos = extrair_termos_busca(message)
    if ultima_resposta and e_referencia_anterior(message):
        # "possui detalhes do produto acima?": o produto está na resposta
        # anterior (ex.: "Identifiquei: Rádio … RC 4102g2."), não na frase.
        texto_busca = f"{ultima_resposta[:_ULTIMA_RESPOSTA_MAX_CHARS]}\n{message}"
    elif not termos and recent_messages:
        texto_busca = "\n".join([*recent_messages, message])
    else:
        texto_busca = message

    documentos = await rag_client.search(
        texto_busca, domain, top_k=top_k, score_threshold=score_threshold
    )
    if not documentos and recent_messages and texto_busca == message:
        texto_busca_fallback = "\n".join([*recent_messages, message])
        documentos = await rag_client.search(
            texto_busca_fallback, domain, top_k=top_k, score_threshold=score_threshold
        )

    # O filtro por produto citado no contexto precisa enxergar a última
    # resposta: é nela que está o "Identifiquei: X" da identificação por
    # imagem (as mensagens recentes são só as do cliente).
    contexto = [*recent_messages, ultima_resposta] if ultima_resposta else recent_messages
    return _filtrar_documentos_relevantes_ao_contexto(documentos, message, contexto)


async def _buscar_candidatos_com_historico(
    message: str,
    recent_messages: list[str],
    sales_catalog_client: SalesCatalogClient,
) -> tuple[list, list[str], list[str]]:
    """Retorna (candidatos, termos, termos_historico). Candidatos da mensagem
    atual vêm primeiro; os do histórico completam até SALES_CANDIDATOS_LIMITE."""
    termos = extrair_termos_busca(message)
    termos_historico = [
        t for t in extrair_termos_busca(" ".join(recent_messages)) if t not in termos
    ]
    candidatos = await sales_catalog_client.buscar_candidatos(termos) if termos else []
    if termos_historico and len(candidatos) < SALES_CANDIDATOS_LIMITE:
        ids_atuais = {c.id for c in candidatos}
        candidatos += [
            c
            for c in await sales_catalog_client.buscar_candidatos(termos_historico)
            if c.id not in ids_atuais
        ]
        candidatos = candidatos[:SALES_CANDIDATOS_LIMITE]
    return candidatos, termos, termos_historico


async def _resolver_sem_produto_especifico(
    slots: Any,
    sales_catalog_client: SalesCatalogClient,
    diagnostico: dict,
) -> DadosCatalogoVendas | DadosCatalogoCategoria | None:
    """Resolve consultas sem produto_id: por categoria ou listagem completa."""
    if slots.categoria is not None:
        dados_categoria = await sales_catalog_client.consultar_categoria(slots.categoria)
        if dados_categoria is None:
            return _logar_consulta_vendas(diagnostico, "categoria_vazia")
        diagnostico["bloco"] = _formatar_dados_catalogo_categoria(dados_categoria)
        _logar_consulta_vendas(diagnostico, "ok_categoria")
        return dados_categoria
    if slots.listar_tudo:
        dados_todos = await sales_catalog_client.listar_todos_produtos()
        if dados_todos is None:
            return _logar_consulta_vendas(diagnostico, "catalogo_vazio")
        diagnostico["bloco"] = _formatar_dados_catalogo_categoria(dados_todos)
        _logar_consulta_vendas(diagnostico, "ok_listar_tudo")
        return dados_todos
    return _logar_consulta_vendas(diagnostico, "llm_sem_produto")


async def _consultar_vendas(
    message: str,
    recent_messages: list[str],
    sales_catalog_client: SalesCatalogClient,
    local_client: LLMClient,
    ultima_resposta: str | None = None,
) -> DadosCatalogoVendas | DadosCatalogoCategoria | None:
    """Busca de candidatos + desambiguação por LLM + detalhes do catálogo
    para uma mensagem de Vendas. Nunca levanta exceção — falhas logam e
    devolvem `None` (mesmo espírito de `analyze_tone`)."""
    diagnostico: dict = {"event": "vendas_catalogo_consulta"}
    if ultima_resposta:
        recent_messages = [*recent_messages, ultima_resposta[:_ULTIMA_RESPOSTA_MAX_CHARS]]
    try:
        candidatos, termos, termos_historico = await _buscar_candidatos_com_historico(
            message, recent_messages, sales_catalog_client
        )
        diagnostico["termos"] = termos
        diagnostico["termos_historico"] = termos_historico
        if not termos and not termos_historico:
            return _logar_consulta_vendas(diagnostico, "sem_termos")
        diagnostico["candidatos"] = [c.nome for c in candidatos]
        # Sempre segue para o LLM mesmo sem candidatos — ele decide entre
        # produto/categoria/listar_tudo (correção de 2026-09-29).
        categorias_disponiveis = await sales_catalog_client.listar_categorias()
        slots = await extract_sales_slots(
            message, recent_messages, candidatos, local_client, categorias_disponiveis
        )
        diagnostico["slots"] = slots.model_dump()
        if slots.produto_id is None:
            return await _resolver_sem_produto_especifico(slots, sales_catalog_client, diagnostico)
        dados = await sales_catalog_client.consultar_detalhes(
            slots.produto_id, slots.produto_relacionado_id, slots.quantidade
        )
        if dados is None:
            return _logar_consulta_vendas(diagnostico, "produto_inexistente")
        diagnostico["bloco"] = _formatar_dados_catalogo_vendas(dados)
        _logar_consulta_vendas(diagnostico, "ok")
        return dados
    except Exception as exc:
        logger.warning(
            "vendas_catalogo_consulta_falhou",
            extra={"router": {"event": "vendas_catalogo_consulta_falhou", "erro": str(exc)}},
        )
        return None


def _logar_consulta_vendas(diagnostico: dict, resultado: str) -> None:
    """Uma linha de log por consulta de vendas, dizendo em qual etapa ela
    parou (`resultado`) e o que cada etapa viu (termos, candidatos, slots do
    LLM, bloco injetado no prompt) — o prompt final não sai na resposta
    SSE, então é por aqui que o teste manual confirma o que o LLM recebeu.
    Devolve `None` para servir de `return` nas saídas antecipadas."""
    logger.info(
        "vendas_catalogo_consulta",
        extra={"router": {**diagnostico, "resultado": resultado}},
    )


# MVP: descrição e ficha técnica truncadas (sem resumo) para o bloco não
# tomar o prompt do modelo local.
_FICHA_MAX_CHARS = 1500


def _truncar_ficha(texto: str) -> str:
    texto = texto.strip()
    if len(texto) <= _FICHA_MAX_CHARS:
        return texto
    return texto[:_FICHA_MAX_CHARS].rstrip() + "…"


def _formatar_dados_catalogo_vendas(dados: DadosCatalogoVendas) -> str:
    # O cabeçalho diz ao LLM que estes dados valem mais que os trechos do RAG:
    # sem ele, no teste local de 2026-09-25 (cenário V8, "E se eu levar 5
    # unidades?" depois de perguntar do GD-15) o modelo respondeu com preço
    # e nome do GD-60 tirados de um trecho do RAG, ignorando o bloco. O prompt
    # final não leva o histórico da conversa, então o bloco é a única fonte do
    # produto de que se está falando.
    # Descrição e ficha técnica vêm antes de estoque/cotação, e o cabeçalho
    # manda responder o que foi perguntado (correção de 2026-09-27: pedindo
    # detalhes, o LLM respondia sobre preço e estoque).
    linhas = [
        "Dados oficiais do catálogo interno, já calculados para esta mensagem. "
        "O cliente está falando deste produto: use exatamente estes nomes, "
        "valores e quantidades, e prefira-os a qualquer informação recuperada "
        "abaixo que seja diferente. Responda o que o cliente perguntou: se ele "
        "pediu detalhes, dados técnicos ou características, use a descrição "
        "comercial e as especificações técnicas, e só fale de preço e estoque "
        "se ele perguntou por eles. Se ele perguntar pelo estoque de um "
        "centro de distribuição específico, ou pedir o estoque 'por CD'/'por "
        "centro de distribuição', responda com o detalhamento por CD abaixo, "
        "não com o total somado.",
        f"Dados do catálogo interno (produto identificado: {dados.produto_nome}):",
    ]
    if dados.descricao:
        linhas.append(f"- Descrição comercial: {_truncar_ficha(dados.descricao)}")
    if dados.especificacoes_tecnicas:
        linhas.append(f"- Especificações técnicas: {_truncar_ficha(dados.especificacoes_tecnicas)}")
    if dados.dimensoes_cm:
        linhas.append(f"- Dimensões (cm): {dados.dimensoes_cm}")
    if dados.peso_kg is not None:
        linhas.append(f"- Peso: {dados.peso_kg} kg")
    linhas.append(f"- Estoque disponível: {dados.estoque_total} unidade(s)")
    if dados.estoque_por_cd:
        # Correção de 2026-09-29: sem o detalhe por CD aqui, "quanto tem no
        # CD-SP?"/"estoque por centro de distribuição?" não tinha como ser
        # respondido — o LLM só via o total e o repetia como se fosse de um
        # único centro.
        detalhamento = ", ".join(
            f"{item.centro_distribuicao}: {item.quantidade} unidade(s)"
            for item in dados.estoque_por_cd
        )
        linhas.append(f"- Estoque por centro de distribuição: {detalhamento}")
    if dados.cotacao is not None:
        preco_unitario, percentual, subtotal = dados.cotacao
        linha_cotacao = f"- Cotação para {dados.quantidade} unidade(s): R$ {subtotal}"
        if percentual > Decimal("0"):
            linha_cotacao += (
                f" ({percentual}% de desconto aplicado sobre R$ {preco_unitario}/unidade)"
            )
        linhas.append(linha_cotacao)
        # Achado de 2026-10-13: com o estoque "CD-RJ: 2 unidades" no mesmo
        # bloco, o modelo local trocou a quantidade pedida (1) pelo estoque
        # do CD (2) no texto, enquanto o card mostrava 1. Como o prompt final
        # não leva o histórico, esta linha é a única fonte da quantidade.
        linhas.append(
            f"- Quantidade do pedido do cliente: {dados.quantidade} unidade(s). "
            "Esta é a quantidade que ele quer comprar; os números de estoque "
            "(total ou por centro de distribuição) são só disponibilidade e "
            "nunca a quantidade do pedido."
        )
    if dados.compativel is not None:
        compat_texto = "sim" if dados.compativel else "não"
        linhas.append(f"- Compatível com {dados.produto_relacionado_nome}: {compat_texto}")
    return "\n".join(linhas)


def _formatar_dados_catalogo_categoria(dados: DadosCatalogoCategoria) -> str:
    # Consulta genérica por categoria ("quais geradores vocês têm em
    # estoque?") ou por todo o catálogo ("quais produtos vocês têm em
    # estoque?", correção de 2026-09-29, `categoria=None`): lista cada
    # produto (da categoria, ou de todo o catálogo) com preço e estoque.
    # Mesmo cabeçalho de "prefira estes dados ao RAG" do bloco de produto
    # único, pelo mesmo motivo (evitar que o LLM misture preços/nomes de
    # trechos do RAG).
    cabecalho_produtos = (
        "Todos os produtos do catálogo interno:"
        if dados.categoria is None
        else f"Produtos da categoria '{dados.categoria}' no catálogo interno:"
    )
    linhas = [
        "Dados oficiais do catálogo interno, já calculados para esta mensagem. "
        "O cliente perguntou pelos produtos disponíveis: use exatamente estes "
        "nomes, preços e quantidades de estoque, e prefira-os a qualquer "
        "informação recuperada abaixo que seja diferente.",
        cabecalho_produtos,
    ]
    for produto in dados.produtos:
        linhas.append(
            f"- {produto.nome}: R$ {produto.preco}/unidade, "
            f"{produto.estoque_total} unidade(s) em estoque"
        )
    return "\n".join(linhas)


def _formatar_bloco_catalogo_vendas(
    dados: DadosCatalogoVendas | DadosCatalogoCategoria | None,
) -> str | None:
    """Despacha para o formatador certo conforme o tipo de consulta de
    Vendas (produto único x listagem por categoria) — os dois blocos entram
    no prompt pelo mesmo parâmetro `dados_catalogo` de `_build_prompt`."""
    if dados is None:
        return None
    if isinstance(dados, DadosCatalogoCategoria):
        return _formatar_dados_catalogo_categoria(dados)
    return _formatar_dados_catalogo_vendas(dados)


def _construir_card_vendas(
    dados: DadosCatalogoVendas | DadosCatalogoCategoria | None,
) -> ChatCard | None:
    """Card rico (Fase 8, correção de 2026-09-29) a partir do mesmo
    resultado de `_consultar_vendas` já usado no bloco de texto do prompt —
    sem chamada extra ao banco. `DadosCatalogoCategoria` (listagem por
    categoria ou catálogo completo) ainda não vira card, só produto único
    (`# MVP`, ver docs/ARCHITECTURE.md §5); `produto_id`/`preco` ausentes
    (não deveria acontecer fora de teste, ver `DadosCatalogoVendas`) também
    não viram card."""
    if not isinstance(dados, DadosCatalogoVendas):
        return None
    if dados.produto_id is None:
        return None
    if dados.cotacao is not None:
        preco_unitario, percentual, subtotal = dados.cotacao
        return CardCotacao(
            produto_id=dados.produto_id,
            nome=dados.produto_nome,
            quantidade=dados.quantidade or 0,
            preco_unitario=preco_unitario,
            percentual_desconto=percentual,
            subtotal=subtotal,
        )
    if dados.preco is None:
        return None
    return CardProduto(
        produto_id=dados.produto_id,
        nome=dados.produto_nome,
        preco=dados.preco,
        imagem_url=dados.imagem_url,
        estoque_total=dados.estoque_total,
    )


async def _construir_card_documento_download(
    db_sessionmaker: async_sessionmaker[AsyncSession] | None,
    documentos: list[Document],
    domain: str,
    threshold: float,
) -> ChatCard | None:
    """Card rico de download do documento-fonte quando o melhor chunk do
    RAG bate com confiança alta (Fase 8, além do MVP) — ver
    docs/superpowers/specs/2026-10-04-download-documentos-rag-chat-design.md.
    Só emite para documentos de collections purpose="chat": é a única
    combinação em que o link de download (endpoint público, ver
    docs/ARCHITECTURE.md §7) funciona sem token para quem está vendo o
    chat. Nunca levanta — mesmo espírito de `_consultar_vendas`/
    `analyze_tone`: qualquer falha aqui não pode derrubar o turno."""
    if not documentos or db_sessionmaker is None:
        return None
    melhor_chunk = max(documentos, key=lambda d: d.score)
    if melhor_chunk.score < threshold:
        return None
    try:
        async with db_sessionmaker() as session:
            resultado = await session.execute(
                select(RagDocument)
                .join(RagCollection, RagDocument.collection_id == RagCollection.id)
                .where(
                    RagDocument.filename == melhor_chunk.source,
                    RagDocument.domain == domain,
                    RagCollection.purpose == "chat",
                )
                .order_by(RagDocument.created_at.desc())
                .limit(1)
            )
            # MVP: casamento por filename+domain, não por document_id — o
            # `Document` devolvido por `RAGClient.search` não carrega
            # document_id, só o filename em `source` (ver
            # app/router/rag_client.py / app/rag/qdrant_client.py). O join
            # com `RagCollection` e o filtro por `purpose="chat"` já
            # resolvem a ambiguidade de `reingest_document` (app/rag/
            # ingest.py) criar uma nova linha com o mesmo filename+domain em
            # outra collection — duplicatas entre collections são estado
            # normal, não um corner case (achado importante 1 da revisão
            # final). `order_by(created_at desc)` é só o critério de
            # desempate caso ainda sobre mais de uma linha `purpose="chat"`.
            doc = resultado.scalar_one_or_none()
            if doc is None or not doc.storage_path:
                return None
            try:
                # Intencionalmente mais estrito que a cadeia de fallback do
                # endpoint de download (`download_document_endpoint`, app/
                # api/rag.py): aqui só `storage_path` é checado, sem tentar
                # `uploads_dir / filename` nem `uploads_dir /
                # f"{id}_{filename}"`. Um documento cujo arquivo só resolve
                # via fallback simplesmente não ganha card — nunca um link
                # morto no chat (achado menor 4 da revisão final).
                file_size = Path(doc.storage_path).stat().st_size
            except OSError:
                return None
            return CardDocumentoDownload(
                documento_id=str(doc.id),
                filename=doc.filename,
                domain=doc.domain,
                score=melhor_chunk.score,
                download_url=f"/api/rag/documents/{doc.id}/download",
                file_size_bytes=file_size,
            )
    except Exception:
        logger.exception(
            "documento_download_card_falhou",
            extra={
                "router": {
                    "event": "documento_download_card_falhou",
                    "domain": domain,
                    "score": melhor_chunk.score,
                }
            },
        )
        return None


class RouterDecision(BaseModel):
    domain: str
    complexity: str
    confidence: float
    complexity_strategy_usada: str
    backend_escolhido: str  # "local" | "externo"
    motivo_escalonamento: str  # "fora_escopo" | "rag_vazio" | "complexidade_alta" | "nenhum"
    # | (agendamento) "coleta_dados" | "horario_invalido" | "aguardando_confirmacao"
    # | "confirmado" | "mcp_indisponivel"
    resposta: str
    latencia_ms: float
    tokens_entrada: int | None
    tokens_saida: int | None
    cost_prompt_usd: float = 0.0
    cost_completion_usd: float = 0.0
    custo_estimado_usd: float
    modelo_usado: str | None = None
    ttft_ms: float | None = None
    tps: float | None = None
    rag_retrieval_ms: float | None = None
    rag_chunks_count: int | None = None
    rag_avg_score: float | None = None
    rag_chunks: list[RagChunkMetric] | None = None
    router_provider: str = DEFAULT_INTENT_ROUTER_PROVIDER
    # Card rico (Fase 8, correção de 2026-09-29) — produto/cotação (Vendas)
    # ou confirmação de agendamento; None na maioria dos turnos.
    card: ChatCard | None = None


class StatusEvent(BaseModel):
    status: str


class TokenEvent(BaseModel):
    text: str


class EscalonamentoEvent(BaseModel):
    # Mesmo tipo de ToneResult.motivo (tone_monitor.py) — o valor vem direto
    # de tone_result.motivo, sem transformação (revisão final, achado
    # menor 5).
    motivo: Literal["urgencia", "insatisfacao"] | None
    confianca: float
    provider_efetivo: str


class LocalBackendIndisponivelError(Exception):
    """Falha de infraestrutura no backend local (Ollama) — sem fallback automático."""


class ExternalBackendIndisponivelError(Exception):
    """Falha de infraestrutura no backend externo (OpenRouter) — sem fallback automático."""


class _AgendamentoFalhaValidacao(Exception):
    """Carrega a resposta já pronta para o visitante quando
    `_validar_horario_para_agendamento` falha — motivo é sempre
    "horario_invalido" (expediente ou conflito de agenda) ou
    "mcp_indisponivel" (falha ao consultar disponibilidade)."""

    def __init__(self, texto: str, motivo: str) -> None:
        self.texto = texto
        self.motivo = motivo
        super().__init__(texto)


async def _validar_horario_para_agendamento(
    slots: BookingSlots,
    scheduling_config: SchedulingConfig,
    calendar_client: CalendarClient,
) -> datetime:
    """Valida expediente e disponibilidade de agenda para `slots.data_hora`.

    Devolve o `datetime` com fuso horário aplicado (mesmo valor devolvido por
    `validar_expediente`, para persistir de volta em `slots.data_hora` — sem
    isso, um `datetime` naive chegaria às chamadas do MCP, ver Fix 3). Em
    falha, levanta `_AgendamentoFalhaValidacao` já com o texto de resposta e
    o motivo de escalonamento prontos.

    Compartilhado pelos dois pontos do fluxo que precisam desta validação: a
    validação original antes de pedir confirmação, E a revalidação
    obrigatória logo antes de `create_event`, mesmo quando a mensagem atual
    confirma — uma confirmação que também muda a data (ou uma confirmação
    tardia sobre um horário que ficou stale) não pode pular a checagem de
    expediente/conflito só porque `slots.awaiting_confirmation` já era
    `True`.
    """
    try:
        dh = validar_expediente(slots.data_hora, scheduling_config)
    except HorarioInvalidoError as exc:
        raise _AgendamentoFalhaValidacao(exc.motivo, "horario_invalido") from exc

    fim = dh + DURACAO_VISITA
    try:
        disponivel = await calendar_client.is_time_available(dh, fim)
    except GoogleCalendarConnectionError as exc:
        logger.error(
            "google_calendar_indisponivel",
            extra={
                "router": {
                    "event": "google_calendar_indisponivel",
                    "etapa": "checagem_disponibilidade",
                    "erro": str(exc),
                }
            },
        )
        raise _AgendamentoFalhaValidacao(MSG_ERRO_MCP, "mcp_indisponivel") from exc

    if not disponivel:
        raise _AgendamentoFalhaValidacao(
            "Esse horário já está reservado. Pode sugerir outro horário?", "horario_invalido"
        )
    return dh


async def _emitir_resposta_agendamento(
    texto: str,
    motivo: str,
    *,
    intent_router_provider: str,
    card: CardAgendamento | None = None,
) -> AsyncIterator[TokenEvent | RouterDecision]:
    yield TokenEvent(text=texto)
    yield RouterDecision(
        domain="agendamento",
        complexity="baixa",
        confidence=1.0,
        complexity_strategy_usada="agendamento",
        backend_escolhido="local",
        motivo_escalonamento=motivo,
        resposta=texto,
        latencia_ms=0.0,
        tokens_entrada=None,
        tokens_saida=None,
        cost_prompt_usd=0.0,
        cost_completion_usd=0.0,
        custo_estimado_usd=0.0,
        router_provider=intent_router_provider,
        card=card,
    )


async def _persistir_agendamento(
    slots: BookingSlots,
    fim: datetime,
    google_event_id: str | None,
    google_event_link: str | None,
    conversation_id: str,
    db_sessionmaker: async_sessionmaker[AsyncSession] | None,
) -> None:
    """Persiste o agendamento confirmado no banco; erros são logados e ignorados."""
    if db_sessionmaker is None:
        return
    try:
        async with db_sessionmaker() as session:
            agendamento = Agendamento(
                user_email=slots.email,
                nome_cliente=slots.nome,
                telefone=slots.telefone,
                data_hora_inicio=slots.data_hora,
                data_hora_fim=fim,
                descricao=f"Telefone: {slots.telefone}",
                status="confirmado",
                origem="chat",
                google_event_id=google_event_id or None,
                google_event_link=google_event_link or None,
                conversation_id=conversation_id,
            )
            session.add(agendamento)
            await session.commit()
    except Exception as exc:
        logger.error(
            "erro_ao_persistir_agendamento",
            extra={
                "router": {
                    "event": "erro_ao_persistir_agendamento",
                    "erro": str(exc),
                    "conversation_id": conversation_id,
                }
            },
        )


async def _confirmar_agendamento(
    slots: BookingSlots,
    conversation_id: str,
    calendar_client: CalendarClient,
    scheduling_config: SchedulingConfig,
    intent_router_provider: str,
    db_sessionmaker: async_sessionmaker[AsyncSession] | None,
) -> AsyncIterator[TokenEvent | RouterDecision]:
    """Revalida horário, cria evento no Calendar, persiste e emite resposta de sucesso.
    Yields eventos de falha se a validação ou criação do evento falhar.
    Retorna True via StopAsyncIteration quando concluído (sucesso ou falha)."""
    # Fix (revisão final, achado crítico 1): revalida mesmo já confirmado —
    # merge_slots pode ter mudado data_hora neste mesmo turno.
    try:
        slots.data_hora = await _validar_horario_para_agendamento(
            slots, scheduling_config, calendar_client
        )
    except _AgendamentoFalhaValidacao as falha:
        if falha.motivo == "horario_invalido":
            slots.data_hora = None
        slots.awaiting_confirmation = False
        set_booking_slots(conversation_id, slots)
        async for evento in _emitir_resposta_agendamento(
            falha.texto, falha.motivo, intent_router_provider=intent_router_provider
        ):
            yield evento
        return

    fim = slots.data_hora + DURACAO_VISITA
    try:
        google_event_id, google_event_link = await calendar_client.create_event(
            summary=f"Visita — {slots.nome}",
            start=slots.data_hora,
            end=fim,
            attendee_email=slots.email,
            attendee_name=slots.nome,
            description=f"Telefone: {slots.telefone}",
        )
    except GoogleCalendarConnectionError as exc:
        logger.error(
            "google_calendar_indisponivel",
            extra={
                "router": {
                    "event": "google_calendar_indisponivel",
                    "etapa": "criacao_evento",
                    "erro": str(exc),
                }
            },
        )
        slots.awaiting_confirmation = False
        set_booking_slots(conversation_id, slots)
        async for evento in _emitir_resposta_agendamento(
            MSG_ERRO_MCP, "mcp_indisponivel", intent_router_provider=intent_router_provider
        ):
            yield evento
        return

    await _persistir_agendamento(
        slots, fim, google_event_id, google_event_link, conversation_id, db_sessionmaker
    )
    texto = mensagem_sucesso(slots, scheduling_config.timezone)
    clear_booking_slots(conversation_id)
    card = CardAgendamento(
        data_hora_inicio=slots.data_hora,
        data_hora_fim=fim,
        google_event_link=google_event_link or None,
    )
    async for evento in _emitir_resposta_agendamento(
        texto, "confirmado", intent_router_provider=intent_router_provider, card=card
    ):
        yield evento


async def _extrair_slots_agendamento(
    message: str,
    recent_messages: list[str],
    slots: BookingSlots,
    local_client: LLMClient,
    scheduling_config: SchedulingConfig,
) -> Any:
    """Extrai slots via LLM local; falha vira `LocalBackendIndisponivelError`."""
    try:
        return await extract_booking_slots(
            message, recent_messages, slots, local_client, scheduling_config.timezone
        )
    except Exception as exc:
        logger.error(
            "backend_indisponivel",
            extra={
                "router": {
                    "event": "backend_indisponivel",
                    "backend": "local",
                    "etapa": "extracao_agendamento",
                    "erro": str(exc),
                }
            },
        )
        raise LocalBackendIndisponivelError(str(exc)) from exc


async def _handle_agendamento(
    conversation_id: str,
    message: str,
    recent_messages: list[str],
    local_client: LLMClient,
    calendar_client: CalendarClient,
    scheduling_config: SchedulingConfig,
    intent_router_provider: str,
    db_sessionmaker: async_sessionmaker[AsyncSession] | None = None,
) -> AsyncIterator[TokenEvent | RouterDecision]:
    slots = get_booking_slots(conversation_id)
    extraction = await _extrair_slots_agendamento(
        message, recent_messages, slots, local_client, scheduling_config
    )
    slots = merge_slots(slots, extraction)

    if not slots.is_complete():
        set_booking_slots(conversation_id, slots)
        async for evento in _emitir_resposta_agendamento(
            mensagem_campos_faltando(slots),
            "coleta_dados",
            intent_router_provider=intent_router_provider,
        ):
            yield evento
        return

    if slots.awaiting_confirmation and extraction.confirmacao:
        async for evento in _confirmar_agendamento(
            slots,
            conversation_id,
            calendar_client,
            scheduling_config,
            intent_router_provider,
            db_sessionmaker,
        ):
            yield evento
        return
    # Resposta ambígua durante awaiting_confirmation=True: volta a "não
    # confirmado ainda" para cair na validação abaixo NO MESMO turno
    # (spec §4.1 passo 7).
    slots.awaiting_confirmation = False

    try:
        slots.data_hora = await _validar_horario_para_agendamento(
            slots, scheduling_config, calendar_client
        )
    except _AgendamentoFalhaValidacao as falha:
        if falha.motivo == "horario_invalido":
            slots.data_hora = None
        set_booking_slots(conversation_id, slots)
        async for evento in _emitir_resposta_agendamento(
            falha.texto,
            falha.motivo,
            intent_router_provider=intent_router_provider,
        ):
            yield evento
        return

    slots.awaiting_confirmation = True
    set_booking_slots(conversation_id, slots)
    async for evento in _emitir_resposta_agendamento(
        mensagem_pedir_confirmacao(slots, scheduling_config.timezone),
        "aguardando_confirmacao",
        intent_router_provider=intent_router_provider,
    ):
        yield evento


async def _checar_modelo_local(
    local_client: LLMClient,
    intent_router_provider: str,
    tone_monitor_enabled: bool,
    tone_monitor_provider: str,
) -> AsyncIterator[StatusEvent]:
    """Emite `carregando_modelo` se o modelo local ainda não está quente."""
    deve_checar = (intent_router_provider == "heuristica_llm") or (
        tone_monitor_enabled and tone_monitor_provider == DEFAULT_TONE_MONITOR_PROVIDER
    )
    if not deve_checar:
        return
    try:
        modelo_pronto = await local_client.is_model_ready()
    except Exception as exc:
        logger.warning(
            "verificacao_modelo_local_falhou",
            extra={"router": {"event": "verificacao_modelo_local_falhou", "erro": str(exc)}},
        )
        modelo_pronto = True
    if not modelo_pronto:
        yield StatusEvent(status="carregando_modelo")


async def _handle_tone_e_classify(
    message: str,
    recent_messages: list[str],
    local_client: LLMClient,
    external_client: LLMClient,
    complexity_strategy: str,
    intent_router_provider: str,
    tone_monitor_enabled: bool,
    tone_monitor_provider: str,
    ultima_troca: tuple[str, str] | None,
) -> tuple[Any, Any]:
    """Roda tom e classificação em paralelo. Levanta `LocalBackendIndisponivelError` se
    `classify()` falhar."""
    tone_coro = (
        analyze_tone(
            message=message,
            recent_messages=recent_messages,
            strategy_provider=tone_monitor_provider,
            llm_client=local_client,
            external_client=external_client,
        )
        if tone_monitor_enabled
        else _sem_analise_de_tom()
    )
    try:
        async with asyncio.TaskGroup() as tg:
            tone_task = tg.create_task(tone_coro)
            classification_task = tg.create_task(
                classify(
                    message=message,
                    recent_messages=recent_messages,
                    strategy=complexity_strategy,
                    llm_client=local_client,
                    provider=intent_router_provider,
                    external_client=external_client,
                    ultima_resposta=ultima_troca[1] if ultima_troca else None,
                )
            )
    except* Exception as eg:
        exc = eg.exceptions[0]
        logger.error(
            "backend_indisponivel",
            extra={
                "router": {
                    "event": "backend_indisponivel",
                    "backend": "local",
                    "etapa": "classificacao",
                    "erro": str(exc),
                }
            },
        )
        raise LocalBackendIndisponivelError(str(exc)) from exc
    return tone_task.result(), classification_task.result()


def _emitir_chart_decision_base(
    intent_router_provider: str, tokens_entrada: int | None, tokens_saida: int | None
) -> dict:
    return dict(
        complexity="baixa",
        confidence=1.0,
        complexity_strategy_usada="regras",
        backend_escolhido="local",
        motivo_escalonamento="nenhum",
        latencia_ms=0.0,
        cost_prompt_usd=0.0,
        cost_completion_usd=0.0,
        custo_estimado_usd=0.0,
        domain="atendimento",
        router_provider=intent_router_provider,
        tokens_entrada=tokens_entrada,
        tokens_saida=tokens_saida,
    )


async def _emitir_eventos_chart(
    chart: Any,
    explicacao: str,
    intent_router_provider: str,
    chart_prompt_tokens: int | None,
    chart_completion_tokens: int | None,
) -> AsyncIterator[TokenEvent | RouterDecision]:
    """Emite os eventos SSE para um resultado de gráfico já processado."""
    base = _emitir_chart_decision_base(
        intent_router_provider, chart_prompt_tokens, chart_completion_tokens
    )
    if chart:
        texto = explicacao or (
            f"Gerei o gráfico '{chart.titulo}' para você com base nos dados mais recentes. "
            "Ele já está salvo no seu painel de Dashboards."
        )
        yield TokenEvent(text=texto)
        yield RouterDecision(
            **base,
            resposta=texto,
            card=CardGrafico(
                chart_id=str(chart.id),
                titulo=chart.titulo,
                tipo_grafico=chart.tipo_grafico,
                config=chart.config_json,
                dados=chart.dados_json,
                fixado=chart.fixado,
            ),
        )
        return
    if explicacao:
        yield TokenEvent(text=explicacao)
        yield RouterDecision(**base, resposta=explicacao)


async def _emitir_chart_somente_admin(
    intent_router_provider: str,
) -> AsyncIterator[TokenEvent | RouterDecision]:
    msg = (
        "A geração de gráficos e dashboards é um recurso exclusivo para "
        "administradores autenticados. Faça login como administrador para "
        "gerar e visualizar gráficos dinâmicos."
    )
    yield TokenEvent(text=msg)
    yield RouterDecision(
        domain="fora_escopo",
        complexity="baixa",
        confidence=1.0,
        complexity_strategy_usada="regras",
        backend_escolhido="local",
        motivo_escalonamento="fora_escopo",
        resposta=msg,
        latencia_ms=0.0,
        tokens_entrada=None,
        tokens_saida=None,
        cost_prompt_usd=0.0,
        cost_completion_usd=0.0,
        custo_estimado_usd=0.0,
        router_provider=intent_router_provider,
    )


async def _gerar_chart(
    message: str,
    user_email: str | None,
    local_client: LLMClient,
    external_client: LLMClient,
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> tuple[Any, str, int | None, int | None]:
    """Gera o gráfico; falha interna vira explicação amigável (sem chart)."""
    from app.services.analytics_agent import process_dynamic_chart_request

    try:
        analytics_llm = local_client if local_client is not None else external_client
        ambiente = "interno" if analytics_llm is local_client else "externo"
        async with db_sessionmaker() as session:
            return await process_dynamic_chart_request(
                session=session,
                prompt=message,
                user_email=user_email or "admin",
                llm_client=analytics_llm,
                ambiente=ambiente,
            )
    except Exception as exc:
        logger.error("falha_ao_gerar_grafico_chat", extra={"erro": str(exc)})
        explicacao = (
            "Não consegui gerar esse gráfico agora por uma falha interna. "
            "Tente novamente em instantes."
        )
        return None, explicacao, None, None


async def _handle_chart_request(
    message: str,
    is_admin: bool,
    user_email: str | None,
    local_client: LLMClient,
    external_client: LLMClient,
    db_sessionmaker: async_sessionmaker[AsyncSession] | None,
    intent_router_provider: str,
) -> AsyncIterator[TokenEvent | RouterDecision]:
    """Processa pedidos de gráfico dinâmico (admin). Yields eventos e retorna
    após o primeiro yield bem-sucedido; não yields nada se não for pedido de gráfico."""
    from app.router.sales_catalog import detectar_intencao_comprovante
    from app.services.analytics_agent import extract_prompt_inline_data
    from app.services.chart_generator import detect_chart_request

    if detectar_intencao_comprovante(message):
        return
    if not (detect_chart_request(message) or extract_prompt_inline_data(message)):
        return

    if not is_admin:
        async for evento in _emitir_chart_somente_admin(intent_router_provider):
            yield evento
        return

    if not db_sessionmaker:
        return

    chart, explicacao, chart_prompt_tokens, chart_completion_tokens = await _gerar_chart(
        message, user_email, local_client, external_client, db_sessionmaker
    )

    async for evento in _emitir_eventos_chart(
        chart, explicacao, intent_router_provider, chart_prompt_tokens, chart_completion_tokens
    ):
        yield evento


_PEDIDO_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _extrair_pedido_uuid(message: str) -> str | None:
    match = _PEDIDO_UUID_RE.search(message)
    return match.group(0) if match else None


def _tokens_do_parecer(parecer: Any) -> dict[str, int | None]:
    return {
        "tokens_entrada": parecer.prompt_tokens if parecer else None,
        "tokens_saida": parecer.completion_tokens if parecer else None,
    }


async def _handle_comprovante(
    message: str,
    conversation_id: str,
    user_email: str | None,
    local_client: LLMClient,
    external_client: LLMClient,
    db_sessionmaker: async_sessionmaker[AsyncSession] | None,
    intent_router_provider: str,
    comprovante_bytes: bytes | None,
    comprovante_filename: str | None,
) -> AsyncIterator[TokenEvent | RouterDecision]:
    """Processa conversão de reserva em venda via comprovante. Yields eventos
    se houver reserva ativa; não yields nada caso contrário."""
    from app.router.sales_catalog import (
        buscar_reserva_ativa,
        detectar_intencao_comprovante,
        processar_conversao_comprovante,
    )

    if not detectar_intencao_comprovante(message) or not db_sessionmaker:
        return

    _decision_base: dict = dict(
        domain="vendas",
        complexity="baixa",
        confidence=1.0,
        complexity_strategy_usada="regras",
        backend_escolhido="local",
        motivo_escalonamento="vendas_comprovante_pagamento",
        latencia_ms=0.0,
        cost_prompt_usd=0.0,
        cost_completion_usd=0.0,
        custo_estimado_usd=0.0,
        router_provider=intent_router_provider,
    )
    try:
        pedido_uuid = _extrair_pedido_uuid(message)
        llm_to_use = local_client if local_client is not None else external_client

        async with db_sessionmaker() as session:
            pedido = await buscar_reserva_ativa(
                session=session,
                conversation_id=conversation_id,
                user_email=user_email,
                pedido_id=pedido_uuid,
            )
            if not pedido:
                async for ev in _emitir_comprovante_sem_reserva(_decision_base):
                    yield ev
                return
            sucesso, texto_resp, parecer_res = await processar_conversao_comprovante(
                session=session,
                pedido=pedido,
                texto_comprovante=message,
                llm_client=llm_to_use,
                comprovante_bytes=comprovante_bytes,
                nome_arquivo=comprovante_filename,
                vision_client=external_client,
                local_vision_client=local_client,
                origem="chat",
                llm_ambiente="interno" if llm_to_use is local_client else "externo",
            )
        yield TokenEvent(text=texto_resp)
        yield RouterDecision(
            **_decision_base,
            resposta=texto_resp,
            **_tokens_do_parecer(parecer_res),
        )
    except Exception as exc:
        logger.warning(
            "falha_processar_comprovante",
            extra={
                "router": {
                    "event": "falha_processar_comprovante",
                    "conversation_id": conversation_id,
                    "erro": str(exc),
                }
            },
        )


def _emitir_comprovante_sem_reserva(
    decision_base: dict,
) -> AsyncIterator[TokenEvent | RouterDecision]:
    """Yields os dois eventos SSE para o caso de comprovante sem reserva ativa."""
    msg = (
        "Recebi o envio do comprovante, mas não encontrei nenhuma reserva "
        "pendente ativa associada a esta conversa ou conta. Por favor, "
        "verifique o código da sua reserva ou faça seu pedido primeiro."
    )

    async def _gen():
        yield TokenEvent(text=msg)
        yield RouterDecision(**decision_base, resposta=msg, tokens_entrada=None, tokens_saida=None)

    return _gen()


@dataclass
class _RagResult:
    documentos: list[Document] = field(default_factory=list)
    dados_catalogo_vendas: DadosCatalogoVendas | DadosCatalogoCategoria | None = None
    backend_escolhido: str = "local"
    motivo: str = "nenhum"
    rag_retrieval_ms: float | None = None
    rag_chunks_count: int | None = None
    rag_avg_score: float | None = None
    rag_chunks: list[RagChunkMetric] | None = None


def _preencher_metricas_rag(r: _RagResult, t0: float) -> None:
    """Preenche latência e métricas de score/chunks do RAG in-place."""
    r.rag_retrieval_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    r.rag_chunks_count = len(r.documentos)
    if r.documentos:
        r.rag_avg_score = round(sum(d.score for d in r.documentos) / len(r.documentos), 4)
        r.rag_chunks = [
            RagChunkMetric(source=d.source, score=round(d.score, 4)) for d in r.documentos
        ]


async def _buscar_rag_e_rotear(
    message: str,
    recent_messages: list[str],
    classification: Any,
    rag_client: RAGClient,
    sales_catalog_client: SalesCatalogClient | None,
    local_client: LLMClient,
    ultima_troca: tuple[str, str] | None,
    dados_cliente: str | None,
    rag_top_k: int,
    rag_score_threshold: float,
) -> _RagResult:
    """Busca RAG + catálogo de vendas em paralelo e decide backend/motivo."""
    r = _RagResult()
    if classification.domain == "fora_escopo":
        if classification.complexity != "baixa":
            r.backend_escolhido, r.motivo = "externo", "fora_escopo"
        return r
    ultima_resposta = ultima_troca[1] if ultima_troca else None

    t0 = time.perf_counter()
    try:
        async with asyncio.TaskGroup() as tg:
            rag_task = tg.create_task(
                _buscar_documentos_rag(
                    message,
                    recent_messages,
                    classification.domain,
                    rag_client,
                    ultima_resposta=ultima_resposta,
                    top_k=rag_top_k,
                    score_threshold=rag_score_threshold,
                )
            )
            vendas_task = (
                tg.create_task(
                    _consultar_vendas(
                        message,
                        recent_messages,
                        sales_catalog_client,
                        local_client,
                        ultima_resposta=ultima_resposta,
                    )
                )
                if classification.domain == "vendas" and sales_catalog_client is not None
                else None
            )
    except* Exception as eg:
        exc = eg.exceptions[0]
        logger.error(
            "rag_indisponivel",
            extra={
                "router": {
                    "event": "rag_indisponivel",
                    "domain": classification.domain,
                    "tipo": type(exc).__name__,
                    "erro": str(exc),
                }
            },
        )
        raise exc from None

    r.documentos = rag_task.result()
    if vendas_task is not None:
        r.dados_catalogo_vendas = vendas_task.result()

    _preencher_metricas_rag(r, t0)
    _decidir_backend(r, classification, dados_cliente)
    return r


def _decidir_backend(r: _RagResult, classification: Any, dados_cliente: str | None) -> None:
    """Aplica a regra de roteamento local/externo ao resultado do RAG in-place."""
    if not r.documentos and r.dados_catalogo_vendas is None and dados_cliente is None:
        r.backend_escolhido = "externo"
        r.motivo = "rag_vazio"
    elif classification.complexity == "alta":
        r.backend_escolhido = "externo"
        r.motivo = "complexidade_alta"


async def _gerar_stream_llm(
    prompt: str,
    client: LLMClient,
    backend_escolhido: str,
    domain: str,
) -> AsyncIterator[StatusEvent | TokenEvent | LLMStreamChunk]:
    """Yields StatusEvent/TokenEvent durante o stream; yield final é o LLMStreamChunk done."""
    try:
        if not await client.is_model_ready():
            yield StatusEvent(status="carregando_modelo")
        chunk_final: LLMStreamChunk | None = None
        async for chunk in client.generate_stream(prompt):
            if chunk.text:
                yield TokenEvent(text=chunk.text)
            if chunk.done:
                chunk_final = chunk
        if chunk_final is None:
            raise RuntimeError("generate_stream terminou sem chunk final (done=True)")
        yield chunk_final
    except Exception as exc:
        logger.error(
            "backend_indisponivel",
            extra={
                "router": {
                    "event": "backend_indisponivel",
                    "backend": backend_escolhido,
                    "domain": domain,
                    "etapa": "geracao",
                    "erro": str(exc),
                }
            },
        )
        if backend_escolhido == "local":
            raise LocalBackendIndisponivelError(str(exc)) from exc
        raise ExternalBackendIndisponivelError(str(exc)) from exc


def _calcular_tps(chunk: LLMStreamChunk) -> float | None:
    """Tokens por segundo a partir do chunk final do stream."""
    if chunk.completion_tokens and chunk.eval_duration_ms:
        return round(chunk.completion_tokens / max(chunk.eval_duration_ms / 1000.0, 0.001), 2)
    return None


async def _construir_decisao(
    classification: Any,
    complexity_strategy: str,
    rag: _RagResult,
    chunk: LLMStreamChunk,
    client: LLMClient,
    resposta_completa: str,
    db_sessionmaker: async_sessionmaker[AsyncSession] | None,
    rag_download_threshold: float,
    conversation_id: str,
) -> RouterDecision:
    """Monta RouterDecision, loga e dispara registro de uso em background."""
    tps = _calcular_tps(chunk)
    decisao = RouterDecision(
        domain=classification.domain,
        complexity=classification.complexity,
        confidence=classification.confidence,
        complexity_strategy_usada=complexity_strategy,
        backend_escolhido=rag.backend_escolhido,
        motivo_escalonamento=rag.motivo,
        resposta=resposta_completa,
        latencia_ms=chunk.total_duration_ms or 0.0,
        tokens_entrada=chunk.prompt_tokens,
        tokens_saida=chunk.completion_tokens,
        cost_prompt_usd=chunk.cost_prompt_usd,
        cost_completion_usd=chunk.cost_completion_usd,
        custo_estimado_usd=chunk.estimated_cost_usd,
        modelo_usado=chunk.model_name or getattr(client, "model", None),
        ttft_ms=chunk.prompt_eval_duration_ms,
        tps=tps,
        rag_retrieval_ms=rag.rag_retrieval_ms,
        rag_chunks_count=rag.rag_chunks_count,
        rag_avg_score=rag.rag_avg_score,
        rag_chunks=rag.rag_chunks,
        router_provider=classification.provider_efetivo,
        card=_construir_card_vendas(rag.dados_catalogo_vendas)
        or await _construir_card_documento_download(
            db_sessionmaker, rag.documentos, classification.domain, rag_download_threshold
        ),
    )
    logger.info(
        "router_decision", extra={"router": {"event": "router_decision", **decisao.model_dump()}}
    )
    spawn_background_task(
        registrar_uso_ia(
            origem="chat",
            ambiente="interno" if rag.backend_escolhido == "local" else "externo",
            modelo=decisao.modelo_usado or "desconhecido",
            operacao="geracao_resposta",
            tokens_entrada=decisao.tokens_entrada,
            tokens_saida=decisao.tokens_saida,
            custo_usd=decisao.custo_estimado_usd,
            referencia_id=conversation_id or None,
            session=None,
            session_factory=None,
            commit=False,
        )
    )
    return decisao


async def _handle_llm_generation(
    message: str,
    recent_messages: list[str],
    classification: Any,
    local_client: LLMClient,
    external_client: LLMClient,
    rag_client: RAGClient,
    sales_catalog_client: SalesCatalogClient | None,
    db_sessionmaker: async_sessionmaker[AsyncSession] | None,
    conversation_id: str,
    intent_router_provider: str,
    resumo_conversa: str | None,
    pedir_email_pos_venda: bool,
    ultima_troca: tuple[str, str] | None,
    dados_cliente: str | None,
    contexto_conversa_anterior: str | None,
    usuario_autenticado: bool,
    rag_top_k: int,
    rag_score_threshold: float,
    rag_download_threshold: float,
    user_email: str | None,
    complexity_strategy: str,
) -> AsyncIterator[StatusEvent | TokenEvent | RouterDecision]:
    """RAG + roteamento local/externo + geração LLM + RouterDecision final."""
    rag = await _buscar_rag_e_rotear(
        message,
        recent_messages,
        classification,
        rag_client,
        sales_catalog_client,
        local_client,
        ultima_troca,
        dados_cliente,
        rag_top_k,
        rag_score_threshold,
    )

    if detectar_tentativa_injecao(message):
        logger.warning(
            "tentativa_injecao_detectada",
            extra={
                "router": {
                    "event": "tentativa_injecao_detectada",
                    "conversation_id": conversation_id,
                    "trecho": message[:200],
                }
            },
        )

    prompt = _build_prompt(
        message,
        rag.documentos,
        classification.domain,
        dados_catalogo=_formatar_bloco_catalogo_vendas(rag.dados_catalogo_vendas),
        resumo_conversa=resumo_conversa,
        pedir_email_pos_venda=pedir_email_pos_venda,
        ultima_troca=ultima_troca,
        dados_cliente=dados_cliente,
        contexto_conversa_anterior=contexto_conversa_anterior,
        usuario_autenticado=usuario_autenticado,
    )

    client = local_client if rag.backend_escolhido == "local" else external_client
    texto_partes: list[str] = []
    chunk_final: LLMStreamChunk | None = None
    async for evento in _gerar_stream_llm(
        prompt, client, rag.backend_escolhido, classification.domain
    ):
        if isinstance(evento, (StatusEvent, TokenEvent)):
            if isinstance(evento, TokenEvent):
                texto_partes.append(evento.text)
            yield evento
        else:
            chunk_final = evento

    resposta_completa = "".join(texto_partes)
    decisao = await _construir_decisao(
        classification=classification,
        complexity_strategy=complexity_strategy,
        rag=rag,
        chunk=chunk_final,
        client=client,
        resposta_completa=resposta_completa,
        db_sessionmaker=db_sessionmaker,
        rag_download_threshold=rag_download_threshold,
        conversation_id=conversation_id,
    )
    yield decisao


def _deve_escalar_tom(
    tone_monitor_enabled: bool,
    tone_result: ToneResult,
    conversation_id: str,
) -> bool:
    return tone_monitor_enabled and tone_result.escalate and not ja_escalada(conversation_id)


def _agendamento_ativo(
    calendar_client: CalendarClient | None,
    scheduling_config: SchedulingConfig | None,
    domain: str,
    conversation_id: str,
) -> bool:
    if calendar_client is None or scheduling_config is None:
        return False
    slots = get_booking_slots(conversation_id)
    return domain == "agendamento" or slots != BookingSlots()


async def _sem_analise_de_tom() -> ToneResult:
    """Substituto de `analyze_tone()` quando `tone_monitor_enabled=False` —
    devolve um resultado neutro sem nenhuma chamada de rede, só para manter
    `asyncio.gather` com a mesma forma (duas corrotinas) independente do
    toggle, sem duplicar o try/except de `classify()` em `handle_message`.
    """
    return ToneResult(
        escalate=False, motivo=None, confidence=0.0, provider_efetivo=DEFAULT_TONE_MONITOR_PROVIDER
    )


async def _executar_handlers_curtos(
    *handlers: Callable[[], AsyncIterator[TokenEvent | RouterDecision]],
) -> AsyncIterator[TokenEvent | RouterDecision]:
    """Roda os handlers em ordem (criados sob demanda) e para no primeiro que
    emitir um `RouterDecision` — ele já concluiu o turno."""
    for criar in handlers:
        concluido = False
        async for evento in criar():
            yield evento
            concluido = concluido or isinstance(evento, RouterDecision)
        if concluido:
            return


async def handle_message(  # noqa: PLR0913
    message: str,
    recent_messages: list[str],
    local_client: LLMClient,
    external_client: LLMClient,
    rag_client: RAGClient,
    complexity_strategy: str,
    conversation_id: str = "",
    calendar_client: CalendarClient | None = None,
    scheduling_config: SchedulingConfig | None = None,
    sales_catalog_client: SalesCatalogClient | None = None,
    intent_router_provider: str = DEFAULT_INTENT_ROUTER_PROVIDER,
    tone_monitor_enabled: bool = True,
    tone_monitor_provider: str = DEFAULT_TONE_MONITOR_PROVIDER,
    resumo_conversa: str | None = None,
    pedir_email_pos_venda: bool = False,
    ultima_troca: tuple[str, str] | None = None,
    dados_cliente: str | None = None,
    contexto_conversa_anterior: str | None = None,
    db_sessionmaker: async_sessionmaker[AsyncSession] | None = None,
    rag_top_k: int = 3,
    rag_score_threshold: float = 0.35,
    rag_download_threshold: float = 0.65,
    is_admin: bool = False,
    user_email: str | None = None,
    comprovante_bytes: bytes | None = None,
    comprovante_filename: str | None = None,
    usuario_autenticado: bool = False,
) -> AsyncIterator[StatusEvent | TokenEvent | RouterDecision | EscalonamentoEvent]:
    async for evento in _checar_modelo_local(
        local_client, intent_router_provider, tone_monitor_enabled, tone_monitor_provider
    ):
        yield evento

    tone_result, classification = await _handle_tone_e_classify(
        message=message,
        recent_messages=recent_messages,
        local_client=local_client,
        external_client=external_client,
        complexity_strategy=complexity_strategy,
        intent_router_provider=intent_router_provider,
        tone_monitor_enabled=tone_monitor_enabled,
        tone_monitor_provider=tone_monitor_provider,
        ultima_troca=ultima_troca,
    )

    if _deve_escalar_tom(tone_monitor_enabled, tone_result, conversation_id):
        marcar_escalada(conversation_id)
        yield EscalonamentoEvent(
            motivo=tone_result.motivo,
            confianca=tone_result.confidence,
            provider_efetivo=tone_result.provider_efetivo,
        )

    concluido = False
    async for evento in _executar_handlers_curtos(
        partial(
            _handle_chart_request,
            message=message,
            is_admin=is_admin,
            user_email=user_email,
            local_client=local_client,
            external_client=external_client,
            db_sessionmaker=db_sessionmaker,
            intent_router_provider=intent_router_provider,
        ),
        partial(
            _handle_comprovante,
            message=message,
            conversation_id=conversation_id,
            user_email=user_email,
            local_client=local_client,
            external_client=external_client,
            db_sessionmaker=db_sessionmaker,
            intent_router_provider=intent_router_provider,
            comprovante_bytes=comprovante_bytes,
            comprovante_filename=comprovante_filename,
        ),
    ):
        yield evento
        concluido = concluido or isinstance(evento, RouterDecision)
    if concluido:
        return

    # MVP: o ramo de agendamento só roda quando (a) calendar_client/scheduling_config
    # foram fornecidos E (b) a classificação disse "agendamento" OU já existe estado
    # parcial salvo para conversation_id.
    if _agendamento_ativo(
        calendar_client, scheduling_config, classification.domain, conversation_id
    ):
        async for evento in _handle_agendamento(
            conversation_id=conversation_id,
            message=message,
            recent_messages=recent_messages,
            local_client=local_client,
            calendar_client=calendar_client,
            scheduling_config=scheduling_config,
            intent_router_provider=intent_router_provider,
            db_sessionmaker=db_sessionmaker,
        ):
            yield evento
        return

    async for evento in _handle_llm_generation(
        message=message,
        recent_messages=recent_messages,
        classification=classification,
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        sales_catalog_client=sales_catalog_client,
        db_sessionmaker=db_sessionmaker,
        conversation_id=conversation_id,
        intent_router_provider=intent_router_provider,
        resumo_conversa=resumo_conversa,
        pedir_email_pos_venda=pedir_email_pos_venda,
        ultima_troca=ultima_troca,
        dados_cliente=dados_cliente,
        contexto_conversa_anterior=contexto_conversa_anterior,
        usuario_autenticado=usuario_autenticado,
        rag_top_k=rag_top_k,
        rag_score_threshold=rag_score_threshold,
        rag_download_threshold=rag_download_threshold,
        user_email=user_email,
        complexity_strategy=complexity_strategy,
    ):
        yield evento
