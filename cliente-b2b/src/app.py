"""Aplicação Streamlit do Cliente Independente MCP B2B."""

import asyncio
import base64
import streamlit as st

try:
    from src.client import B2BMCPClient, B2BAuthError, B2BMCPError
except ImportError:
    from client import B2BMCPClient, B2BAuthError, B2BMCPError

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
    return [{"produto_id": int(item["produto_id"]), "quantidade": int(item["quantidade"])} for item in carrinho]


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
    """Deriva subtotal bruto e desconto total a partir dos itens de `cotar`
    (o servidor devolve só preço líquido por item e o total geral)."""
    subtotal_bruto = 0.0
    for item in cotacao.get("itens", []):
        preco_unitario = float(item.get("preco_unitario", 0))
        percentual = float(item.get("percentual_desconto_aplicado", 0))
        quantidade = int(item.get("quantidade", 0))
        if percentual < 100:
            preco_cheio = preco_unitario / (1 - percentual / 100) if percentual else preco_unitario
        else:
            preco_cheio = preco_unitario
        subtotal_bruto += preco_cheio * quantidade
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


def run_async(coro):
    """Executa corrotina assíncrona dentro do ciclo síncrono do Streamlit."""
    return asyncio.run(coro)


def main():
    st.set_page_config(
        page_title="Portal B2B - Cliente MCP",
        page_icon="🏢",
        layout="wide",
    )

    if "carrinho" not in st.session_state:
        st.session_state.carrinho = []

    if "conexao_ok" not in st.session_state:
        st.session_state.conexao_ok = False
        st.session_state.info_servidor = None

    # ==========================
    # BARRA LATERAL (SIDEBAR)
    # ==========================
    with st.sidebar:
        st.title("🏢 Conexão MCP B2B")
        st.caption("Configurações do cliente e autenticação")

        server_url = st.text_input(
            "URL do Servidor MCP",
            value="http://127.0.0.1:8100/mcp",
            help="Endpoint HTTP Streamable do servidor MCP corporativo (MCP_B2B_HOST:MCP_B2B_PORT/mcp)",
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
            with st.spinner("Conectando ao servidor MCP..."):
                try:
                    info = run_async(client.testar_conexao())
                    st.session_state.conexao_ok = True
                    st.session_state.info_servidor = info
                    st.success(f"Conectado com sucesso ao servidor: **{info['servidor']}** (v{info['versao']})")
                except B2BAuthError as err:
                    st.session_state.conexao_ok = False
                    st.error(f"Erro de Autenticação: {err}")
                except Exception as err:
                    st.session_state.conexao_ok = False
                    st.error(f"Falha de Conexão: {err}")

        st.divider()

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

    # ==========================
    # CORPO PRINCIPAL
    # ==========================
    st.title("Portal do Parceiro B2B — Demonstração MCP")
    st.markdown(
        "Este portal simula a integração de um cliente/parceiro comercial corporativo consumindo "
        "recursos de catálogo e ferramentas transacionais expostas via **Model Context Protocol (MCP)**."
    )

    tab_recursos, tab_cotar, tab_frete, tab_comp, tab_pedido, tab_conversao = st.tabs([
        "📦 Catálogo & Recursos",
        "💰 Cotação de Preços",
        "🚚 Consulta de Frete",
        "🔍 Compatibilidade",
        "🛒 Fechar Pedido",
        "🧾 Converter Reserva / Comprovante",
    ])

    # --------------------------
    # TAB 1: CATÁLOGO & RECURSOS
    # --------------------------
    with tab_recursos:
        st.subheader("Catálogo de Produtos (`catalogo://produtos`)")
        categoria_filtro = st.text_input("Filtrar por categoria (opcional):", key="categoria_filtro")
        if st.button("Carregar Catálogo", use_container_width=True):
            with st.spinner("Lendo recurso..."):
                try:
                    st.session_state.catalogo = run_async(client.obter_catalogo(categoria_filtro or None))
                except Exception as exc:
                    st.error(str(exc))

        if "catalogo" in st.session_state:
            st.markdown("#### Produtos no Catálogo")
            st.json(st.session_state.catalogo) if modo_dev else st.write(st.session_state.catalogo)

        st.divider()
        st.markdown("#### Estoque e Preços por Produto")
        produto_id_recurso = st.number_input("ID do Produto", min_value=1, value=1, step=1, key="produto_id_recurso")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Consultar Estoque (`estoque://produtos/{id}`)", use_container_width=True):
                with st.spinner("Lendo recurso..."):
                    try:
                        st.session_state.estoque = run_async(client.obter_estoque(int(produto_id_recurso)))
                    except Exception as exc:
                        st.error(str(exc))
        with col2:
            if st.button("Tabela de Preços (`precos://produtos/{id}`)", use_container_width=True):
                with st.spinner("Lendo recurso..."):
                    try:
                        st.session_state.precos = run_async(client.obter_precos(int(produto_id_recurso)))
                    except Exception as exc:
                        st.error(str(exc))

        if "estoque" in st.session_state:
            st.markdown("#### Saldos de Estoque por CD")
            st.json(st.session_state.estoque) if modo_dev else st.write(st.session_state.estoque)

        if "precos" in st.session_state:
            st.markdown("#### Preço e Faixas de Desconto")
            st.json(st.session_state.precos) if modo_dev else st.write(st.session_state.precos)

        st.divider()
        st.markdown("#### Pesquisa Semântica em Manuais (`manuais://busca/{domain}`)")
        col_dom, col_query = st.columns([1, 3])
        with col_dom:
            domain_manual = st.selectbox("Domínio", DOMINIOS_MANUAIS)
        with col_query:
            query_manual = st.text_input("Buscar dúvidas ou especificações técnicas:", placeholder="ex.: cabo de rede e alcance máximo")
        if st.button("Buscar Manual"):
            if query_manual:
                with st.spinner("Pesquisando na base vetorial via MCP..."):
                    try:
                        res_manual = run_async(client.pesquisar_manuais(domain_manual, query_manual))
                        if modo_dev:
                            st.json(res_manual)
                        else:
                            st.write(res_manual)
                    except Exception as exc:
                        st.error(str(exc))

    # --------------------------
    # TAB 2: COTAÇÃO B2B
    # --------------------------
    with tab_cotar:
        st.subheader("Cotação Comercial com Desconto por Volume (`cotar`)")

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

        if st.session_state.carrinho:
            st.markdown("##### Itens na Cesta de Cotação:")
            st.table(st.session_state.carrinho)
            if st.button("Limpar Cesta"):
                st.session_state.carrinho = []
                st.rerun()

            if st.button("Calcular Cotação B2B", type="primary"):
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
                        st.json(cotacao) if modo_dev else st.table(cotacao.get("itens", []))
                    except Exception as exc:
                        st.error(f"Erro ao cotar: {exc}")
        else:
            st.info("Adicione itens acima para simular a cotação com a tabela de parceiro.")

    # --------------------------
    # TAB 3: CONSULTA DE FRETE
    # --------------------------
    with tab_frete:
        st.subheader("Cálculo de Frete e Prazos (`consultar_frete`)")
        cep_destino = st.text_input("CEP de Destino:", value="01310-100", max_chars=9)

        if st.button("Calcular Frete dos Itens"):
            if not st.session_state.carrinho:
                st.warning("Adicione produtos na cotação para calcular o frete.")
            else:
                with st.spinner("Consultando estimativa de frete via MCP..."):
                    try:
                        itens_envio = formatar_itens_carrinho(st.session_state.carrinho)
                        res_frete = run_async(client.consultar_frete(cep_destino, itens_envio))
                        col_f1, col_f2 = st.columns(2)
                        col_f1.metric("Prazo de Entrega", f"{res_frete.get('prazo_dias', '-')} dias úteis")
                        col_f2.metric("Valor do Frete", formatar_moeda(res_frete.get("custo_estimado", 0)))
                        st.json(res_frete) if modo_dev else st.write(res_frete)
                    except Exception as exc:
                        st.error(f"Erro ao consultar frete: {exc}")

    # --------------------------
    # TAB 4: COMPATIBILIDADE
    # --------------------------
    with tab_comp:
        st.subheader("Validador de Compatibilidade Técnica (`validar_compatibilidade`)")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            prod_a = st.number_input("ID do Produto", min_value=1, value=1, step=1, key="comp_a")
        with col_c2:
            prod_b = st.number_input("ID do Produto Relacionado", min_value=1, value=2, step=1, key="comp_b")

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
    with tab_pedido:
        st.subheader("Emissão de Pedido B2B (`reservar_pedido`)")
        st.warning("Atenção: A chamada a esta ferramenta reserva e baixa o estoque real dos produtos no sistema.")

        centro_distribuicao = st.text_input(
            "Centro de Distribuição para Reserva:",
            value="SP",
            key="pedido_cd",
            help="Aplicado a todos os itens da cesta (ver limitação no README).",
        )

        confirma_pedido = st.checkbox("Confirmo que desejo efetivar a reserva de estoque e emitir o pedido oficial.")

        if st.button("🛒 Emitir Pedido B2B", type="primary", disabled=not confirma_pedido):
            if not st.session_state.carrinho:
                st.error("Cesta de produtos está vazia. Adicione itens na aba Cotação antes de fechar o pedido.")
            else:
                with st.spinner("Processando pedido e reserva no servidor MCP..."):
                    try:
                        itens_envio = formatar_itens_pedido(st.session_state.carrinho, centro_distribuicao)
                        resultado_pedido = run_async(client.reservar_pedido(itens_envio))
                        st.balloons()
                        st.session_state["ultimo_pedido_id"] = resultado_pedido.get("id")
                        st.success("🎉 **Pedido B2B Criado com Sucesso!**")
                        st.write(f"**Número do Pedido:** `{resultado_pedido.get('id', 'N/A')}`")
                        st.write(f"**Status:** `{resultado_pedido.get('status', 'reservado')}`")
                        st.write(f"**Total Faturado:** {formatar_moeda(calcular_total_pedido(resultado_pedido))}")
                        if modo_dev:
                            st.json(resultado_pedido)
                    except Exception as exc:
                        st.error(f"Falha ao reservar pedido: {exc}")

    # --------------------------
    # TAB 6: CONVERSÃO DE RESERVA
    # --------------------------
    with tab_conversao:
        st.subheader("Comprovação Financeira & Conversão de Reserva (`converter_reserva_venda`)")
        st.info("Envie o comprovante de pagamento (PIX, TED, Boleto) referente a uma reserva para validação via IA Multimodal e conversão em venda faturada.")

        pedido_id_sugerido = st.session_state.get("ultimo_pedido_id", "")
        pedido_id_input = st.text_input("ID do Pedido / Reserva (UUID):", value=str(pedido_id_sugerido or ""), key="conv_pedido_id")

        tipo_entrada = st.radio("Formato do Comprovante:", ["Arquivo (PDF, PNG, JPG)", "Texto / Linha Digitável / PIX"], horizontal=True)

        comprovante_b64_ou_texto = ""
        nome_arquivo = "comprovante.txt"

        if tipo_entrada.startswith("Arquivo"):
            upload_comprovante = st.file_uploader("Selecione o arquivo do comprovante:", type=["pdf", "png", "jpg", "jpeg", "webp"])
            if upload_comprovante is not None:
                nome_arquivo = upload_comprovante.name
                comprovante_b64_ou_texto = base64.b64encode(upload_comprovante.getvalue()).decode("utf-8")
        else:
            texto_comprovante_input = st.text_area("Cole o texto do comprovante ou dados da transferência:", height=120, placeholder="Comprovante de Transferência PIX\nValor: R$ ...")
            if texto_comprovante_input:
                comprovante_b64_ou_texto = texto_comprovante_input.strip()

        if st.button("🚀 Enviar Comprovante & Converter em Venda", type="primary"):
            if not pedido_id_input.strip():
                st.error("Informe o ID do Pedido / Reserva.")
            elif not comprovante_b64_ou_texto:
                st.error("Forneça o arquivo ou texto do comprovante de pagamento.")
            else:
                with st.spinner("Avaliando comprovante com IA Multimodal e convertendo reserva..."):
                    try:
                        resultado_conv = run_async(
                            client.converter_reserva_venda(
                                pedido_id=pedido_id_input.strip(),
                                comprovante_base64_ou_texto=comprovante_b64_ou_texto,
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


if __name__ == "__main__":
    main()
