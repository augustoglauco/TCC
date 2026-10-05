import asyncio
import logging
import re
import time
import unicodedata
from collections.abc import AsyncIterator
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Agendamento, RagDocument
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
from app.rag.collections_registry import get_collection
from app.router.classifier import Domain, classify
from app.router.llm_client import LLMClient, LLMStreamChunk
from app.router.playbooks import build_system_prompt
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
    system_prompt = build_system_prompt(domain)
    partes: list[str] = []
    if system_prompt is not None:
        partes.append(system_prompt)

    if dados_cliente is not None:
        partes.append(dados_cliente)

    if contexto_conversa_anterior:
        partes.append(
            "Contexto da conversa anterior do cliente (use como histórico prévio do cliente; "
            "se a conversa atual tratar de algo novo, priorize o contexto atual):\n"
            f"{contexto_conversa_anterior}"
        )

    if resumo_conversa:
        # O prompt não leva as mensagens anteriores; o resumo periódico é o
        # que dá ao LLM o contexto da conversa (ex.: de que produto se fala).
        partes.append(
            "Resumo da conversa até aqui (use como contexto; se a mensagem "
            f"atual disser algo diferente, ela vale):\n{resumo_conversa}"
        )

    if ultima_troca:
        # O resumo só existe a cada 6 mensagens; a troca anterior é o que
        # resolve referências como "o produto acima" ou "e esse?".
        cliente, assistente = ultima_troca
        partes.append(
            "Troca anterior da conversa (use para entender referências como "
            "'o produto acima' ou 'esse'):\n"
            f"Cliente: {cliente[:_ULTIMA_RESPOSTA_MAX_CHARS]}\n"
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
            f"Informações recuperadas:\n{contexto}"
        )

    if pedir_email_pos_venda and domain in DOMINIOS_POS_VENDA:
        # R10 (Fase 6): identidade pelo e-mail, pedida só no momento natural
        # — no pós-venda, para localizar a compra.
        partes.append(
            "Ainda não sabemos o e-mail do cliente. Se fizer sentido para "
            "localizar a compra dele, peça educadamente, uma única vez, o "
            "e-mail usado na compra."
        )

    partes.append(f"Mensagem do cliente: {message}")
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


