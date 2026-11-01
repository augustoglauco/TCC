"""Classificador por palavras-chave: separa pedido de consulta de conversa comum."""

import re

_CONSULTA_RE = re.compile(
    r"\b(consult[ea]\w*|list[ea]\w*|mostr[ea]\w*|quant[oa]s?|quais|qual(?:is)?\s+(?:o|a|os|as)\s+\w+"
    r"\s+(?:de|do|da|dos|das))\b",
    re.IGNORECASE,
)
_DADOS_RE = re.compile(
    r"\b(produtos?|pedidos?|vendas?|estoque|clientes?|agendamentos?|mensagens?)\b",
    re.IGNORECASE,
)


_GRAFICO_RE = re.compile(r"\b(gr[aá]ficos?|dashboards?)\b", re.IGNORECASE)
_PERGUNTA_RE = re.compile(r"(como|qual|quais|quando|por\s+que|o\s+que)\b", re.IGNORECASE)


_REGRAS_RE = re.compile(r"\b(pol[ií]ticas?|prazos?|regras?|como)\b", re.IGNORECASE)


def detectar_consulta(message: str) -> bool:
    """True se o texto pede uma consulta sobre dados do sistema (e não um gráfico)."""
    if _GRAFICO_RE.search(message) or _REGRAS_RE.search(message):
        return False
    return bool(_CONSULTA_RE.search(message) and _DADOS_RE.search(message))


_ESCRITA_RE = re.compile(
    r"\b(inclu[ai]\w*|cadastr[ae]\w*|adicion[ae]\w*|alter[ae]\w*|mude\w*|renome[ie]\w*|atualiz[ae]\w*"
    r"|d[êe]\s+baixa|baixa\s+(?:de|no|do)|cancel[ae]\w*|conclu[ai]\w*|finaliz[ae]\w*|marque)\b",
    re.IGNORECASE,
)
_DADOS_ESCRITA_RE = re.compile(
    r"\b(produtos?|estoque|vendas?|pedidos?|descri[cç][aã]o|nome)\b", re.IGNORECASE
)


def detectar_escrita(message: str) -> bool:
    """True se o texto pede uma mudança de dados (produto, estoque, venda); gráficos e perguntas
    ("como…", "qual…") não contam."""
    if _GRAFICO_RE.search(message) or _PERGUNTA_RE.match(message.strip()):
        return False
    return bool(_ESCRITA_RE.search(message) and _DADOS_ESCRITA_RE.search(message))
