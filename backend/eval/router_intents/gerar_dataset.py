"""Gera o conjunto de 300 mensagens do roteador (R1/R3, Fase 10).

O requisito da Estratégia A não é só "300 mensagens": é **≥200 desenhadas
para chegar ao LLM**. Hoje só 22,5% chegam (9 de 40 medido), porque o atalho
por palavra-chave de `app.router.classifier` resolve o resto antes — e aí a
acurácia medida é a da tabela de keywords, não a do modelo que se quer
escolher. Num conjunto "representativo", o n efetivo de comparação entre
candidatos seria um terço do nominal.

Uma mensagem chega ao LLM quando **não** é cortesia pura e
`_match_domain_by_keywords` devolve `None`, o que acontece em dois casos:

- **zero domínios casados** — o cliente usou sinônimo fora da tabela
  ("quanto sai", "pifou", "trocar por outro");
- **dois ou mais domínios casados** — a ambiguidade real ("desconto" de
  vendas + "defeito" de suporte), que colapsa de propósito para o LLM.

Este gerador explora os dois: o prompt proíbe as palavras da tabela para o
domínio pedido (força o primeiro caso) e pede combinações cruzadas (força o
segundo). Depois **verifica cada mensagem com as funções reais do
classificador** — determinístico, sem chamar LLM — e grava em cada caso se
ela chega ao LLM e por quê.

# MVP: o rascunho é do LLM e todo item nasce `pendente`. A revisão humana
# prevista é por amostra (~140 itens): todas as ambíguas, onde o rótulo
# automático é discutível, mais uma amostra das demais
# (`docs/EVALUATION.md` Seção 0).

Uso (a partir de `backend/`, exige só `EXTERNAL_MODEL_API_KEY`):

    .venv/bin/python eval/router_intents/gerar_dataset.py --dry-run
    .venv/bin/python eval/router_intents/gerar_dataset.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR.parent.parent / "src"))

from app.config import get_settings  # noqa: E402
from app.router.classifier import (  # noqa: E402
    _DOMAIN_KEYWORDS,
    _is_cortesia,
    _match_domain_by_keywords,
    strip_code_fence,
)
from app.router.openrouter_client import OpenRouterClient  # noqa: E402

SAIDA_PADRAO = BASE_DIR / "dataset.json"
AUDITORIA = BASE_DIR.parent / "rag_ingestion" / "auditoria_corpus.json"

DOMINIOS = ("vendas", "suporte", "atendimento", "agendamento")
# 60 por domínio + 60 fora de escopo = 300. Em cada domínio, 40 desenhadas
# para chegar ao LLM e 20 livres (podem cair no atalho), para a "acurácia do
# sistema" refletir o mix real em vez de só o caminho difícil.
POR_DOMINIO_DIFICIL = 40
POR_DOMINIO_LIVRE = 20
FORA_ESCOPO = 60
LOTE = 20
PAUSA_ENTRE_CHAMADAS_S = 3.0
MAX_TENTATIVAS = 5
ESPERA_BASE_S = 8.0

DESCRICAO_DOMINIO = {
    "vendas": (
        "quer comprar, pedir orçamento, saber preço, estoque ou compatibilidade antes da compra"
    ),
    "suporte": "produto já adquirido com defeito, erro ou problema técnico",
    "atendimento": "nota fiscal, troca, devolução, cancelamento, reclamação ou pedido já feito",
    "agendamento": "quer marcar, remarcar ou confirmar uma visita técnica",
}

_PROMPT_DOMINIO = """Você monta o conjunto de teste do roteador de intenção de \
um assistente de uma empresa de controle de acesso e segurança eletrônica \
(catracas, leitores faciais, relógios de ponto, fechaduras).

Produtos do catálogo, para dar realismo às mensagens:
{produtos}

Escreva {n} mensagens de cliente do domínio **{dominio}** ({descricao}).

