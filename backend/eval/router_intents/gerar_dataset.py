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
from collections import Counter
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
        "quer comprar, pedir orçamento, saber preço, estoque ou tirar dúvida de "
        "compatibilidade já no meio de uma intenção de compra"
    ),
    "suporte": (
        "produto já adquirido com defeito, erro ou problema técnico; ou dúvida isolada de "
        "compatibilidade entre produtos, sem intenção de compra"
    ),
    "atendimento": (
        "pós-compra (nota fiscal, troca, devolução, cancelamento, reclamação, pedido já "
        "feito) ou dúvida genérica sobre a empresa (localização, horário de funcionamento, "
        "acesso ao site)"
    ),
    "agendamento": (
        "quer marcar uma visita para conhecer o produto, conhecer a empresa, fazer "
        "manutenção no ambiente do cliente, receber um vendedor no ambiente do cliente "
        "ou comprar em uma unidade da empresa (remarcar, cancelar ou confirmar só se já "
        "tem visita em seu nome); a mensagem não relata defeito, só pede a visita"
    ),
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

# Cada domínio só se mistura com um parceiro com quem a mistura acontece de
# verdade: vendas+suporte/atendimento não ocorre em mensagem real (quem tem
# defeito não está comprando), e forçar essa mistura gerava frases sem sentido.
PAR_AMBIGUO = {
    "vendas": (
        "agendamento",
        "quero comprar a catraca, dá pra marcar uma visita pra ver o local antes?",
    ),
    "suporte": (
        "agendamento",
        "o leitor facial está com defeito, dá pra marcar um técnico aí?",
    ),
    "atendimento": (
        "suporte",
        "comprei a catraca e veio com defeito, quero a troca",
    ),
    "agendamento": (
        "suporte",
        "preciso marcar uma visita, o relógio de ponto está com problema de novo",
    ),
}

_PROMPT_AMBIGUA = """Você monta a parte difícil do conjunto de teste do roteador \
de intenção de um assistente de controle de acesso e segurança eletrônica.

Produtos do catálogo:
{produtos}

Escreva {n} mensagens de cliente que **misturem dois assuntos de propósito**: \
o domínio **{dominio}** ({descricao}) e o domínio **{outro}** ({descricao_outro}). \
O domínio **{dominio}** deve ser a leitura mais defensável, mas a mensagem tem \
de tocar nos dois.

Regras:
- A mensagem tem de **fazer sentido como situação real de um cliente**, escrita \
por uma pessoa só, com um único objetivo. Se os dois assuntos não puderem \
acontecer juntos na vida real, não force: escolha outra situação.
- Cada mensagem deve conter ao menos uma palavra de cada um destes dois grupos:
{grupos}
- **Curta**: de 8 a 20 palavras, uma ou duas frases no máximo, no tom de um \
WhatsApp. Nada de texto longo nem de lista de pedidos.
- Português correto e coerente: releia cada frase e descarte a que tiver trecho \
sem sentido ou palavra solta. **Sem erro de digitação proposital.**
- Cite o produto pelo nome em, no máximo, metade das mensagens; nas outras, \
diga só "o leitor", "a catraca", "o relógio".
- Cada mensagem pede **uma única coisa principal** e menciona o outro assunto \
como contexto, nunca como segundo pedido independente.
- Não misture um terceiro domínio. Não repita a estrutura das mensagens \
anteriores: varie o começo e o jeito de pedir.

Exemplo do tipo de mistura (não copie): "{exemplo}".

Responda só com um array JSON de strings:
["mensagem 1", "mensagem 2"]"""

_PROMPT_FORA_ESCOPO = """Você monta a parte de controle do conjunto de teste do \
roteador de intenção de um assistente de uma empresa de controle de acesso.

Escreva {n} mensagens que **não** pertencem a nenhum dos quatro domínios de \
atendimento (vendas, suporte técnico, atendimento ao usuário, agendamento de \
visita).

Misture estes tipos, em proporções parecidas:
- saudação ou agradecimento solto ("bom dia", "obrigado", "valeu");
- pergunta institucional que não seja dúvida genérica sobre a empresa ("tem \
vaga de emprego?", "vocês patrocinam eventos?") — localização, horário de \
funcionamento e acesso ao site são atendimento, não fora de escopo;
- assunto completamente alheio ("qual o resultado do jogo?", "me conta uma \
piada");
- conversa fiada sobre tecnologia em geral, sem pedir nada da empresa.

Responda só com um array JSON de strings:
["mensagem 1", "mensagem 2"]"""


