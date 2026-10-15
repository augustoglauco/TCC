"""Cérebro de IA do agente de estoque (R13): um LLM decide o risco de falta.

Recebe só fatos estruturados (nada de texto livre de usuário, então não há
vetor de prompt injection) e devolve JSON. Qualquer falha — modelo fora do
ar, timeout, JSON inválido — devolve `None` e o chamador cai na regra
determinística.

# MVP: uma chamada por produto avaliado; sem cache, sem few-shot.
"""

import json
import logging
from typing import Any

from app.agents.estoque_preditivo import AGENTE_IA, Decisao, FatosEstoque
from app.router.classifier import strip_code_fence
from app.services.ai_usage import registrar_uso_ia

logger = logging.getLogger("assistente.agents.estoque_ia")

_PROMPT = """Você é um analista de estoque. Avalie se o produto abaixo corre risco de \
faltar nos próximos {horizonte} dias e responda SOMENTE com JSON.

Produto: {nome} (categoria: {categoria}, preço unitário: R$ {preco})
Estoque total: {estoque_total} unidade(s). Por centro de distribuição: {por_centro}
Baixa nos últimos {janela} dias: {unidades} unidade(s) (média {taxa:.2f}/dia).
Baixa diária, do dia mais antigo ao mais recente: {diario}
Referência determinística: {referencia}

Considere a tendência (baixa recente acelerando ou desacelerando), picos isolados \
e a distribuição entre centros. Não invente dados.

Formato exato:
{{"risco": "baixo"|"medio"|"alto", "dias_ate_falta": número ou null, \
"reposicao_sugerida": inteiro >= 0, "alertar": true|false, \
"justificativa": "uma ou duas frases em português"}}"""

_RISCOS = {"baixo", "medio", "alto"}


def montar_prompt(f: FatosEstoque) -> str:
    cobertura = f.cobertura
    referencia = (
        "sem baixa na janela"
        if cobertura is None
        else f"cobertura de {float(cobertura):.1f} dias no ritmo médio"
    )
    return _PROMPT.format(
        horizonte=f.horizonte_dias,
        nome=f.nome,
        categoria=f.categoria,
        preco=f.preco,
        estoque_total=f.estoque_total,
        por_centro=json.dumps(f.estoque_por_centro, ensure_ascii=False),
        janela=f.janela_dias,
        unidades=f.unidades_janela,
        taxa=float(f.taxa_diaria),
        diario=json.dumps(f.consumo_diario),
        referencia=referencia,
    )


def interpretar_resposta(texto: str) -> dict[str, Any] | None:
    try:
        dados = json.loads(strip_code_fence(texto))
    except json.JSONDecodeError, TypeError, ValueError:
        return None
    if not isinstance(dados, dict) or dados.get("risco") not in _RISCOS:
        return None
    if not isinstance(dados.get("alertar"), bool):
        return None
    return dados


async def decidir_com_ia(f: FatosEstoque, client: Any, llm: str) -> Decisao | None:
    if client is None:
        return None
    try:
        resposta = await client.generate(montar_prompt(f))
    except Exception:  # noqa: BLE001 - IA fora do ar => regra determinística
        logger.exception("Falha ao chamar o LLM do agente de estoque")
        return None

    try:
        await registrar_uso_ia(
            origem="admin",
            ambiente="externo" if llm == "externo" else "interno",
            modelo=getattr(resposta, "model_name", None) or "desconhecido",
            operacao="agente_estoque_ia",
            tokens_entrada=getattr(resposta, "prompt_tokens", None),
            tokens_saida=getattr(resposta, "completion_tokens", None),
            custo_usd=getattr(resposta, "estimated_cost_usd", None),
            referencia_id=str(f.produto_id),
            commit=False,
        )
    except Exception:  # noqa: BLE001 - telemetria nunca derruba o agente
        logger.warning("Falha ao registrar uso de IA do agente de estoque", exc_info=True)

    dados = interpretar_resposta(getattr(resposta, "text", "") or "")
    if dados is None:
        return None

    risco = dados["risco"]
    modelo = getattr(resposta, "model_name", None)
    meta = {
        "produto_id": f.produto_id,
        "metodo": "ia",
        "modelo": modelo,
        "risco": risco,
        "dias_ate_falta": dados.get("dias_ate_falta"),
        "reposicao_sugerida": dados.get("reposicao_sugerida"),
        "estoque_atual": f.estoque_total,
        "taxa_diaria": float(round(f.taxa_diaria, 3)),
        "horizonte_dias": f.horizonte_dias,
    }
    if not dados["alertar"] or risco == "baixo":
        return Decisao(False, AGENTE_IA, "aviso", "", "", meta)

    dias = dados.get("dias_ate_falta")
    quando = f"~{round(float(dias))} dias" if isinstance(dias, (int, float)) else "em breve"
    reposicao = dados.get("reposicao_sugerida")
    sugestao = (
        f" Reposição sugerida: {int(reposicao)} unidade(s)."
        if isinstance(reposicao, (int, float)) and reposicao > 0
        else ""
    )
    justificativa = str(dados.get("justificativa") or "").strip()
    return Decisao(
        True,
        AGENTE_IA,
        "critico" if risco == "alto" else "aviso",
        f"Risco de falta ({risco}): {f.nome} ({quando})",
        f'Produto "{f.nome}" (id {f.produto_id}), estoque {f.estoque_total} unidade(s). '
        f"{justificativa}{sugestao}",
        meta,
    )
