import httpx
import pytest

from app.rag.crawler import NonHtmlContentError, crawl, extract_text_and_links, fetch_page


def test_extract_text_and_links_remove_script_style_nav_footer():
    html = """
    <html><body>
      <nav>menu</nav>
      <script>var x = 1;</script>
      <style>.a{color:red}</style>
      <main><h1>Título</h1><p>Conteúdo real da página.</p></main>
      <footer>rodapé</footer>
    </body></html>
    """

    text, _links = extract_text_and_links(html, "https://exemplo.com")

    assert "menu" not in text
    assert "rodapé" not in text
    assert "var x" not in text
    assert "Título" in text
    assert "Conteúdo real da página." in text


def test_extract_text_and_links_resolve_links_relativos_e_absolutos():
    html = """
    <html><body>
      <a href="/produtos">Produtos</a>
      <a href="https://exemplo.com/suporte#faq">Suporte</a>
      <a href="https://outrosite.com/x">Externo</a>
    </body></html>
    """

    _text, links = extract_text_and_links(html, "https://exemplo.com/")

    assert "https://exemplo.com/produtos" in links
    # fragmento (#faq) é removido pela normalização
    assert "https://exemplo.com/suporte" in links
    assert "https://outrosite.com/x" in links


def _mock_transport(paginas: dict[str, tuple]) -> httpx.MockTransport:
    """`paginas`: url -> (status_code, content_type, corpo) para uma resposta
    normal, ou url -> ("redirect", url_destino) para uma resposta 302 com
    `Location: url_destino` (usado nos testes de redirect, achado #3 da
    revisão final — `httpx.AsyncClient(follow_redirects=True)` segue o
    redirect da mesma forma que em produção)."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url not in paginas:
            return httpx.Response(404)
        entrada = paginas[url]
        if entrada[0] == "redirect":
            _, destino = entrada
            return httpx.Response(302, headers={"location": destino})
        status_code, content_type, corpo = entrada
        return httpx.Response(status_code, headers={"content-type": content_type}, text=corpo)

    return httpx.MockTransport(handler)


async def test_fetch_page_retorna_none_em_erro_http():
    client = httpx.AsyncClient(transport=_mock_transport({}))

    page = await fetch_page(client, "https://exemplo.com/inexistente")

    assert page is None


async def test_fetch_page_levanta_non_html_content_error_para_content_type_nao_html():
    """Achado #4 da revisão final: content-type não-HTML não é uma falha de
    fetch (o `None` de erro real) — `fetch_page` sinaliza esse caso com uma
    exceção própria, para `crawl()` poder ignorá-lo sem contá-lo em
    `errors`."""
    transport = _mock_transport(
        {"https://exemplo.com/arquivo.pdf": (200, "application/pdf", "binario")}
    )
    client = httpx.AsyncClient(transport=transport)

    with pytest.raises(NonHtmlContentError):
        await fetch_page(client, "https://exemplo.com/arquivo.pdf")


async def test_fetch_page_usa_url_final_apos_redirect_para_resolver_links_relativos():
    """Achado #3 da revisão final: se a página respondeu com redirect (ex.:
    `/docs` -> `/docs/v2/`), links relativos nela devem resolver contra a
    URL FINAL (`response.url`), não a originalmente requisitada — senão
    viram URLs quebradas."""
    html = '<html><body><a href="pagina">Pagina</a></body></html>'
    paginas = {
        "https://exemplo.com/docs": ("redirect", "https://exemplo.com/docs/v2/"),
        "https://exemplo.com/docs/v2/": (200, "text/html", html),
    }
    transport = _mock_transport(paginas)
    client = httpx.AsyncClient(transport=transport)

    page = await fetch_page(client, "https://exemplo.com/docs")

    assert page is not None
    assert page.url == "https://exemplo.com/docs/v2/"
    # link relativo "pagina" resolvido contra a URL final pós-redirect — se
    # resolvesse contra "https://exemplo.com/docs" (URL originalmente
    # requisitada), o resultado quebrado seria "https://exemplo.com/pagina".
    assert page.links == ["https://exemplo.com/docs/v2/pagina"]


async def test_fetch_page_retorna_pagina_com_texto_e_links():
    html = '<html><body><p>Olá</p><a href="/outra">Outra</a></body></html>'
    transport = _mock_transport({"https://exemplo.com/": (200, "text/html", html)})
    client = httpx.AsyncClient(transport=transport)

    page = await fetch_page(client, "https://exemplo.com/")

    assert page is not None
    assert "Olá" in page.text
    assert page.links == ["https://exemplo.com/outra"]


def _site_com_grafo_de_links() -> dict[str, tuple[int, str, str]]:
    """Grafo: home -> a -> b -> home (link de retorno), e home -> externo (outro host)."""
    home = (
        200,
        "text/html",
        '<html><body>home <a href="/a">a</a> '
        '<a href="https://outrosite.com/x">externo</a></body></html>',
    )
    pagina_a = (200, "text/html", '<html><body>pagina a <a href="/b">b</a></body></html>')
    pagina_b = (
        200,
        "text/html",
        '<html><body>pagina b <a href="/">home de novo</a></body></html>',
    )
    return {
        "https://exemplo.com/": home,
        "https://exemplo.com/a": pagina_a,
        "https://exemplo.com/b": pagina_b,
    }


async def test_crawl_respeita_profundidade():
    transport = _mock_transport(_site_com_grafo_de_links())
    client = httpx.AsyncClient(transport=transport)

    result = await crawl(client, "https://exemplo.com/", depth=1, max_pages=10)

    urls = {page.url for page in result.pages}
    assert urls == {"https://exemplo.com/", "https://exemplo.com/a"}


async def test_crawl_respeita_max_pages():
    transport = _mock_transport(_site_com_grafo_de_links())
    client = httpx.AsyncClient(transport=transport)

    result = await crawl(client, "https://exemplo.com/", depth=5, max_pages=2)

    assert len(result.pages) == 2


async def test_crawl_nao_segue_host_diferente():
    transport = _mock_transport(_site_com_grafo_de_links())
    client = httpx.AsyncClient(transport=transport)

    result = await crawl(client, "https://exemplo.com/", depth=5, max_pages=10)

    urls = {page.url for page in result.pages}
    assert "https://outrosite.com/x" not in urls


async def test_crawl_evita_loop_com_link_de_retorno():
    transport = _mock_transport(_site_com_grafo_de_links())
    client = httpx.AsyncClient(transport=transport)

    result = await crawl(client, "https://exemplo.com/", depth=5, max_pages=10)

    urls = [page.url for page in result.pages]
    assert len(urls) == len(set(urls))
    assert urls.count("https://exemplo.com/") == 1


async def test_crawl_registra_erro_e_continua():
    paginas = _site_com_grafo_de_links()
    paginas["https://exemplo.com/a"] = (500, "text/html", "erro interno")
    transport = _mock_transport(paginas)
    client = httpx.AsyncClient(transport=transport)

    result = await crawl(client, "https://exemplo.com/", depth=5, max_pages=10)

    assert "https://exemplo.com/a" in result.errors
    urls = {page.url for page in result.pages}
    assert "https://exemplo.com/" in urls
    # "b" só é alcançável a partir de "a", que falhou — não é visitada
    assert "https://exemplo.com/b" not in urls


async def test_crawl_ignora_conteudo_nao_html_sem_contar_como_erro():
    """Achado #4 da revisão final: um link para PDF/imagem não deve virar
    "erro" no resultado do crawl — é conteúdo ignorado, não uma falha."""
    html_home = '<html><body>home <a href="/manual.pdf">manual</a></body></html>'
    paginas = {
        "https://exemplo.com/": (200, "text/html", html_home),
        "https://exemplo.com/manual.pdf": (200, "application/pdf", "binario"),
    }
    transport = _mock_transport(paginas)
    client = httpx.AsyncClient(transport=transport)

    result = await crawl(client, "https://exemplo.com/", depth=1, max_pages=10)

    urls = {page.url for page in result.pages}
    assert urls == {"https://exemplo.com/"}
    assert result.errors == []


async def test_crawl_ignora_pagina_que_redireciona_para_host_diferente():
    """Achado #3 da revisão final: uma URL do mesmo host que redireciona
    para um host diferente deve ser tratada como as páginas de content-type
    não suportado — ignorada, sem entrar em `pages` nem alimentar a fila
    com seus links (o "restrito ao mesmo host" continua valendo mesmo com
    redirect)."""
    html_home = '<html><body>home <a href="/vai-para-fora">vai</a></body></html>'
    paginas = {
        "https://exemplo.com/": (200, "text/html", html_home),
        "https://exemplo.com/vai-para-fora": ("redirect", "https://outrosite.com/pagina"),
        "https://outrosite.com/pagina": (200, "text/html", "<html><body>fora</body></html>"),
    }
    transport = _mock_transport(paginas)
    client = httpx.AsyncClient(transport=transport)

    result = await crawl(client, "https://exemplo.com/", depth=1, max_pages=10)

    urls = {page.url for page in result.pages}
    assert urls == {"https://exemplo.com/"}
    assert result.errors == []
