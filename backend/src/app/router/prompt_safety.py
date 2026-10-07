"""Isolamento por delimitador e detecção log-only de tentativas de prompt
injection (R12/R4, decisão de 2026-10-07) — ver
docs/superpowers/specs/2026-10-07-seguranca-prompt-injection-mcp-design.md.

Duas funções, sem bloquear nunca nenhuma mensagem (decisão C da spec §2):
- `wrap_untrusted`: isola texto não confiável (mensagem do cliente, trecho
  do RAG, texto de OCR de comprovante) em tags que o prompt de sistema
  (ver `app.router.playbooks`) instrui o LLM a tratar como dado, nunca
  como comando.
- `detectar_tentativa_injecao`: heurística pequena, só para logar (nunca
  para alterar o fluxo) — poucos padrões de ALTA confiança, para não gerar
  falso positivo em conversas legítimas de vendas/suporte.
"""

import re

_TAGS: dict[str, tuple[str, str]] = {
    "entrada_cliente": ("<entrada_cliente>", "</entrada_cliente>"),
    "contexto_rag": ("<contexto_rag>", "</contexto_rag>"),
    "texto_comprovante": ("<texto_comprovante>", "</texto_comprovante>"),
}


def wrap_untrusted(label: str, content: str) -> str:
    """Envolve `content` nas tags de `label`, escapando qualquer ocorrência
    literal da própria tag dentro de `content` — sem isso, o cliente
    poderia "fechar" a tag mais cedo e inserir texto fora do isolamento."""
    open_tag, close_tag = _TAGS[label]
    escaped = content.replace(open_tag, f"&lt;{label}&gt;").replace(
        close_tag, f"&lt;/{label}&gt;"
    )
    return f"{open_tag}\n{escaped}\n{close_tag}"


# MVP: poucos padrões de ALTA confiança, não um filtro semântico amplo —
# decisão C da spec (§2): um blocklist agressivo teria falso positivo real
# em conversas de vendas/suporte (ex.: "ignore o que eu falei antes, mudei
# de ideia"). Usado só para logar, nunca para bloquear.
_PADROES_INJECAO_ALTA_CONFIANCA = [
    re.compile(
        r"(ignore|esque[cç]a)\s+(todas\s+as\s+|as\s+)?instru[cç][õo]es(\s+anteriores)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(exiba|revele|mostre)\s+(o\s+seu|seu|o)\s+prompt\s+de\s+sistema",
        re.IGNORECASE,
    ),
    re.compile(r"modo\s+desenvolvedor\s+ativado", re.IGNORECASE),
    re.compile(r"\bdan\s+mode\b", re.IGNORECASE),
]


def detectar_tentativa_injecao(mensagem: str) -> bool:
    """Retorna True se `mensagem` bater algum padrão de alta confiança —
    usado só para emitir um log de visibilidade (ver `app.router.orchestrator`),
    nunca para bloquear ou alterar a resposta ao cliente."""
    return any(padrao.search(mensagem) for padrao in _PADROES_INJECAO_ALTA_CONFIANCA)