Regras:
- Linguagem de cliente real brasileiro: curta, informal, com erro de digitação \
ocasional, sem saudação enfeitada.
- **PROIBIDO usar estas palavras** (e variações delas): {proibidas}. Use \
sinônimo ou rodeio — "quanto sai", "quanto fica", "pifou", "parou do nada", \
"queria trocar por outro", "manda alguém aqui".
- Uma mensagem por item, sem numerar, sem explicar.

Responda só com um array JSON de strings:
["mensagem 1", "mensagem 2"]"""

_PROMPT_LIVRE = """Você monta o conjunto de teste do roteador de intenção de um \
assistente de controle de acesso e segurança eletrônica.

Produtos do catálogo:
{produtos}

Escreva {n} mensagens de cliente do domínio **{dominio}** ({descricao}), do \
jeito que o cliente escreveria naturalmente — sem evitar nenhuma palavra.

Linguagem real: curta, informal, erro de digitação ocasional.

Responda só com um array JSON de strings:
["mensagem 1", "mensagem 2"]"""

_PROMPT_AMBIGUA = """Você monta a parte difícil do conjunto de teste do roteador \
de intenção de um assistente de controle de acesso e segurança eletrônica.

Produtos do catálogo:
{produtos}

Escreva {n} mensagens de cliente que **misturem dois assuntos de propósito**, \
de modo que fique genuinamente discutível em qual domínio classificar — mas em \
que o domínio **{dominio}** ({descricao}) seja a leitura mais defensável.

Cada mensagem deve conter ao menos uma palavra de dois destes grupos:
{grupos}

Exemplo do tipo de mistura (não copie): "comprei a catraca com desconto mês \
passado e ela já está com defeito, quero trocar" — tem vendas, suporte e \
atendimento ao mesmo tempo.

Responda só com um array JSON de strings:
["mensagem 1", "mensagem 2"]"""

_PROMPT_FORA_ESCOPO = """Você monta a parte de controle do conjunto de teste do \
roteador de intenção de um assistente de uma empresa de controle de acesso.

Escreva {n} mensagens que **não** pertencem a nenhum dos quatro domínios de \
atendimento (vendas, suporte técnico, atendimento ao usuário, agendamento de \
visita).

Misture estes tipos, em proporções parecidas:
- saudação ou agradecimento solto ("bom dia", "obrigado", "valeu");
- pergunta institucional ("vocês ficam onde?", "que horas abre?", "tem vaga de \
emprego?");
- assunto completamente alheio ("qual o resultado do jogo?", "me conta uma \
piada");
- conversa fiada sobre tecnologia em geral, sem pedir nada da empresa.