async def _consultar_vendas(
    message: str,
    recent_messages: list[str],
    sales_catalog_client: SalesCatalogClient,
    local_client: LLMClient,
    ultima_resposta: str | None = None,
) -> DadosCatalogoVendas | DadosCatalogoCategoria | None:
    """Busca de candidatos + desambiguação por LLM + detalhes do catálogo
    para uma mensagem de Vendas (spec
    docs/superpowers/specs/2026-09-24-orquestrador-mcp-b2b-vendas-design.md).
    Quando a pergunta é genérica por um tipo de produto ("quais geradores
    vocês têm em estoque?"), o LLM devolve uma `categoria` em vez de um
    `produto_id` único, e a resposta lista os produtos daquela categoria com
    estoque (`DadosCatalogoCategoria`). Nunca levanta exceção — qualquer
    falha (erro de banco, resposta do LLM não-JSON já tratada dentro de
    `extract_sales_slots`) loga e devolve `None`, mesmo espírito de
    `analyze_tone` nunca derrubar o turno."""
    diagnostico: dict = {"event": "vendas_catalogo_consulta"}
    # "possui detalhes?" depois da imagem: o produto está na última resposta
    # (ex.: "Identifiquei: Rádio … RC 4102g2."), que entra no histórico da
    # busca e da escolha pelo LLM. Sempre, não só com "acima"/"esse": o
    # histórico já é só complemento (candidatos da mensagem atual vêm
    # primeiro) e o LLM escolhe (correções de 2026-09-27/28).
    if ultima_resposta:
        recent_messages = [*recent_messages, ultima_resposta[:_ULTIMA_RESPOSTA_MAX_CHARS]]
    try:
        termos = extrair_termos_busca(message)
        # Termos das mensagens anteriores entram só como complemento: numa
        # mensagem de acompanhamento ("E se eu levar 3 unidades?") o produto
        # foi citado antes, e sem isso a busca não achava nada — ou achava o
        # produto errado por coincidência (o "5" de "5 unidades" casando com
        # "GD-15"; teste local de 2026-09-25, cenário V8). O LLM da etapa 2 já
        # recebe o histórico e escolhe entre os candidatos das duas buscas.
        termos_historico = [
            termo
            for termo in extrair_termos_busca(" ".join(recent_messages))
            if termo not in termos
        ]
        diagnostico["termos"] = termos
        diagnostico["termos_historico"] = termos_historico
        if not termos and not termos_historico:
            return _logar_consulta_vendas(diagnostico, "sem_termos")
        candidatos = await sales_catalog_client.buscar_candidatos(termos) if termos else []
        if termos_historico and len(candidatos) < SALES_CANDIDATOS_LIMITE:
            # Candidatos da mensagem atual primeiro; os do histórico
            # completam a lista até o mesmo teto, sem repetir produto.
            ids_atuais = {candidato.id for candidato in candidatos}
            candidatos += [
                candidato
                for candidato in await sales_catalog_client.buscar_candidatos(termos_historico)
                if candidato.id not in ids_atuais
            ]
            candidatos = candidatos[:SALES_CANDIDATOS_LIMITE]
        diagnostico["candidatos"] = [candidato.nome for candidato in candidatos]
        # Correção de 2026-09-29 (docs/ARCHITECTURE.md §5): antes, nenhum
        # candidato encontrado por palavra-chave (`buscar_candidatos`)
        # interrompia a consulta aqui (`sem_candidatos`) sem nunca chamar o
        # LLM — uma pergunta totalmente genérica ("quais produtos vocês têm
        # em estoque?") não casa nome/categoria nenhum por ILIKE, então nunca
        # tinha chance de virar `listar_tudo`. Agora sempre segue para a
        # etapa 2 (LLM), mesmo com `candidatos` vazio — ele decide entre
        # produto/categoria/listar_tudo mesmo sem candidatos prontos.
        categorias_disponiveis = await sales_catalog_client.listar_categorias()
        slots = await extract_sales_slots(
            message, recent_messages, candidatos, local_client, categorias_disponiveis
        )
        diagnostico["slots"] = slots.model_dump()
        if slots.produto_id is None:
            # Sem produto específico, mas com categoria genérica → lista os
            # produtos daquela categoria com estoque ("quais geradores vocês
            # têm?"). Corrige o caso em que a busca genérica caía em
            # `llm_sem_produto` e o chat respondia "não tenho informações".
            if slots.categoria is not None:
                dados_categoria = await sales_catalog_client.consultar_categoria(slots.categoria)
                if dados_categoria is None:
                    return _logar_consulta_vendas(diagnostico, "categoria_vazia")
                diagnostico["bloco"] = _formatar_dados_catalogo_categoria(dados_categoria)
                _logar_consulta_vendas(diagnostico, "ok_categoria")
                return dados_categoria
            # Sem produto nem categoria, mas pedido genérico de "ver tudo"
            # (correção de 2026-09-29) → lista o catálogo completo.
            if slots.listar_tudo:
                dados_todos = await sales_catalog_client.listar_todos_produtos()
                if dados_todos is None:
                    return _logar_consulta_vendas(diagnostico, "catalogo_vazio")
                diagnostico["bloco"] = _formatar_dados_catalogo_categoria(dados_todos)
                _logar_consulta_vendas(diagnostico, "ok_listar_tudo")
                return dados_todos
            return _logar_consulta_vendas(diagnostico, "llm_sem_produto")
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
                .where(RagDocument.filename == melhor_chunk.source, RagDocument.domain == domain)
                .limit(1)
            )
            # MVP: casamento por filename+domain, não por document_id — o
            # `Document` devolvido por `RAGClient.search` não carrega
            # document_id, só o filename em `source` (ver
            # app/router/rag_client.py / app/rag/qdrant_client.py).
            doc = resultado.scalar_one_or_none()
            if doc is None or not doc.storage_path:
                return None
            collection = await get_collection(session, doc.collection_id)
            if collection is None or collection.purpose != "chat":
                return None
            try:
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
        logger.exception("documento_download_card_falhou")
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
    try:
        extraction = await extract_booking_slots(
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

    if slots.awaiting_confirmation:
        if extraction.confirmacao:
            # Fix (revisão final, achado crítico 1): mesmo já confirmado,
            # revalida expediente/disponibilidade antes de criar o evento de
            # verdade — `merge_slots` já aplicou qualquer `data_hora` nova
            # extraída desta mesma mensagem ANTES deste ponto, então uma
            # mensagem que muda a data e confirma ao mesmo tempo (ou uma
            # confirmação tardia sobre um horário que ficou stale) não pode
            # pular a checagem só porque `awaiting_confirmation` já era
            # `True`.
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
                    falha.texto,
                    falha.motivo,
                    intent_router_provider=intent_router_provider,
                ):
                    yield evento
                return

            try:
                fim = slots.data_hora + DURACAO_VISITA
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
                    MSG_ERRO_MCP,
                    "mcp_indisponivel",
                    intent_router_provider=intent_router_provider,
                ):
                    yield evento
                return

            if db_sessionmaker is not None:
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

            texto = mensagem_sucesso(slots, scheduling_config.timezone)
            clear_booking_slots(conversation_id)
            card = CardAgendamento(
                data_hora_inicio=slots.data_hora,
                data_hora_fim=fim,
                google_event_link=google_event_link or None,
            )
            async for evento in _emitir_resposta_agendamento(
                texto,
                "confirmado",
                intent_router_provider=intent_router_provider,
                card=card,
            ):
                yield evento
            return

        # Resposta ambígua durante awaiting_confirmation=True (ex.: o
        # visitante mudou data/hora em vez de confirmar claramente): volta
        # a "não confirmado ainda" em vez de só repetir a pergunta, para
        # cair no bloco de validação abaixo NO MESMO turno — se a
        # data_hora mudou para algo inválido (fora do expediente/em
        # conflito), o visitante não recebe "posso confirmar?" de novo
        # sobre um horário que na verdade não é mais válido (spec §4.1
        # passo 7).
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


