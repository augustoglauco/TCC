"""Aplicação Streamlit do Cliente Independente MCP B2B."""

import asyncio
import base64

import streamlit as st

try:
    from src.client import B2BAuthError, B2BMCPClient
except ImportError:
    from client import B2BAuthError, B2BMCPClient

# Domínios de atendimento existentes para a busca em manuais (R7) — o
# recurso `manuais://busca/{domain}` exige um deles no caminho da URI.
DOMINIOS_MANUAIS = ["vendas", "suporte", "atendimento"]


def formatar_moeda(valor: float | int | None) -> str:
    """Formata valor numérico para o padrão de moeda brasileiro R$ X.XXX,XX."""
    if valor is None:
        return "R$ 0,00"
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_itens_carrinho(carrinho: list[dict]) -> list[dict]:
    """Extrai produto_id e quantidade dos itens para `cotar`/`consultar_frete`."""
    return [
        {"produto_id": int(item["produto_id"]), "quantidade": int(item["quantidade"])}
        for item in carrinho
    ]


def formatar_itens_pedido(carrinho: list[dict], centro_distribuicao: str) -> list[dict]:
    """Extrai itens para `reservar_pedido`, que exige um centro de distribuição
    por item. # MVP: um único CD aplicado a todo o carrinho — o cliente de
    demonstração não modela split de pedido entre centros."""
    return [
        {
            "produto_id": int(item["produto_id"]),
            "quantidade": int(item["quantidade"]),
            "centro_distribuicao": centro_distribuicao,
        }
        for item in carrinho
    ]


def calcular_resumo_cotacao(cotacao: dict) -> dict:
    """Deriva subtotal bruto e desconto total a partir dos itens de `cotar`.
    O servidor devolve em `preco_unitario` o preço vigente ANTES do desconto
    por volume e em `total` o valor já com desconto; o bruto é, portanto,
    `preco_unitario * quantidade`."""
    subtotal_bruto = sum(
        float(item.get("preco_unitario", 0)) * int(item.get("quantidade", 0))
        for item in cotacao.get("itens", [])
    )
    total = float(cotacao.get("total", 0))
    return {
        "subtotal_bruto": subtotal_bruto,
        "desconto_total": subtotal_bruto - total,
        "total": total,
    }


def calcular_total_pedido(pedido: dict) -> float:
    """`reservar_pedido` não devolve um total agregado — soma os itens."""
    return sum(
        float(item.get("preco_unitario", 0)) * int(item.get("quantidade", 0))
        for item in pedido.get("itens", [])
    )


def necessidade_por_produto(carrinho: list[dict]) -> dict[int, int]:
    """Soma a quantidade por produto (o mesmo produto pode entrar na cesta mais de uma vez)."""
    total: dict[int, int] = {}
    for item in carrinho:
        pid = int(item["produto_id"])
        total[pid] = total.get(pid, 0) + int(item["quantidade"])
    return total


def centros_que_atendem(carrinho: list[dict], saldos: dict[int, dict[str, int]]) -> list[str]:
    """CDs com saldo suficiente para TODOS os itens da cesta. `saldos` é
    `{produto_id: {centro: quantidade}}`. Como o pedido usa um único CD
    (# MVP, ver `formatar_itens_pedido`), só esses CDs servem."""
    comuns: set[str] | None = None
    for pid, quantidade in necessidade_por_produto(carrinho).items():
        ok = {cd for cd, saldo in saldos.get(pid, {}).items() if saldo >= quantidade}
        comuns = ok if comuns is None else comuns & ok
    return sorted(comuns or [])


def linhas_carrinho(carrinho: list[dict], nomes: dict[int, str]) -> list[dict]:
    """Linhas legíveis da cesta (ID, nome e quantidade) para exibição."""
    return [
        {
            "ID": int(item["produto_id"]),
            "Produto": nomes.get(int(item["produto_id"]), f"Produto {item['produto_id']}"),
            "Quantidade": int(item["quantidade"]),
        }
        for item in carrinho
    ]


