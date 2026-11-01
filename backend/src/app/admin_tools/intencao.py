"""Classificador por palavras-chave: separa pedido de consulta de conversa comum."""

import re

_CONSULTA_RE = re.compile(
    r"\b(consult[ea]\w*|list[ea]\w*|mostr[ea]\w*|quant[oa]s?|qual(?:is)?\s+(?:o|a|os|as)\s+\w+"
    r"\s+(?:de|do|da|dos|das))\b",
    re.IGNORECASE,
)
_DADOS_RE = re.compile(
    r"\b(produtos?|pedidos?|vendas?|estoque|clientes?|agendamentos?|mensagens?)\b",
    re.IGNORECASE,
)


def detectar_consulta(message: str) -> bool:
    """True se o texto pede uma consulta sobre dados do sistema (e não um gráfico)."""
    if re.search(r"\b(gr[aá]fico|dashboard)\b", message, re.IGNORECASE):
        return False
    return bool(_CONSULTA_RE.search(message) and _DADOS_RE.search(message))