async def _sem_analise_de_tom() -> ToneResult:
    """Substituto de `analyze_tone()` quando `tone_monitor_enabled=False` —
    devolve um resultado neutro sem nenhuma chamada de rede, só para manter
    `asyncio.gather` com a mesma forma (duas corrotinas) independente do
    toggle, sem duplicar o try/except de `classify()` em `handle_message`.
    """
    return ToneResult(
        escalate=False, motivo=None, confidence=0.0, provider_efetivo=DEFAULT_TONE_MONITOR_PROVIDER
    )


async def handle_message(
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
) -> AsyncIterator[StatusEvent | TokenEvent | RouterDecision | EscalonamentoEvent]:
    # No Ollama real, esta é a primeira chamada bloqueante ao modelo — seja
    # ela feita por `classify()` com strategy="llm" (logo abaixo) ou pelo
    # fallback LLM do Monitor de Tom dentro de `analyze_tone()` (bloco
    # seguinte) — que paga o cold-start, não a geração da resposta em si.
    # Sem este check aqui (só existia antes de `generate_stream`, mais
    # abaixo), o cold-start acontecia em silêncio: quando o check de depois
    # rodava, o modelo já estava carregado e o evento `status` nunca era
    # emitido, apesar da espera real ter ocorrido (bug relatado pelo
    # usuário: "a mensagem para aguardar não aparece").
    #
    # Achado na revisão final do branch Monitor de Tom (R8): este check
    # cobria só a condição de classificação e ficava DEPOIS do bloco do
    # Monitor de Tom — com tone_monitor_enabled=True e
    # tone_monitor_provider="heuristica_llm" (ambos padrão), a chamada LLM
    # de `analyze_tone()` passou a ser, com frequência, a primeira chamada
    # bloqueante de verdade, reintroduzindo o mesmo bug por uma rota
    # diferente da originalmente corrigida. Por isso o check foi movido para
    # o topo da função e a condição de disparo foi ampliada para cobrir
    # também o caminho do Monitor de Tom — mesmo quando a heurística acaba
    # resolvendo sozinha e o LLM nunca chega a ser chamado: um
    # `carregando_modelo` a mais quando o modelo já está quente (ou quando a
    # heurística resolve sozinha) é inofensivo para o frontend; a FALTA dele
    # quando o modelo está realmente frio é que é o bug real.
    # Achado no code-review (2026-09-24): com o Monitor de Tom no padrão
    # (habilitado, provedor "heuristica_llm"), `deve_checar_modelo_local`
    # fica quase sempre `True` — inclusive para mensagens que a heurística
    # de tom resolve sozinha (sem chamar o LLM) e que a classificação vai
    # rotear 100% pro backend externo (ex.: `fora_escopo`). Antes desta
    # correção, uma falha aqui (Ollama fora do ar) virava
    # `LocalBackendIndisponivelError` e derrubava a requisição inteira,
    # mesmo quando o backend local nunca seria de fato necessário para essa
    # mensagem. Esta checagem é só uma otimização de UX (mostrar
    # "carregando_modelo" antes de um cold-start real) — não é a fonte de
    # verdade sobre disponibilidade do backend local; essa fonte de verdade
    # continua sendo o try/except em volta de `classify()` logo abaixo (que
    # SÓ dispara quando o backend local é de fato chamado) e a degradação
    # graciosa já embutida em `analyze_tone()`. Por isso uma falha aqui vira
    # só um log de aviso, não uma exceção.
    deve_checar_modelo_local = (intent_router_provider == "heuristica_llm") or (
        tone_monitor_enabled and tone_monitor_provider == DEFAULT_TONE_MONITOR_PROVIDER
    )
    if deve_checar_modelo_local:
        try:
            modelo_pronto = await local_client.is_model_ready()
        except Exception as exc:
            logger.warning(
                "verificacao_modelo_local_falhou",
                extra={
                    "router": {
                        "event": "verificacao_modelo_local_falhou",
                        "erro": str(exc),
                    }
                },
            )
            modelo_pronto = True  # não emite carregando_modelo; segue o fluxo normal
        if not modelo_pronto:
            yield StatusEvent(status="carregando_modelo")

    # Monitor de Tom (R8, Fase 4B) — transversal a todo domínio (ver
    # docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md §2). Nunca
    # substitui a resposta normal: só adiciona um evento a mais no stream.
    #
    # Achado no code-review (2026-09-24): `analyze_tone()` e `classify()`
    # são independentes (nenhum usa o resultado do outro) mas eram
    # `await`ados em sequência — em uma GPU única (16GB), isso dobra a
    # espera antes do primeiro token em toda mensagem sem sinal heurístico
    # de tom. `asyncio.gather` roda as duas em paralelo; quando o Monitor de
    # Tom está desligado, `_sem_analise_de_tom()` só devolve um resultado
    # neutro sem custo de rede, mantendo um único caminho de código em vez
    # de duplicar o try/except de `classify()`.
    if tone_monitor_enabled:
        tone_coro = analyze_tone(
            message=message,
            recent_messages=recent_messages,
            strategy_provider=tone_monitor_provider,
            llm_client=local_client,
            external_client=external_client,
        )
    else:
        tone_coro = _sem_analise_de_tom()

    # Com strategy="llm" a classificação chama o backend local. Falha aqui é
    # falha de infraestrutura local, não "conteúdo não classificável" — vira
    # LocalBackendIndisponivelError em vez de degradar em silêncio para
    # fora_escopo (que rotearia ao backend externo). O wrapping fica aqui, e
    # não dentro de `classify()`, para não criar import circular.
    # `analyze_tone()` nunca levanta exceção (degrada sozinha), então só a
    # falha de `classify()` chega aqui mesmo rodando as duas em paralelo.
    #
    # Achado no code-review (2026-09-24): `asyncio.gather` (sem
    # `return_exceptions=True`) propaga a exceção de `classify()` assim que
    # ela acontece, mas NÃO cancela `tone_coro` se ainda estiver rodando —
    # a chamada LLM/Jev do Monitor de Tom ficava órfã, continuando depois
    # da requisição já ter falhado. `asyncio.TaskGroup` resolve isso: ao
    # sair do bloco com uma exceção, cancela automaticamente as outras
    # tasks do grupo (aqui, só há uma tarefa irmã: `tone_task`).
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

    tone_result = tone_task.result()
    classification = classification_task.result()

    if tone_monitor_enabled and tone_result.escalate and not ja_escalada(conversation_id):
        marcar_escalada(conversation_id)
        yield EscalonamentoEvent(
            motivo=tone_result.motivo,
            confianca=tone_result.confidence,
            provider_efetivo=tone_result.provider_efetivo,
        )

    # Dashboards e Gráficos Dinâmicos Gerados via Chat (Admin)
    from app.services.analytics_agent import extract_prompt_inline_data, process_dynamic_chart_request
    from app.services.chart_generator import detect_chart_request

    chart_request = detect_chart_request(message) or extract_prompt_inline_data(message)
    if chart_request:
        if not is_admin:
            msg_negada = (
                "A geração de gráficos e dashboards é um recurso exclusivo para "
                "administradores autenticados. Faça login como administrador para gerar e visualizar gráficos dinâmicos."
            )
            yield TokenEvent(text=msg_negada)
            yield RouterDecision(
                domain="fora_escopo",
                complexity="baixa",
                confidence=1.0,
                complexity_strategy_usada="regras",
                backend_escolhido="local",
                motivo_escalonamento="fora_escopo",
                resposta=msg_negada,
                latencia_ms=0.0,
                tokens_entrada=None,
                tokens_saida=None,
                cost_prompt_usd=0.0,
                cost_completion_usd=0.0,
                custo_estimado_usd=0.0,
                router_provider=intent_router_provider,
            )
            return

        if db_sessionmaker:
            chart = None
            explicacao = ""
            try:
                analytics_llm = local_client if local_client is not None else external_client
                session_ctx = db_sessionmaker()
                if hasattr(session_ctx, "__aenter__"):
                    async with session_ctx as session:
                        chart, explicacao = await process_dynamic_chart_request(
                            session=session,
                            prompt=message,
                            user_email=user_email or "admin",
                            llm_client=analytics_llm,
                        )
                else:
                    chart, explicacao = await process_dynamic_chart_request(
                        session=session_ctx,
                        prompt=message,
                        user_email=user_email or "admin",
                        llm_client=analytics_llm,
                    )
            except Exception as exc:
                logger.error("falha_ao_gerar_grafico_chat", extra={"erro": str(exc)})

            if chart:
                texto_resp = explicacao or (
                    f"Gerei o gráfico '{chart.titulo}' para você com base nos dados mais recentes. "
                    "Ele já está salvo no seu painel de Dashboards."
                )
                yield TokenEvent(text=texto_resp)
                card = CardGrafico(
                    chart_id=str(chart.id),
                    titulo=chart.titulo,
                    tipo_grafico=chart.tipo_grafico,
                    config=chart.config_json,
                    dados=chart.dados_json,
                    fixado=chart.fixado,
                )
                yield RouterDecision(
                    domain="atendimento",
                    complexity="baixa",
                    confidence=1.0,
                    complexity_strategy_usada="regras",
                    backend_escolhido="local",
                    motivo_escalonamento="nenhum",
                    resposta=texto_resp,
                    latencia_ms=0.0,
                    tokens_entrada=None,
                    tokens_saida=None,
                    cost_prompt_usd=0.0,
                    cost_completion_usd=0.0,
                    custo_estimado_usd=0.0,
                    card=card,
                    router_provider=intent_router_provider,
                )
                return

    # MVP: o ramo de agendamento só roda quando (a) o chamador forneceu
    # `calendar_client`/`scheduling_config` para esta chamada E (b) a
    # classificação por palavra-chave disse "agendamento" OU já existe
    # estado parcial de agendamento salvo para `conversation_id`. A
    # condição (b) sozinha não basta: `classify()` não tem memória de
    # conversa — mensagens de continuação do fluxo (ex.: "meu nome é
    # Maria", "sim, pode confirmar") não contêm nenhuma palavra-chave de
    # domínio, então o estado parcial salvo (b, segunda metade) é quem
    # mantém a conversa no fluxo depois do primeiro turno. A condição (a)
    # sozinha também não basta: assim que `app.api.chat` (Task 10/11)
    # passar a injetar esses dois objetos como singletons de vida da
    # aplicação em toda chamada, (a) por si só viraria sempre-verdadeiro e
    # roubaria vendas/suporte/atendimento/fora_escopo para este ramo — por
    # isso a combinação com (b). Hoje (antes da Task 10/11), `app.api.chat`
    # ainda não passa `calendar_client`/`scheduling_config`, então (a) é
    # sempre falso e o comportamento de todo domínio (inclusive mensagens
    # com palavra-chave de agendamento) permanece o do fluxo genérico até
    # a integração ser ligada — ver
    # docs/superpowers/specs/2026-09-21-agendamento-mcp-calendar-design.md
    # §4.1.
    slots_existentes = get_booking_slots(conversation_id)
    agendamento_em_andamento = (
        classification.domain == "agendamento" or slots_existentes != BookingSlots()
    )
    # MVP: limitação aceita (ver docs/ARCHITECTURE.md §7) — uma vez que uma
    # conversa entra no fluxo de agendamento (por palavra-chave OU por já
    # ter estado parcial salvo, condição `agendamento_em_andamento` acima),
    # não há como sair dele a não ser completando um agendamento com
    # sucesso: os ramos de `horario_invalido` e falha de MCP preservam os
    # slots de propósito (para permitir nova tentativa), o que mantém
    # `slots_existentes != BookingSlots()` verdadeiro indefinidamente — e o
    # classificador por palavra-chave (`ROUTER_COMPLEXITY_STRATEGY=heuristic`
    # em produção) inclui a palavra isolada "horário" entre as palavras-chave
    # de agendamento, então uma pergunta como "qual o horário de
    # funcionamento?" pode entrar no fluxo por falso positivo. Sem
    # mecanismo de abandono/timeout nesta fase — decisão do controlador:
    # ajuste de palavras-chave do classificador fica para a Fase 10 (ver
    # docs/ROADMAP.md, Fase 1) e um mecanismo de abandono pertence a uma
    # futura fase de memória/gestão de sessão, não a esta.
    if calendar_client is not None and scheduling_config is not None and agendamento_em_andamento:
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

    backend_escolhido = "local"
    motivo = "nenhum"
    documentos: list[Document] = []
    dados_catalogo_vendas: DadosCatalogoVendas | DadosCatalogoCategoria | None = None
    rag_retrieval_ms: float | None = None
    rag_chunks_count: int | None = None
    rag_avg_score: float | None = None
    rag_chunks: list[RagChunkMetric] | None = None

    if classification.domain == "fora_escopo":
        if classification.complexity == "baixa":
            backend_escolhido = "local"
            motivo = "nenhum"
        else:
            backend_escolhido = "externo"
            motivo = "fora_escopo"
    else:
        t_rag_start = time.perf_counter()
        try:
            async with asyncio.TaskGroup() as tg:
                rag_task = tg.create_task(
                    _buscar_documentos_rag(
                        message,
                        recent_messages,
                        classification.domain,
                        rag_client,
                        ultima_resposta=ultima_troca[1] if ultima_troca else None,
                        top_k=rag_top_k,
                        score_threshold=rag_score_threshold,
                    )
                )
                vendas_task: asyncio.Task[DadosCatalogoVendas | None] | None = None
                if classification.domain == "vendas" and sales_catalog_client is not None:
                    # Busca RAG e consulta de vendas são independentes — rodam
                    # em paralelo (mesmo idioma já usado para tone/classify,
                    # ver docs/ARCHITECTURE.md §5, correção de 2026-09-24).
                    # `_consultar_vendas` nunca levanta (ver seu docstring),
                    # então só `rag_task` pode disparar o `except*` abaixo.
                    vendas_task = tg.create_task(
                        _consultar_vendas(
                            message,
                            recent_messages,
                            sales_catalog_client,
                            local_client,
                            ultima_resposta=ultima_troca[1] if ultima_troca else None,
                        )
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
            # `except* Exception` (não `except* RAGConnectionError`): hoje só
            # `RAGConnectionError` escapa daqui (`_consultar_vendas` nunca
            # levanta, ver seu docstring), mas capturar só esse tipo deixaria
            # uma armadilha silenciosa — qualquer outra exceção que um dia
            # passe a escapar de `_buscar_documentos_rag`/`rag_client.search`
            # sairia como `ExceptionGroup` não-encapsulado em vez do tipo
            # original, quebrando quem espera `except RAGConnectionError` (ou
            # qualquer outro `except` específico) em volta de
            # `handle_message`. Por isso o log acima precisa registrar
            # `tipo`/`erro` explicitamente — sem eles, qualquer exceção que não
            # seja `RAGConnectionError` ficaria muda no log estruturado.
            # `raise exc` (não um `raise` nu) para propagar a exceção
            # original, não um ExceptionGroup — chamadores de handle_message
            # ainda esperam o tipo original (hoje sempre RAGConnectionError na
            # prática).
            # `from None` só suprime o encadeamento implícito do
            # ExceptionGroup no traceback (B904); não afeta o tipo/identidade
            # da exceção relançada.
            raise exc from None

        documentos = rag_task.result()
        if vendas_task is not None:
            dados_catalogo_vendas = vendas_task.result()

        t_rag_end = time.perf_counter()
        rag_retrieval_ms = round((t_rag_end - t_rag_start) * 1000.0, 2)
        rag_chunks_count = len(documentos)
        if documentos:
            rag_avg_score = round(sum(d.score for d in documentos) / len(documentos), 4)
            rag_chunks = [
                RagChunkMetric(source=d.source, score=round(d.score, 4)) for d in documentos
            ]

        # Produto achado no banco (bloco do catálogo) ou dados do cliente
        # já contam como contexto: sem PDF que fale dele, a resposta sai
        # baseada no banco, no local.
        if not documentos and dados_catalogo_vendas is None and dados_cliente is None:
            backend_escolhido = "externo"
            motivo = "rag_vazio"
        elif classification.complexity == "alta":
            backend_escolhido = "externo"
            motivo = "complexidade_alta"

    # A decisão de roteamento (backend_escolhido/motivo) usa o sinal vazio x
    # não-vazio acima (o bloco do catálogo conta como contexto), sem mudar
    # aqui; o conteúdo dos documentos (quando houver) só entra a partir deste
    # ponto, no prompt em si.
    # _build_prompt é sempre chamado para anexar o playbook do domínio (Fase
    # 3); para `fora_escopo` (sem playbook) e sem documentos, ele reduz a
    # apenas "Mensagem do cliente: ...".
    prompt = _build_prompt(
        message,
        documentos,
        classification.domain,
        dados_catalogo=_formatar_bloco_catalogo_vendas(dados_catalogo_vendas),
        resumo_conversa=resumo_conversa,
        pedir_email_pos_venda=pedir_email_pos_venda,
        ultima_troca=ultima_troca,
        dados_cliente=dados_cliente,
        contexto_conversa_anterior=contexto_conversa_anterior,
    )

    client = local_client if backend_escolhido == "local" else external_client

    # `is_model_ready()` faz uma chamada de rede (ex.: GET /api/ps do Ollama)
    # tão sujeita a falha de infraestrutura quanto `generate_stream` — por
    # isso fica dentro do mesmo try/except abaixo, em vez de solta antes
    # dele (correção de revisão: antes, uma falha aqui propagava crua até o
    # endpoint, sem virar `LocalBackendIndisponivelError`/
    # `ExternalBackendIndisponivelError` nem o evento SSE `error`).
    texto_partes: list[str] = []
    chunk_final: LLMStreamChunk | None = None
    try:
        if not await client.is_model_ready():
            yield StatusEvent(status="carregando_modelo")

        async for chunk in client.generate_stream(prompt):
            if chunk.text:
                texto_partes.append(chunk.text)
                yield TokenEvent(text=chunk.text)
            if chunk.done:
                chunk_final = chunk

        if chunk_final is None:
            # generate_stream terminou (loop `async for` esgotou) sem nunca
            # emitir um chunk `done=True` — mesma família de falha de
            # infraestrutura que uma exceção explícita, por isso fica dentro
            # deste try/except (correção de revisão: antes, um
            # `assert` fora do try deixava esse caso escapar como
            # AssertionError cru em vez de virar `LocalBackendIndisponivelError`/
            # `ExternalBackendIndisponivelError` e o evento SSE `error`).
            raise RuntimeError("generate_stream terminou sem chunk final (done=True)")
    except Exception as exc:
        logger.error(
            "backend_indisponivel",
            extra={
                "router": {
                    "event": "backend_indisponivel",
                    "backend": backend_escolhido,
                    "domain": classification.domain,
                    "etapa": "geracao",
                    "erro": str(exc),
                }
            },
        )
        if backend_escolhido == "local":
            raise LocalBackendIndisponivelError(str(exc)) from exc
        raise ExternalBackendIndisponivelError(str(exc)) from exc

    # TPS usa `eval_duration` (tempo de geração pura) — `total_duration`
    # inclui também `load_duration` (carregar o modelo) e
    # `prompt_eval_duration` (processar o prompt), então usar o total
    # subestimaria a taxa de geração de tokens.
    tps: float | None = None
    if chunk_final.completion_tokens and chunk_final.eval_duration_ms:
        gen_duration_s = max(chunk_final.eval_duration_ms / 1000.0, 0.001)
        tps = round(chunk_final.completion_tokens / gen_duration_s, 2)

    resposta_completa = "".join(texto_partes)

    decisao = RouterDecision(
        domain=classification.domain,
        complexity=classification.complexity,
        confidence=classification.confidence,
        complexity_strategy_usada=complexity_strategy,
        backend_escolhido=backend_escolhido,
        motivo_escalonamento=motivo,
        resposta=resposta_completa,
        latencia_ms=chunk_final.total_duration_ms or 0.0,
        tokens_entrada=chunk_final.prompt_tokens,
        tokens_saida=chunk_final.completion_tokens,
        cost_prompt_usd=chunk_final.cost_prompt_usd,
        cost_completion_usd=chunk_final.cost_completion_usd,
        custo_estimado_usd=chunk_final.estimated_cost_usd,
        modelo_usado=chunk_final.model_name or getattr(client, "model", None),
        ttft_ms=chunk_final.prompt_eval_duration_ms,
        tps=tps,
        rag_retrieval_ms=rag_retrieval_ms,
        rag_chunks_count=rag_chunks_count,
        rag_avg_score=rag_avg_score,
        rag_chunks=rag_chunks,
        # Fix (revisão final, achado importante 1): usa o provedor QUE
        # REALMENTE classificou (`classification.provider_efetivo`), não o
        # parâmetro bruto `intent_router_provider` pedido pelo chamador —
        # senão uma falha silenciosa do Jev (que degrada para a heurística
        # dentro de `_classify_with_jev`) ficaria atribuída ao Jev na
        # telemetria, corrompendo a comparação entre provedores (ver
        # docs/EVALUATION.md). O sub-fluxo de agendamento em
        # `_emitir_resposta_agendamento` NÃO chama `classify()` (tem sua
        # própria lógica de extração/estado), então continua usando o
        # parâmetro bruto — não há `ClassificationResult` de onde tirar um
        # valor efetivo ali.
        router_provider=classification.provider_efetivo,
        card=_construir_card_vendas(dados_catalogo_vendas)
        or await _construir_card_documento_download(
            db_sessionmaker, documentos, classification.domain, rag_download_threshold
        ),
    )
    logger.info(
        "router_decision",
        extra={"router": {"event": "router_decision", **decisao.model_dump()}},
    )
    yield decisao