# Ambíguas multi-rótulo (2026-10-20): com rótulo único, suporte+agendamento
# e atendimento+suporte eram arbitrários (mesmo molde, rótulos opostos). Agora
# cada par é fixo e o caso aceita os dois domínios em `intencoes_aceitas`.
PARES_AMBIGUOS = (
    (
        "vendas",
        "agendamento",
        "quero comprar a catraca, dá pra marcar uma visita pra ver o local antes?",
    ),
    (
        "suporte",
        "agendamento",
        "o leitor facial está com defeito, dá pra marcar um técnico aí?",
    ),
    (
        "atendimento",
        "suporte",
        "comprei a catraca e veio com defeito, quero a troca",
    ),
    # Pares com vendas, para o domínio não ficar só em um par (2026-10-20):
    # dúvida técnica antes de comprar e recompra a partir de pedido anterior.
    (
        "vendas",
        "suporte",
        "quero comprar o leitor, mas funciona com o sistema que já uso? preciso de ajuda técnica",
    ),
    (
        "vendas",
        "atendimento",
        "quero comprar a catraca, vocês ficam onde? dá pra ir aí ver pessoalmente?",
    ),
)

_PROMPT_AMBIGUA_PAR = """Você monta a parte difícil do conjunto de teste do roteador \
de intenção de um assistente de controle de acesso e segurança eletrônica.

Produtos do catálogo:
{produtos}

Escreva {n} mensagens de cliente que **caibam legitimamente em dois domínios**: \
**{dominio}** ({descricao}) e **{outro}** ({descricao_outro}). Um atendente \
humano aceitaria encaminhar para qualquer um dos dois; as duas leituras são \
igualmente defensáveis.

Regras:
- A mensagem tem de **fazer sentido como situação real de um cliente**, escrita \
por uma pessoa só, com um único objetivo.
- Cada mensagem deve conter ao menos uma palavra de cada um destes dois grupos:
{grupos}
- **Curta**: de 8 a 20 palavras, uma ou duas frases, tom de WhatsApp.
- Português correto e coerente, **sem erro de digitação proposital**.
- Cite o produto pelo nome em, no máximo, metade das mensagens; nas outras, \
diga só "o leitor", "a catraca", "o relógio".
- **Uma frase complementa a outra**: as duas partes têm de formar um único \
pedido coerente, nunca duas perguntas soltas sem relação.
- Atendimento é pós-compra **ou** dúvida genérica sobre a empresa (localização, \
horário de funcionamento, acesso ao site). Pós-compra (pedido, troca, nota \
fiscal, atraso) só se a pessoa já comprou antes: diga "meu pedido anterior", \
"o que comprei". Quem ainda quer comprar não tem pedido para atrasar ou trocar.
- Visita só por um destes motivos: conhecer o produto, conhecer a empresa, \
manutenção no ambiente do cliente, vendedor no ambiente do cliente ou compra \
em uma unidade da empresa. Remarcar/cancelar/confirmar só se o cliente já tem visita \
agendada em seu nome e a mensagem deixa isso claro.
- Não misture um terceiro domínio. Varie o começo e o jeito de pedir.

Exemplo do tipo de mistura (não copie): "{exemplo}".

Responda só com um array JSON de strings:
["mensagem 1", "mensagem 2"]"""


class _ClienteSemRaciocinio(httpx.AsyncClient):
    """Desliga o raciocínio oculto (Qwen3.5 etc.) no Ollama: com o prompt longo
    ele gasta a saída pensando e devolve `content` vazio."""

    async def post(self, url, **kwargs):  # type: ignore[override]
        if isinstance(kwargs.get("json"), dict):
            kwargs["json"] = {**kwargs["json"], "reasoning_effort": "none"}
        return await super().post(url, **kwargs)


def _proibidas(dominio: str) -> str:
    return ", ".join(f'"{k}"' for k in _DOMAIN_KEYWORDS[dominio])