def linhas_pedido(pedido: dict, nomes: dict[int, str]) -> list[dict]:
    """Itens da reserva devolvida por `reservar_pedido`, com subtotal por linha."""
    return [
        {
            "Produto": nomes.get(int(item["produto_id"]), f"Produto {item['produto_id']}"),
            "Quantidade": int(item["quantidade"]),
            "CD": item.get("centro_distribuicao", ""),
            "Preço unitário": formatar_moeda(item.get("preco_unitario")),
            "Subtotal": formatar_moeda(
                float(item.get("preco_unitario", 0)) * int(item.get("quantidade", 0))
            ),
        }
        for item in pedido.get("itens", [])
    ]


def run_async(coro):
    """Executa corrotina assíncrona dentro do ciclo síncrono do Streamlit."""
    return asyncio.run(coro)


def _exibir(dado, modo_dev: bool):
    """Mostra `dado` como JSON no modo desenvolvedor, senão em formato livre."""
    if modo_dev:
        st.json(dado)
    else:
        st.write(dado)


def _carregar_em_sessao(chave: str, chamada):
    """Executa `chamada()` (fábrica da corrotina) e guarda o resultado em
    `st.session_state[chave]`; erro do servidor vira mensagem na tela."""
    with st.spinner("Lendo recurso..."):
        try:
            st.session_state[chave] = run_async(chamada())
        except Exception as exc:
            st.error(str(exc))


# ==========================
# BARRA LATERAL (SIDEBAR)
# ==========================
def _inicializar_estado():
    if "carrinho" not in st.session_state:
        st.session_state.carrinho = []

    if "conexao_ok" not in st.session_state:
        st.session_state.conexao_ok = False
        st.session_state.info_servidor = None


def _testar_conexao(client: B2BMCPClient):
    with st.spinner("Conectando ao servidor MCP..."):
        try:
            info = run_async(client.testar_conexao())
            st.session_state.conexao_ok = True
            st.session_state.info_servidor = info
            st.success(
                f"Conectado com sucesso ao servidor: **{info['servidor']}** (v{info['versao']})"
            )
        except B2BAuthError as err:
            st.session_state.conexao_ok = False
            st.error(f"Erro de Autenticação: {err}")
        except Exception as err:
            st.session_state.conexao_ok = False
            st.error(f"Falha de Conexão: {err}")


def _render_status_conexao():
    if st.session_state.conexao_ok and st.session_state.info_servidor:
        st.markdown("### 🟢 Status: Conectado")
        st.write(f"**Servidor:** `{st.session_state.info_servidor['servidor']}`")
        st.write(f"**Ferramentas:** {len(st.session_state.info_servidor['ferramentas'])}")
        with st.expander("Ver Ferramentas MCP"):
            for tool in st.session_state.info_servidor["ferramentas"]:
                st.markdown(f"- `{tool}`")
    else:
        st.markdown("### 🔴 Status: Desconectado")
        st.caption("Clique no botão acima para inicializar a sessão com o servidor.")


def _render_sidebar() -> tuple[B2BMCPClient, bool]:
    """Desenha a barra lateral; devolve o cliente configurado e o modo dev."""
    with st.sidebar:
        st.title("🏢 Conexão MCP B2B")
        st.caption("Configurações do cliente e autenticação")

        server_url = st.text_input(
            "URL do Servidor MCP",
            value="http://127.0.0.1:8100/mcp",
            help=(
                "Endpoint HTTP Streamable do servidor MCP corporativo "
                "(MCP_B2B_HOST:MCP_B2B_PORT/mcp)"
            ),
        )

        auth_token = st.text_input(
            "Chave do Parceiro (Bearer)",
            value="",
            type="password",
            help="Chave configurada em MCP_B2B_PARTNER_KEYS no servidor",
        )

        modo_dev = st.checkbox("Modo Desenvolvedor (Exibir JSON-RPC)", value=False)

        client = B2BMCPClient(server_url=server_url, auth_token=auth_token)

        if st.button("🔌 Conectar / Testar Conexão", use_container_width=True):
            _testar_conexao(client)

        st.divider()
        _render_status_conexao()
    return client, modo_dev


