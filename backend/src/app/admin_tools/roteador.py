"""Interpreta, com o LLM local, qual ferramenta de escrita o Admin pediu."""

import json
import logging
import re
from typing import Any

from app.admin_tools.ferramentas import FERRAMENTAS

logger = logging.getLogger(__name__)

PROMPT_FERRAMENTAS = """Você traduz um pedido do administrador em UMA ação do sistema.
Ações disponíveis e seus argumentos:
- incluir_produto: nome, descricao, preco (número), categoria
- alterar_nome_produto: produto (id ou nome), novo_nome
- alterar_descricao_produto: produto (id ou nome), nova_descricao
- baixa_estoque: produto (id ou nome), cd (centro de distribuição), quantidade (inteiro)
- atualizar_venda: pedido_id (UUID), novo_status ("venda_concluida" ou "cancelada")
Responda APENAS com JSON: {{"ferramenta": "<ação>", "argumentos": {{...}}}}.
Se o pedido não corresponder a nenhuma ação, responda {{"ferramenta": null}}.
Não invente valores que o administrador não informou.

Pedido: {pedido}
"""


async def interpretar_escrita(llm_client: Any, message: str) -> dict[str, Any] | None:
    """`{"ferramenta", "argumentos"}` ou None (LLM fora, JSON ruim, ferramenta desconhecida)."""
    try:
        resposta = await llm_client.generate(PROMPT_FERRAMENTAS.format(pedido=message))
    except Exception:  # fronteira de isolamento: LLM fora do ar não derruba o turno
        logger.exception("falha_ao_interpretar_escrita_admin")
        return None
    bruto = str(getattr(resposta, "response", getattr(resposta, "text", resposta)))
    achado = re.search(r"\{.*\}", bruto, re.DOTALL)
    if not achado:
        return None
    try:
        dados = json.loads(achado.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(dados, dict):
        return None
    nome, argumentos = dados.get("ferramenta"), dados.get("argumentos")
    if nome not in FERRAMENTAS or not isinstance(argumentos, dict):
        return None
    return {"ferramenta": nome, "argumentos": argumentos}