Responda só com um array JSON de strings:
["mensagem 1", "mensagem 2"]"""


def _proibidas(dominio: str) -> str:
    return ", ".join(f'"{k}"' for k in _DOMAIN_KEYWORDS[dominio])


def _grupos_de_keywords() -> str:
    return "\n".join(
        f"- {dominio}: " + ", ".join(f'"{k}"' for k in keywords)
        for dominio, keywords in _DOMAIN_KEYWORDS.items()
    )


def classificar_caminho(mensagem: str) -> tuple[bool, str]:
    """(chega_ao_llm, motivo) pelas funções reais do classificador.

    É a parte que torna o conjunto verificável sem gastar uma chamada de LLM:
    o mesmo código que roda em produção decide se a mensagem seria resolvida
    pelo atalho.
    """
    if _is_cortesia(mensagem):
        return False, "cortesia"
    atalho = _match_domain_by_keywords(mensagem)
    if atalho is not None:
        return False, f"atalho_{atalho}"
    normalizado = mensagem.lower()
    casados = sum(
        1
        for keywords in _DOMAIN_KEYWORDS.values()
        if any(k.lower() in normalizado for k in keywords)
    )
    return True, "duas_ou_mais_keywords" if casados >= 2 else "zero_keywords"


def produtos_do_corpus(limite: int = 12) -> list[str]:
    auditoria = json.loads(AUDITORIA.read_text(encoding="utf-8"))
    pastas = sorted({i["arquivo"].split("/")[0] for i in auditoria["itens_pdfs"]})
    return [p for p in pastas if p != "Suporte"][:limite]


def montar_casos(
    mensagens: list[str], dominio: str, ambiguo: bool, proximo_id: int, vistos: set[str]
) -> list[dict]:
    casos = []
    for mensagem in mensagens:
        texto = (mensagem or "").strip()
        chave = texto.lower()
        if not texto or chave in vistos:
            continue
        vistos.add(chave)
        chega, motivo = classificar_caminho(texto)
        casos.append(
            {
                "id": proximo_id + len(casos),
                "mensagem": texto,
                "intencao_esperada": dominio,
                "ambiguo": ambiguo,
                "chega_ao_llm": chega,
                "motivo_caminho": motivo,
                "revisao": {"status": "pendente", "em": None},
            }
        )
    return casos


async def _gerar(client, prompt: str) -> list[str]:
    for tentativa in range(MAX_TENTATIVAS):
        try:
            resposta = await client.generate(prompt)
            break
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429 or tentativa == MAX_TENTATIVAS - 1:
                raise
            espera = ESPERA_BASE_S * (2**tentativa)
            print(f"    429 ({tentativa + 1}/{MAX_TENTATIVAS}), aguardando {espera:.0f}s...")
            await asyncio.sleep(espera)
    await asyncio.sleep(PAUSA_ENTRE_CHAMADAS_S)
    try:
        dados = json.loads(strip_code_fence(resposta.text))
    except (ValueError, TypeError) as exc:
        print(f"    JSON inválido do modelo: {exc}")
        return []
    if isinstance(dados, dict):
        for valor in dados.values():
            if isinstance(valor, list):
                dados = valor
                break
    return [d for d in dados if isinstance(d, str)] if isinstance(dados, list) else []


def envelope(casos: list[dict], modelo: str) -> dict:
    chegam = [c for c in casos if c["chega_ao_llm"]]
    return {
        "descricao": (
            "Conjunto de 300 mensagens do roteador (Estratégia A, Fase 10). "
            "Rótulo = domínio esperado; `chega_ao_llm` diz se a mensagem passa "
            "do atalho por palavra-chave e chega ao classificador LLM."
        ),
        "observacoes": (
            f"Rascunho gerado por {modelo}, todo item `revisao.status = pendente`. "
            "`chega_ao_llm` e `motivo_caminho` são calculados pelas funções reais "
            "de `app.router.classifier` (`_is_cortesia`, `_match_domain_by_keywords`), "
            "não pelo modelo. Reportar duas taxas na avaliação: acurácia do sistema "
            "(todos os casos) e acurácia do modelo no subconjunto que chega a ele."
        ),
        "total": len(casos),
        "chegam_ao_llm": len(chegam),
        "casos": casos,
    }


def salvar(saida: Path, casos: list[dict], modelo: str) -> None:
    saida.write_text(
        json.dumps(envelope(casos, modelo), ensure_ascii=False, indent=2), encoding="utf-8"
    )


async def executar(args) -> int:
    saida = Path(args.saida)
    produtos = "\n".join(f"- {p}" for p in produtos_do_corpus())

    settings = get_settings()
    modelo = args.modelo or settings.external_model_name
    client = OpenRouterClient(
        base_url=settings.external_model_base_url,
        api_key=settings.external_model_api_key,
        model=modelo,
        timeout_s=settings.external_llm_timeout_s,
    )
    print(f"Modelo do rascunho: {modelo}\n")

    casos: list[dict] = []
    vistos: set[str] = set()
    if args.completar and saida.exists():
        casos = json.loads(saida.read_text(encoding="utf-8"))["casos"]
        vistos = {c["mensagem"].lower() for c in casos}

    async def pedir(prompt: str, dominio: str, ambiguo: bool, quantos: int, rotulo: str) -> None:
        restante = quantos
        while restante > 0:
            n = min(LOTE, restante)
            print(f"[{rotulo}] {dominio}: pedindo {n}...")
            if args.dry_run:
                restante -= n
                continue
            mensagens = await _gerar(
                client, prompt.format(n=n, produtos=produtos, **_extra(dominio))
            )
            proximo = max((c["id"] for c in casos), default=0) + 1
            novos = montar_casos(mensagens[:n], dominio, ambiguo, proximo, vistos)
            casos.extend(novos)
            chegam = sum(1 for c in novos if c["chega_ao_llm"])
            print(f"    {len(novos)} caso(s), {chegam} chega(m) ao LLM")
            salvar(saida, casos, modelo)
            if not novos:
                break
            restante -= len(novos)

    def _extra(dominio: str) -> dict:
        return {
            "dominio": dominio,
            "descricao": DESCRICAO_DOMINIO.get(dominio, ""),
            "proibidas": _proibidas(dominio) if dominio in _DOMAIN_KEYWORDS else "",
            "grupos": _grupos_de_keywords(),
        }

    # Dedup descarta repetidas e o total pode fechar abaixo da meta: sem
    # `--completar` a rodada recomeça do zero, então o resto vem aqui.
    meta_total = len(DOMINIOS) * (POR_DOMINIO_DIFICIL + POR_DOMINIO_LIVRE) + FORA_ESCOPO
    if args.completar and casos:
        faltam = meta_total - len(casos)
        if faltam > 0:
            await pedir(_PROMPT_LIVRE, DOMINIOS[0], False, faltam, "completar")
        salvar(saida, casos, modelo)
        print(f"\n{saida}: {len(casos)} mensagem(ns) após completar.")
        return 0

    for dominio in DOMINIOS:
        # Metade das difíceis por "sinônimo fora da tabela" e metade por
        # ambiguidade real: são os dois caminhos distintos até o LLM, e um
        # conjunto com só um dos dois mediria metade do problema.
        await pedir(_PROMPT_DOMINIO, dominio, False, POR_DOMINIO_DIFICIL // 2, "sem-keyword")
        await pedir(_PROMPT_AMBIGUA, dominio, True, POR_DOMINIO_DIFICIL // 2, "ambígua")
        await pedir(_PROMPT_LIVRE, dominio, False, POR_DOMINIO_LIVRE, "livre")

    restante = FORA_ESCOPO
    while restante > 0 and not args.dry_run:
        n = min(LOTE, restante)
        print(f"[fora_escopo] pedindo {n}...")
        mensagens = await _gerar(client, _PROMPT_FORA_ESCOPO.format(n=n))
        proximo = max((c["id"] for c in casos), default=0) + 1
        novos = montar_casos(mensagens[:n], "fora_escopo", False, proximo, vistos)
        casos.extend(novos)
        print(f"    {len(novos)} caso(s)")
        salvar(saida, casos, modelo)
        if not novos:
            break
        restante -= len(novos)

    if args.dry_run:
        print("\n(dry-run) nenhuma chamada feita.")
        return 0

    salvar(saida, casos, modelo)
    chegam = sum(1 for c in casos if c["chega_ao_llm"])
    pct = 100 * chegam / max(1, len(casos))
    print(f"\n{saida}: {len(casos)} mensagem(ns), {chegam} chega(m) ao LLM ({pct:.0f}%)")
    if chegam < 200:
        print(f"ATENÇÃO: meta é >=200 chegando ao LLM; faltam {200 - chegam}. Rode de novo.")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", default=str(SAIDA_PADRAO))
    parser.add_argument("--modelo", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--completar",
        action="store_true",
        help="parte do dataset existente e pede só o que falta para chegar a 300",
    )
    args = parser.parse_args(argv[1:])
    return asyncio.run(executar(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