def _grupos_de_keywords(dominios: tuple[str, ...] | None = None) -> str:
    return "\n".join(
        f"- {dominio}: " + ", ".join(f'"{k}"' for k in keywords)
        for dominio, keywords in _DOMAIN_KEYWORDS.items()
        if dominios is None or dominio in dominios
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


def faltantes(casos: list[dict]) -> list[tuple[str, bool, int]]:
    """(domínio, ambígua?, quantas faltam) para fechar a meta por categoria.

    Itens descartados na revisão não contam: o `--completar` repõe o que a
    revisão tirou, na mesma categoria, em vez de só fechar o total.
    """
    vivos = [c for c in casos if (c.get("revisao") or {}).get("status") != "descartado"]
    contagem = Counter((c["intencao_esperada"], bool(c["ambiguo"])) for c in vivos)
    faltas = [
        (dominio, ambiguo, meta - contagem[(dominio, ambiguo)])
        for dominio in DOMINIOS
        for ambiguo, meta in _METAS_POR_DOMINIO
        if meta > contagem[(dominio, ambiguo)]
    ]
    tem_fora = sum(n for (dominio, _), n in contagem.items() if dominio == "fora_escopo")
    if FORA_ESCOPO > tem_fora:
        faltas.append(("fora_escopo", False, FORA_ESCOPO - tem_fora))
    return faltas


def produtos_do_corpus(limite: int = 12) -> list[str]:
    auditoria = json.loads(AUDITORIA.read_text(encoding="utf-8"))
    pastas = sorted({i["arquivo"].split("/")[0] for i in auditoria["itens_pdfs"]})
    return [p for p in pastas if p != "Suporte"][:limite]


def montar_casos(
    mensagens: list[str],
    dominio: str,
    ambiguo: bool,
    proximo_id: int,
    vistos: set[str],
    aceitas: list[str] | None = None,
) -> list[dict]:
    casos = []
    for mensagem in mensagens:
        texto = (mensagem or "").strip()
        chave = texto.lower()
        if not texto or chave in vistos:
            continue
        vistos.add(chave)
        chega, motivo = classificar_caminho(texto)
        caso = {
            "id": proximo_id + len(casos),
            "mensagem": texto,
            "intencao_esperada": dominio,
            "ambiguo": ambiguo,
            "chega_ao_llm": chega,
            "motivo_caminho": motivo,
            "revisao": {"status": "pendente", "em": None},
        }
        if aceitas:
            caso["intencoes_aceitas"] = aceitas
        casos.append(caso)
    return casos


async def _chamar_com_retry(client, prompt: str):
    for tentativa in range(MAX_TENTATIVAS):
        try:
            return await client.generate(prompt)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429 or tentativa == MAX_TENTATIVAS - 1:
                raise
            espera = ESPERA_BASE_S * (2**tentativa)
            print(f"    429 ({tentativa + 1}/{MAX_TENTATIVAS}), aguardando {espera:.0f}s...")
            await asyncio.sleep(espera)


def _lista_de_textos(dados) -> list[str]:
    if isinstance(dados, dict):
        dados = next((v for v in dados.values() if isinstance(v, list)), dados)
    return [d for d in dados if isinstance(d, str)] if isinstance(dados, list) else []


async def _gerar(client, prompt: str) -> list[str]:
    resposta = await _chamar_com_retry(client, prompt)
    await asyncio.sleep(PAUSA_ENTRE_CHAMADAS_S)
    try:
        dados = json.loads(strip_code_fence(resposta.text))
    except (ValueError, TypeError) as exc:
        print(f"    JSON inválido do modelo: {exc}")
        return []
    return _lista_de_textos(dados)


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


_METAS_POR_DOMINIO = (
    (True, POR_DOMINIO_DIFICIL // 2),
    (False, POR_DOMINIO_DIFICIL // 2 + POR_DOMINIO_LIVRE),
)


class _Gerador:
    """Estado de uma rodada: cliente, casos acumulados e dedup (`vistos`)."""

    def __init__(self, args, client, modelo: str) -> None:
        self.args = args
        self.client = client
        self.modelo = modelo
        self.saida = Path(args.saida)
        self.produtos = "\n".join(f"- {p}" for p in produtos_do_corpus())
        self.casos: list[dict] = []
        self.vistos: set[str] = set()

    def carregar_existentes(self) -> None:
        for arquivo in self.args.evitar:
            self.vistos |= {
                c["mensagem"].lower()
                for c in json.loads(Path(arquivo).read_text(encoding="utf-8"))["casos"]
            }
        if self.args.completar and self.saida.exists():
            self.casos = json.loads(self.saida.read_text(encoding="utf-8"))["casos"]
            self.vistos = {c["mensagem"].lower() for c in self.casos}

    def salvar(self) -> None:
        salvar(self.saida, self.casos, self.modelo)

    async def _lotes(
        self,
        prefixo: str,
        quantos: int,
        prompt_de,
        dominio: str,
        ambiguo: bool,
        aceitas: list[str] | None = None,
        mostrar_chegam: bool = True,
        dry_run_consome: bool = True,
    ) -> None:
        """Pede `quantos` mensagens em lotes de `LOTE`, salvando a cada lote."""
        restante = quantos
        while restante > 0:
            n = min(LOTE, restante)
            print(f"{prefixo} pedindo {n}...")
            if self.args.dry_run:
                if not dry_run_consome:
                    break
                restante -= n
                continue
            mensagens = await _gerar(self.client, prompt_de(n))
            proximo = max((c["id"] for c in self.casos), default=0) + 1
            novos = montar_casos(mensagens[:n], dominio, ambiguo, proximo, self.vistos, aceitas)
            self.casos.extend(novos)
            if mostrar_chegam:
                chegam = sum(1 for c in novos if c["chega_ao_llm"])
                print(f"    {len(novos)} caso(s), {chegam} chega(m) ao LLM")
            else:
                print(f"    {len(novos)} caso(s)")
            self.salvar()
            if not novos:
                break
            restante -= len(novos)

    def _extra(self, dominio: str) -> dict:
        outro, exemplo = PAR_AMBIGUO.get(dominio, (dominio, ""))
        return {
            "dominio": dominio,
            "descricao": DESCRICAO_DOMINIO.get(dominio, ""),
            "proibidas": _proibidas(dominio) if dominio in _DOMAIN_KEYWORDS else "",
            "outro": outro,
            "descricao_outro": DESCRICAO_DOMINIO.get(outro, ""),
            "exemplo": exemplo,
            "grupos": _grupos_de_keywords((dominio, outro)),
        }

    async def pedir(self, prompt: str, dominio: str, ambiguo: bool, quantos: int, rotulo: str):
        await self._lotes(
            f"[{rotulo}] {dominio}:",
            quantos,
            lambda n: prompt.format(n=n, produtos=self.produtos, **self._extra(dominio)),
            dominio,
            ambiguo,
        )

    async def pedir_fora_escopo(self, quantos: int) -> None:
        if self.args.dry_run:
            return
        await self._lotes(
            "[fora_escopo]",
            quantos,
            lambda n: _PROMPT_FORA_ESCOPO.format(n=n),
            "fora_escopo",
            False,
            mostrar_chegam=False,
        )

    async def pedir_par(self, dominio: str, outro: str, exemplo: str) -> None:
        def prompt_de(n: int) -> str:
            return _PROMPT_AMBIGUA_PAR.format(
                n=n,
                produtos=self.produtos,
                dominio=dominio,
                descricao=DESCRICAO_DOMINIO[dominio],
                outro=outro,
                descricao_outro=DESCRICAO_DOMINIO[outro],
                grupos=_grupos_de_keywords((dominio, outro)),
                exemplo=exemplo,
            )

        await self._lotes(
            f"[par] {dominio}+{outro}:",
            self.args.ambiguas_por_par,
            prompt_de,
            dominio,
            True,
            [dominio, outro],
            dry_run_consome=False,
        )

    async def modo_extra_nao_ambiguas(self) -> int:
        # "DOM:N" = difíceis (sem palavra da tabela, chegam ao LLM); "DOM:N:livre" = livres.
        for item in self.args.extra_nao_ambiguas.split(","):
            dominio, quantos, *modo = item.split(":")
            if dominio == "fora_escopo":
                await self.pedir_fora_escopo(int(quantos))
                continue
            livre = modo == ["livre"]
            await self.pedir(
                _PROMPT_LIVRE if livre else _PROMPT_DOMINIO,
                dominio,
                False,
                int(quantos),
                "extra-livre" if livre else "extra-sem-keyword",
            )
        self.salvar()
        print(f"\n{self.saida}: {len(self.casos)} não ambígua(s) extras.")
        return 0

    async def modo_ambiguas_por_par(self) -> int:
        # Só ambíguas multi-rótulo, em arquivo à parte (a mescla no
        # dataset.json é decisão de quem revisa).
        filtro = self.args.pares.split(",") if self.args.pares else None
        for dominio, outro, exemplo in PARES_AMBIGUOS:
            if filtro is not None and f"{dominio}+{outro}" not in filtro:
                continue
            await self.pedir_par(dominio, outro, exemplo)
        self.salvar()
        print(f"\n{self.saida}: {len(self.casos)} ambígua(s) multi-rótulo.")
        return 0

    async def modo_piloto(self) -> int:
        # Só ambíguas, para medir a qualidade do gerador antes da rodada toda.
        for dominio in DOMINIOS:
            await self.pedir(_PROMPT_AMBIGUA, dominio, True, self.args.piloto, "piloto-ambígua")
        self.salvar()
        print(f"\n{self.saida}: {len(self.casos)} ambígua(s) de piloto.")
        return 0

    async def modo_completar(self) -> int:
        for dominio, ambiguo, faltam in faltantes(self.casos):
            if ambiguo:
                await self.pedir(_PROMPT_AMBIGUA, dominio, True, faltam, "completar-ambígua")
            elif dominio == "fora_escopo":
                await self.pedir_fora_escopo(faltam)
            else:
                await self.pedir(_PROMPT_LIVRE, dominio, False, faltam, "completar")
        self.salvar()
        print(f"\n{self.saida}: {len(self.casos)} mensagem(ns) após completar.")
        return 0

    async def modo_completo(self) -> int:
        for dominio in DOMINIOS:
            # Metade das difíceis por "sinônimo fora da tabela" e metade por
            # ambiguidade real: são os dois caminhos distintos até o LLM, e um
            # conjunto com só um dos dois mediria metade do problema.
            await self.pedir(
                _PROMPT_DOMINIO, dominio, False, POR_DOMINIO_DIFICIL // 2, "sem-keyword"
            )
            await self.pedir(_PROMPT_AMBIGUA, dominio, True, POR_DOMINIO_DIFICIL // 2, "ambígua")
            await self.pedir(_PROMPT_LIVRE, dominio, False, POR_DOMINIO_LIVRE, "livre")
        await self.pedir_fora_escopo(FORA_ESCOPO)

        if self.args.dry_run:
            print("\n(dry-run) nenhuma chamada feita.")
            return 0

        self.salvar()
        chegam = sum(1 for c in self.casos if c["chega_ao_llm"])
        pct = 100 * chegam / max(1, len(self.casos))
        print(
            f"\n{self.saida}: {len(self.casos)} mensagem(ns), {chegam} chega(m) ao LLM ({pct:.0f}%)"
        )
        if chegam < 200:
            print(f"ATENÇÃO: meta é >=200 chegando ao LLM; faltam {200 - chegam}. Rode de novo.")
        return 0

    async def rodar(self) -> int:
        args = self.args
        if args.extra_nao_ambiguas:
            return await self.modo_extra_nao_ambiguas()
        if args.ambiguas_por_par:
            return await self.modo_ambiguas_por_par()
        if args.piloto:
            return await self.modo_piloto()
        # Dedup descarta repetidas e o total pode fechar abaixo da meta: sem
        # `--completar` a rodada recomeça do zero, então o resto vem aqui.
        if args.completar and self.casos:
            return await self.modo_completar()
        return await self.modo_completo()


def _criar_cliente(args, modelo: str, settings) -> OpenRouterClient:
    # Ollama expõe /v1/chat/completions compatível com OpenAI: basta apontar
    # `--base-url http://localhost:11434/v1` (a chave é ignorada).
    return OpenRouterClient(
        base_url=args.base_url or settings.external_model_base_url,
        api_key="ollama" if args.base_url else settings.external_model_api_key,
        model=modelo,
        timeout_s=args.timeout_s or settings.external_llm_timeout_s,
        client=_ClienteSemRaciocinio() if args.base_url else None,
    )


async def executar(args) -> int:
    settings = get_settings()
    modelo = args.modelo or settings.external_model_name
    gerador = _Gerador(args, _criar_cliente(args, modelo, settings), modelo)
    print(f"Modelo do rascunho: {modelo}\n")
    gerador.carregar_existentes()
    return await gerador.rodar()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", default=str(SAIDA_PADRAO))
    parser.add_argument("--modelo", default=None)
    parser.add_argument("--base-url", default=None, help="ex.: http://localhost:11434/v1 (Ollama)")
    parser.add_argument("--timeout-s", type=float, default=None)
    parser.add_argument(
        "--piloto",
        type=int,
        default=0,
        metavar="N",
        help="gera só N ambíguas por domínio (use com --saida fora de dataset.json)",
    )
    parser.add_argument(
        "--ambiguas-por-par",
        type=int,
        default=0,
        metavar="N",
        help="gera só N ambíguas multi-rótulo (`intencoes_aceitas`) por par de domínios",
    )
    parser.add_argument("--pares", default="", help='filtra pares, ex.: "vendas+suporte"')
    parser.add_argument(
        "--extra-nao-ambiguas",
        default="",
        metavar="DOM:N,...",
        help='gera N não ambíguas por domínio, ex.: "agendamento:6,agendamento:3:livre"',
    )
    parser.add_argument(
        "--evitar", nargs="*", default=[], help="datasets cujas mensagens não podem repetir"
    )
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