# --------------------------
# TAB 1: CATÁLOGO & RECURSOS
# --------------------------
def _render_catalogo(client: B2BMCPClient, modo_dev: bool):
    st.subheader("Catálogo de Produtos (`catalogo://produtos`)")
    categoria_filtro = st.text_input("Filtrar por categoria (opcional):", key="categoria_filtro")
    if st.button("Carregar Catálogo", use_container_width=True):
        _carregar_em_sessao("catalogo", lambda: client.obter_catalogo(categoria_filtro or None))

    if "catalogo" in st.session_state:
        st.markdown("#### Produtos no Catálogo")
        _exibir(st.session_state.catalogo, modo_dev)


def _render_estoque_precos(client: B2BMCPClient, modo_dev: bool):
    st.markdown("#### Estoque e Preços por Produto")
    produto_id_recurso = st.number_input(
        "ID do Produto", min_value=1, value=1, step=1, key="produto_id_recurso"
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Consultar Estoque (`estoque://produtos/{id}`)", use_container_width=True):
            _carregar_em_sessao("estoque", lambda: client.obter_estoque(int(produto_id_recurso)))
    with col2:
        if st.button("Tabela de Preços (`precos://produtos/{id}`)", use_container_width=True):
            _carregar_em_sessao("precos", lambda: client.obter_precos(int(produto_id_recurso)))

    if "estoque" in st.session_state:
        st.markdown("#### Saldos de Estoque por CD")
        _exibir(st.session_state.estoque, modo_dev)

    if "precos" in st.session_state:
        st.markdown("#### Preço e Faixas de Desconto")
        _exibir(st.session_state.precos, modo_dev)


def _buscar_manual(client: B2BMCPClient, domain_manual: str, query_manual: str, modo_dev: bool):
    with st.spinner("Pesquisando na base vetorial via MCP..."):
        try:
            res_manual = run_async(client.pesquisar_manuais(domain_manual, query_manual))
            _exibir(res_manual, modo_dev)
        except Exception as exc:
            st.error(str(exc))


def _render_busca_manuais(client: B2BMCPClient, modo_dev: bool):
    st.markdown("#### Pesquisa Semântica em Manuais (`manuais://busca/{domain}`)")
    col_dom, col_query = st.columns([1, 3])
    with col_dom:
        domain_manual = st.selectbox("Domínio", DOMINIOS_MANUAIS)
    with col_query:
        query_manual = st.text_input(
            "Buscar dúvidas ou especificações técnicas:",
            placeholder="ex.: cabo de rede e alcance máximo",
        )
    if st.button("Buscar Manual") and query_manual:
        _buscar_manual(client, domain_manual, query_manual, modo_dev)


def _render_tab_recursos(client: B2BMCPClient, modo_dev: bool):
    _render_catalogo(client, modo_dev)
    st.divider()
    _render_estoque_precos(client, modo_dev)
    st.divider()
    _render_busca_manuais(client, modo_dev)


# --------------------------
# TAB 2: COTAÇÃO B2B
# --------------------------
def _render_adicionar_item():
    col_add1, col_add2, col_add3 = st.columns([3, 2, 2])
    with col_add1:
        p_id = st.number_input("ID do Produto", min_value=1, value=1, step=1)
    with col_add2:
        p_qtd = st.number_input("Quantidade", min_value=1, value=5, step=1)
    with col_add3:
        st.write("")
        st.write("")
        if st.button("➕ Adicionar à Cotação", use_container_width=True):
            st.session_state.carrinho.append({"produto_id": p_id, "quantidade": p_qtd})
            st.success(f"Produto {p_id} (Qtd: {p_qtd}) adicionado!")


def _calcular_cotacao(client: B2BMCPClient, modo_dev: bool):
    with st.spinner("Calculando cotação no MCP..."):
        try:
            itens_envio = formatar_itens_carrinho(st.session_state.carrinho)
            cotacao = run_async(client.cotar(itens_envio))
            resumo = calcular_resumo_cotacao(cotacao)

            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Subtotal Bruto", formatar_moeda(resumo["subtotal_bruto"]))
            col_m2.metric("Desconto Total Volume", formatar_moeda(resumo["desconto_total"]))
            col_m3.metric("Total Líquido Cotação", formatar_moeda(resumo["total"]))

            st.markdown("##### Detalhamento por Item:")
            # if/else em vez de expressão condicional: o "magic" do Streamlit exibiria o
            # valor devolvido (um DeltaGenerator) como texto na tela.
            if modo_dev:
                st.json(cotacao)
            else:
                st.table(cotacao.get("itens", []))
        except Exception as exc:
            st.error(f"Erro ao cotar: {exc}")


def _render_tab_cotar(client: B2BMCPClient, modo_dev: bool):
    st.subheader("Cotação Comercial com Desconto por Volume (`cotar`)")
    _render_adicionar_item()

    if not st.session_state.carrinho:
        st.info("Adicione itens acima para simular a cotação com a tabela de parceiro.")
        return

    st.markdown("##### Itens na Cesta de Cotação:")
    st.table(linhas_carrinho(st.session_state.carrinho, _nomes(_infos_da_cesta(client))))
    if st.button("Limpar Cesta"):
        st.session_state.carrinho = []
        st.rerun()

    if st.button("Calcular Cotação B2B", type="primary"):
        _calcular_cotacao(client, modo_dev)


# --------------------------
# TAB 3: CONSULTA DE FRETE
# --------------------------
def _calcular_frete(client: B2BMCPClient, cep_destino: str, modo_dev: bool):
    with st.spinner("Consultando estimativa de frete via MCP..."):
        try:
            itens_envio = formatar_itens_carrinho(st.session_state.carrinho)
            res_frete = run_async(client.consultar_frete(cep_destino, itens_envio))
            col_f1, col_f2 = st.columns(2)
            col_f1.metric("Prazo de Entrega", f"{res_frete.get('prazo_dias', '-')} dias úteis")
            col_f2.metric("Valor do Frete", formatar_moeda(res_frete.get("custo_estimado", 0)))
            _exibir(res_frete, modo_dev)
        except Exception as exc:
            st.error(f"Erro ao consultar frete: {exc}")


def _render_tab_frete(client: B2BMCPClient, modo_dev: bool):
    st.subheader("Cálculo de Frete e Prazos (`consultar_frete`)")
    cep_destino = st.text_input("CEP de Destino:", value="01310-100", max_chars=9)

    if st.button("Calcular Frete dos Itens"):
        if not st.session_state.carrinho:
            st.warning("Adicione produtos na cotação para calcular o frete.")
        else:
            _calcular_frete(client, cep_destino, modo_dev)


# --------------------------
# TAB 4: COMPATIBILIDADE
# --------------------------
def _render_tab_compatibilidade(client: B2BMCPClient, modo_dev: bool):
    st.subheader("Validador de Compatibilidade Técnica (`validar_compatibilidade`)")
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        prod_a = st.number_input("ID do Produto", min_value=1, value=1, step=1, key="comp_a")
    with col_c2:
        prod_b = st.number_input(
            "ID do Produto Relacionado", min_value=1, value=2, step=1, key="comp_b"
        )

    if st.button("Verificar Compatibilidade Técnica", use_container_width=True):
        with st.spinner("Validando compatibilidade no MCP..."):
            try:
                res_comp = run_async(client.validar_compatibilidade(prod_a, prod_b))
                if res_comp.get("compativel", False):
                    st.success("✅ **Produtos Compatíveis!**")
                else:
                    st.warning("⚠️ **Produtos Não Compatíveis.**")

                if modo_dev:
                    st.json(res_comp)
            except Exception as exc:
                st.error(f"Erro ao verificar compatibilidade: {exc}")


# --------------------------
# TAB 5: FECHAR PEDIDO
# --------------------------
def _info_produto(client: B2BMCPClient, produto_id: int) -> dict:
    """Nome e saldo por CD de um produto, em cache na sessão (limpo após cada pedido).
    Falha de leitura devolve só um nome genérico, sem cachear."""
    cache = st.session_state.setdefault("produtos_info", {})
    if produto_id in cache:
        return cache[produto_id]
    try:
        detalhe = run_async(client.obter_produto_detalhe(produto_id))
        estoque = run_async(client.obter_estoque(produto_id))
    except Exception:
        return {"nome": f"Produto {produto_id}", "centros": {}}
    cache[produto_id] = {
        "nome": detalhe.get("nome", f"Produto {produto_id}"),
        "centros": {
            c["centro_distribuicao"]: int(c["quantidade"]) for c in estoque.get("centros", [])
        },
    }
    return cache[produto_id]


def _infos_da_cesta(client: B2BMCPClient) -> dict[int, dict]:
    ids = necessidade_por_produto(st.session_state.carrinho)
    return {pid: _info_produto(client, pid) for pid in ids}


def _nomes(infos: dict[int, dict]) -> dict[int, str]:
    return {pid: info["nome"] for pid, info in infos.items()}


def _previa_valor(client: B2BMCPClient) -> dict | None:
    """Cotação da cesta atual (cache por conteúdo da cesta): o valor antes de confirmar."""
    chave = tuple((int(i["produto_id"]), int(i["quantidade"])) for i in st.session_state.carrinho)
    cache = st.session_state.get("previa_cotacao")
    if cache and cache["chave"] == chave:
        return cache["cotacao"]
    try:
        cotacao = run_async(client.cotar(formatar_itens_carrinho(st.session_state.carrinho)))
    except Exception as exc:
        st.warning(f"Não foi possível calcular a prévia de valor: {exc}")
        return None
    st.session_state["previa_cotacao"] = {"chave": chave, "cotacao": cotacao}
    return cotacao


def _render_previa(client: B2BMCPClient, infos: dict[int, dict]):
    st.markdown("##### Itens que serão reservados:")
    st.table(linhas_carrinho(st.session_state.carrinho, _nomes(infos)))
    cotacao = _previa_valor(client)
    if cotacao is None:
        return
    resumo = calcular_resumo_cotacao(cotacao)
    col1, col2, col3 = st.columns(3)
    col1.metric("Subtotal bruto", formatar_moeda(resumo["subtotal_bruto"]))
    col2.metric("Desconto por volume", formatar_moeda(resumo["desconto_total"]))
    col3.metric("Valor estimado da reserva", formatar_moeda(resumo["total"]))


def _escolher_cd(infos: dict[int, dict]) -> str:
    """CD da reserva: só os que têm saldo para toda a cesta; sem dados de estoque, texto livre."""
    saldos = {pid: info["centros"] for pid, info in infos.items()}
    if not any(saldos.values()):
        return st.text_input("Centro de Distribuição para Reserva:", value="SP", key="pedido_cd")
    centros = centros_que_atendem(st.session_state.carrinho, saldos)
    if not centros:
        st.error(
            "Nenhum centro de distribuição tem saldo para todos os itens da cesta. "
            "Reduza as quantidades ou remova itens (o pedido usa um único CD)."
        )
        return ""
    return st.selectbox(
        "Centro de Distribuição para Reserva:",
        centros,
        key="pedido_cd_sel",
        help="Só aparecem CDs com saldo para todos os itens. Aplicado a todos os itens da cesta.",
    )


def _emitir_pedido(client: B2BMCPClient, centro_distribuicao: str, infos: dict[int, dict]):
    with st.spinner("Processando pedido e reserva no servidor MCP..."):
        try:
            itens_envio = formatar_itens_pedido(st.session_state.carrinho, centro_distribuicao)
            resultado = run_async(client.reservar_pedido(itens_envio))
        except Exception as exc:
            st.error(f"Falha ao reservar pedido: {exc}")
            return
    cotacao = (st.session_state.get("previa_cotacao") or {}).get("cotacao") or {}
    st.session_state["ultimo_pedido_id"] = resultado.get("id")
    st.session_state["pedido_emitido"] = {
        "pedido": resultado,
        "nomes": _nomes(infos),
        "total_cotacao": float(cotacao["total"]) if "total" in cotacao else None,
    }
    st.session_state.carrinho = []
    st.session_state.pop("previa_cotacao", None)
    st.session_state.pop("produtos_info", None)
    st.session_state["pedido_confirma_n"] = st.session_state.get("pedido_confirma_n", 0) + 1
    st.rerun()


def _render_pedido_emitido(modo_dev: bool):
    emitido = st.session_state.get("pedido_emitido")
    if not emitido:
        return
    pedido = emitido["pedido"]
    total = calcular_total_pedido(pedido)
    st.success("🎉 **Reserva criada com sucesso!** O estoque foi separado; falta o pagamento.")
    st.write("**Número do Pedido (copie para a aba de conversão):**")
    st.code(str(pedido.get("id", "N/A")), language=None)
    st.write(
        f"**Status:** `{pedido.get('status', 'reservado')}` (aguardando pagamento) · "
        f"**Criado em:** {pedido.get('criado_em', '—')}"
    )
    st.table(linhas_pedido(pedido, emitido["nomes"]))
    st.metric("Valor a pagar", formatar_moeda(total))
    cotado = emitido["total_cotacao"]
    if cotado is not None and abs(total - cotado) > 0.005:
        st.warning(
            f"A cotação indicava {formatar_moeda(cotado)} (com desconto por volume), "
            f"mas a reserva foi gravada em {formatar_moeda(total)}."
        )
    st.info(
        "**Próximo passo:** pague o valor acima e envie o comprovante na aba "
        "**🧾 Converter Reserva / Comprovante** (o número do pedido já vem preenchido)."
    )
    if modo_dev:
        st.json(pedido)
    if st.button("Fazer novo pedido"):
        st.session_state.pop("pedido_emitido", None)
        st.rerun()


def _render_tab_pedido(client: B2BMCPClient, modo_dev: bool):
    st.subheader("Emissão de Pedido B2B (`reservar_pedido`)")
    st.warning(
        "Atenção: A chamada a esta ferramenta reserva e baixa o estoque "
        "real dos produtos no sistema."
    )
    _render_pedido_emitido(modo_dev)

    if not st.session_state.carrinho:
        st.info("Cesta vazia. Adicione itens na aba **Cotação de Preços** para fechar um pedido.")
        return

    infos = _infos_da_cesta(client)
    _render_previa(client, infos)
    centro_distribuicao = _escolher_cd(infos)
    confirma = st.checkbox(
        "Confirmo que desejo efetivar a reserva de estoque e emitir o pedido oficial.",
        key=f"pedido_confirma_{st.session_state.get('pedido_confirma_n', 0)}",
    )
    pode_emitir = confirma and bool(centro_distribuicao)
    if st.button("🛒 Emitir Pedido B2B", type="primary", disabled=not pode_emitir):
        _emitir_pedido(client, centro_distribuicao, infos)


# --------------------------
# TAB 6: CONVERSÃO DE RESERVA
# --------------------------
def _ler_comprovante(tipo_entrada: str) -> tuple[str, str]:
    """Lê o comprovante informado; devolve (conteúdo base64 ou texto, nome do arquivo)."""
    if not tipo_entrada.startswith("Arquivo"):
        texto = st.text_area(
            "Cole o texto do comprovante ou dados da transferência:",
            height=120,
            placeholder="Comprovante de Transferência PIX\nValor: R$ ...",
        )
        return (texto.strip() if texto else ""), "comprovante.txt"

    upload = st.file_uploader(
        "Selecione o arquivo do comprovante:", type=["pdf", "png", "jpg", "jpeg", "webp"]
    )
    if upload is None:
        return "", "comprovante.txt"
    return base64.b64encode(upload.getvalue()).decode("utf-8"), upload.name


def _converter_reserva(
    client: B2BMCPClient, pedido_id: str, comprovante: str, nome_arquivo: str, modo_dev: bool
):
    with st.spinner("Avaliando comprovante com IA Multimodal e convertendo reserva..."):
        try:
            resultado_conv = run_async(
                client.converter_reserva_venda(
                    pedido_id=pedido_id,
                    comprovante_base64_ou_texto=comprovante,
                    nome_arquivo=nome_arquivo,
                )
            )
            st.balloons()
            st.success(f"🎉 {resultado_conv.get('mensagem', 'Conversão realizada com sucesso!')}")
            st.write(f"**Status Atual:** `{resultado_conv.get('status')}`")
            st.write(f"**Tipo de Conversão:** `{resultado_conv.get('tipo_conversao')}`")
            st.write(f"**Convertido por:** `{resultado_conv.get('convertido_por')}`")
            if resultado_conv.get("parecer"):
                st.markdown("##### 📄 Parecer Financeiro da IA:")
                st.json(resultado_conv["parecer"])
            if modo_dev:
                st.json(resultado_conv)
        except Exception as exc:
            st.error(f"Falha na validação ou conversão: {exc}")


def _render_tab_conversao(client: B2BMCPClient, modo_dev: bool):
    st.subheader("Comprovação Financeira & Conversão de Reserva (`converter_reserva_venda`)")
    st.info(
        "Envie o comprovante de pagamento (PIX, TED, Boleto) referente a uma "
        "reserva para validação via IA Multimodal e conversão em venda "
        "faturada."
    )

    pedido_id_sugerido = st.session_state.get("ultimo_pedido_id", "")
    pedido_id_input = st.text_input(
        "ID do Pedido / Reserva (UUID):",
        value=str(pedido_id_sugerido or ""),
        key="conv_pedido_id",
    )

    tipo_entrada = st.radio(
        "Formato do Comprovante:",
        ["Arquivo (PDF, PNG, JPG)", "Texto / Linha Digitável / PIX"],
        horizontal=True,
    )
    comprovante, nome_arquivo = _ler_comprovante(tipo_entrada)

    if st.button("🚀 Enviar Comprovante & Converter em Venda", type="primary"):
        if not pedido_id_input.strip():
            st.error("Informe o ID do Pedido / Reserva.")
        elif not comprovante:
            st.error("Forneça o arquivo ou texto do comprovante de pagamento.")
        else:
            _converter_reserva(client, pedido_id_input.strip(), comprovante, nome_arquivo, modo_dev)


def main():
    st.set_page_config(
        page_title="Portal B2B - Cliente MCP",
        page_icon="🏢",
        layout="wide",
    )
    _inicializar_estado()
    client, modo_dev = _render_sidebar()

    # ==========================
    # CORPO PRINCIPAL
    # ==========================
    st.title("Portal do Parceiro B2B — Demonstração MCP")
    st.markdown(
        "Este portal simula a integração de um cliente/parceiro comercial corporativo consumindo "
        "recursos de catálogo e ferramentas transacionais expostas via "
        "**Model Context Protocol (MCP)**."
    )

    abas = st.tabs(
        [
            "📦 Catálogo & Recursos",
            "💰 Cotação de Preços",
            "🚚 Consulta de Frete",
            "🔍 Compatibilidade",
            "🛒 Fechar Pedido",
            "🧾 Converter Reserva / Comprovante",
        ]
    )
    renderizadores = [
        _render_tab_recursos,
        _render_tab_cotar,
        _render_tab_frete,
        _render_tab_compatibilidade,
        _render_tab_pedido,
        _render_tab_conversao,
    ]
    for aba, renderizar in zip(abas, renderizadores, strict=True):
        with aba:
            renderizar(client, modo_dev)


if __name__ == "__main__":
    main()
