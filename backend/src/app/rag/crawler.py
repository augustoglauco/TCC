"""Crawler HTTP para o RAG (R4, Fase 2) — navegação BFS a partir de uma URL
semente, com profundidade e teto de páginas parametrizáveis por execução.

# MVP: execução síncrona por chamada, sem fila de background nem
agendamento — ver docs/superpowers/specs/2026-09-19-crawler-paginas-design.md
§2. Só processa respostas `text/html`; outros tipos de conteúdo (imagem, PDF
linkado) são ignorados nesta entrega (RAG multimodal é Fase 3).
"""

from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

_FETCH_TIMEOUT_S = 10.0
_IGNORED_TAGS = ("script", "style", "nav", "footer")


@dataclass
class FetchedPage:
    url: str
    text: str
    links: list[str] = field(default_factory=list)


@dataclass
class CrawlResult:
    pages: list[FetchedPage] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class NonHtmlContentError(Exception):
    """Levantada internamente por `fetch_page` (achado #4 da revisão final)
    quando o fetch teve sucesso (status 2xx) mas o content-type devolvido
    não é `text/html` — ex.: um PDF ou uma imagem linkados a partir de uma
    página HTML. Não é uma falha de fetch: só sinaliza a `crawl()` para
    ignorar essa URL sem contá-la em `errors` (conteúdo não-HTML é
    "ignorado", não um erro — ver docstring do módulo)."""


def _normalize_url(url: str) -> str:
    """Remove o fragmento (`#...`) — necessário para o visited-set do BFS
    tratar âncoras diferentes da mesma página como a mesma URL."""
    parsed = urlparse(url)
    return urlunparse(parsed._replace(fragment=""))


def extract_text_and_links(html: str, base_url: str) -> tuple[str, list[str]]:
    """Extrai texto visível (sem `script`/`style`/`nav`/`footer`) e os links
    (`<a href>`) resolvidos para absoluto via `urljoin` e normalizados."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_IGNORED_TAGS):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())
    links = [_normalize_url(urljoin(base_url, a["href"])) for a in soup.find_all("a", href=True)]
    return text, links


async def fetch_page(client: httpx.AsyncClient, url: str) -> FetchedPage | None:
    """Busca `url`; devolve `None` (sem levantar) em falha real de
    rede/timeout/status não-2xx — cabe ao chamador (`crawl`) registrar como
    erro. Levanta `NonHtmlContentError` quando o fetch teve sucesso mas o
    content-type não é HTML (achado #4 da revisão final: antes retornava
    `None` igual a uma falha real, fazendo `crawl()` contar PDFs/imagens
    linkados como "erro" em vez de simplesmente ignorá-los).

    Usa `response.url` (URL final após redirects, se houver) — não a `url`
    originalmente requisitada — como base para resolver links relativos e
    como `FetchedPage.url` (achado #3 da revisão final: sem isso, links
    relativos de uma página que respondeu com redirect resolviam contra a
    URL errada)."""
    try:
        response = await client.get(url, timeout=_FETCH_TIMEOUT_S, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type:
        raise NonHtmlContentError(url)
    final_url = str(response.url)
    text, links = extract_text_and_links(response.text, final_url)
    return FetchedPage(url=final_url, text=text, links=links)


async def crawl(
    client: httpx.AsyncClient, seed_url: str, depth: int, max_pages: int
) -> CrawlResult:
    """BFS a partir de `seed_url`, restrito ao mesmo host, até `depth`
    saltos ou `max_pages` páginas visitadas (o que vier primeiro).
    Visited-set por URL normalizada evita loop em links de retorno."""
    seed_normalizada = _normalize_url(seed_url)
    seed_host = urlparse(seed_normalizada).netloc

    result = CrawlResult()
    visited: set[str] = set()
    fila: list[tuple[str, int]] = [(seed_normalizada, 0)]

    while fila and len(result.pages) < max_pages:
        url, nivel = fila.pop(0)
        if url in visited:
            continue
        visited.add(url)

        try:
            page = await fetch_page(client, url)
        except NonHtmlContentError:
            # Fetch com sucesso, conteúdo não-HTML: ignorado, não é erro
            # (achado #4 da revisão final).
            continue
        if page is None:
            result.errors.append(url)
            continue

        if urlparse(page.url).netloc != seed_host:
            # A URL originalmente enfileirada era do mesmo host (passou pelo
            # filtro abaixo), mas um redirect levou a um host diferente —
            # tratada como conteúdo ignorado: não conta como página nem
            # alimenta a fila com seus links (achado #3 da revisão final,
            # parte 2: fecha o gap de "restrito ao mesmo host" para o caso
            # de redirect cross-host).
            continue

        result.pages.append(page)

        if nivel >= depth:
            continue
        for link in page.links:
            if link not in visited and urlparse(link).netloc == seed_host:
                fila.append((link, nivel + 1))

    return result
