"""Gera o rascunho das 180 perguntas de RAG documentos (R4, Fase 10,
Estratégia A — `docs/EVALUATION.md` Seção 0).

São 160 perguntas respondíveis, distribuídas pelos PDFs úteis do corpus
`docs/Manuais_fornecedor/ControlId/`, e 20 **sem resposta no corpus**, para
medir alucinação. Cada item respondível carrega o `trecho_origem`, que é o
que troca ~1,5 min de caça no PDF por ~10 s de leitura lado a lado na tela
`/admin/datasets` — o orçamento de ~2 h de revisão deste conjunto depende
disso.

Duas decisões que valem registro:

1. **O texto vem de `app.rag.pdf_extract`, o mesmo extrator da ingestão.**
   Um extrator diferente aqui produziria perguntas que dependem de texto que
   o RAG nunca indexou, e o sistema erraria por um motivo que não é o que se
   quer medir.
2. **Os documentos elegíveis saem de `auditoria_corpus.json` (Etapa 0)**,
   filtrando `classificacao == "util"`. Isso já exclui os 11 PDFs
   degenerados e, com eles, os 8 de imagem pura que ficaram com 0 chunks na
   ingestão — perguntar sobre documento invisível à busca contaminaria a
   medida de alucinação, que precisa vir só das 20 deliberadas.

O modelo é o `EXTERNAL_MODEL_NAME` do `.env` (tier `:free` por decisão do
dono em 2026-10-17): grátis, mas com rate limit apertado, daí a pausa entre
chamadas, o backoff em 429 e a retomada por documento.

# MVP: o rascunho é do LLM e **todo item nasce `pendente`** — o gabarito só
# vale depois da revisão humana na tela `/admin/datasets`. As 20 sem
# resposta são as que mais precisam de conferência: o modelo pode propor um
# tema que, na verdade, está no corpus.

Uso (a partir de `backend/`, exige só `EXTERNAL_MODEL_API_KEY`):

    .venv/bin/python eval/rag_quality/gerar_dataset.py
    .venv/bin/python eval/rag_quality/gerar_dataset.py --limite-docs 3 --total 6
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR.parent.parent / "src"))

from app.config import get_settings  # noqa: E402
from app.rag.pdf_extract import extract_text_from_pdf  # noqa: E402
from app.router.classifier import strip_code_fence  # noqa: E402
from app.router.openrouter_client import OpenRouterClient  # noqa: E402

AUDITORIA_PADRAO = BASE_DIR.parent / "rag_ingestion" / "auditoria_corpus.json"
SAIDA_PADRAO = BASE_DIR / "dataset.json"
TOTAL_RESPONDIVEIS = 160
TOTAL_SEM_RESPOSTA = 20
POR_DOCUMENTO = 2
# Prompt grande não melhora a pergunta e aumenta a chance de 429 no tier
# `:free`; 12k chars cobrem o datasheet típico deste corpus inteiro.
MAX_CHARS_PROMPT = 12_000
MAX_CHARS_TRECHO = 400
PAUSA_ENTRE_CHAMADAS_S = 3.0
MAX_TENTATIVAS = 5
ESPERA_BASE_S = 8.0

_PROMPT_PERGUNTAS = """Você monta o conjunto de teste de um assistente com RAG \
sobre manuais e datasheets de controle de acesso e segurança eletrônica.

Documento: {documento}

Texto do documento, exatamente como o sistema o indexa:
---
{texto}
---

Gere {n} pergunta(s) que um cliente real faria e que sejam respondíveis SÓ \
com o texto acima.

Regras:
- Nada de inventar: se a informação não está no texto, não pergunte.
- "resposta_esperada" é curta e factual, com o número/unidade quando houver.
- "trecho_origem" é a cópia LITERAL do pedaço do texto acima que contém a \
resposta (no máximo {max_trecho} caracteres). Não reescreva nem resuma.
- "dificuldade": "facil" quando a resposta está numa linha só, "media" \
quando exige juntar duas informações do documento, "dificil" quando exige \
ler tabela ou interpretar.
- Não cite o nome do arquivo na pergunta.

Responda só com um array JSON, sem comentários:
[{{"pergunta": "...", "resposta_esperada": "...", "trecho_origem": "...", \
"dificuldade": "facil"}}]"""

_PROMPT_SEM_RESPOSTA = """Você monta a parte de controle de um conjunto de \
teste: perguntas que o assistente NÃO tem como responder, para medir se ele \
admite não saber em vez de alucinar.

O acervo dele cobre exatamente estas linhas de produto, e nada mais:
{produtos}

Gere {n} perguntas plausíveis de um cliente real do ramo de controle de \
acesso e segurança eletrônica cuja resposta NÃO está nesse acervo.

Regras:
- Não mencione nenhum dos produtos da lista acima.
- A pergunta tem de ser do mesmo ramo (nada de "qual a capital da França").
- Evite pergunta sobre preço, prazo ou estoque: isso o sistema responde por \
outro caminho, que não é o RAG de documentos.
- "motivo_ausencia" explica em uma linha por que o acervo não cobre aquilo.

Responda só com um array JSON, sem comentários:
[{{"pergunta": "...", "motivo_ausencia": "...", "dificuldade": "media"}}]"""

RESPOSTA_SEM_RESPOSTA = (
    "Não consta no corpus. A resposta correta é o assistente dizer que não "
    "tem essa informação, sem inventar dado nem citar fonte."
)


def documentos_elegiveis(auditoria: dict) -> list[dict]:
    """PDFs `util` da auditoria, do maior para o menor em caracteres.

    A ordem importa porque a cota total (`--total`) corta a lista: documento
    com mais texto rende pergunta melhor, então é o primeiro a entrar.
    """
    uteis = [i for i in auditoria.get("itens_pdfs", []) if i.get("classificacao") == "util"]
    return sorted(uteis, key=lambda i: i.get("chars", 0), reverse=True)


def cota_por_documento(docs: list[dict], total: int, por_documento: int) -> list[tuple[dict, int]]:
    """Distribui `total` perguntas pelos documentos, no máximo
    `por_documento` em cada, parando quando a cota acaba."""
    plano: list[tuple[dict, int]] = []
    restante = total
    for doc in docs:
        if restante <= 0:
            break
        n = min(por_documento, restante)
        plano.append((doc, n))
        restante -= n
    return plano


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip().lower()


def trecho_confere(trecho: str, texto: str) -> bool:
    """O `trecho_origem` existe no documento?

    Sem esta checagem o campo perde a função: um trecho parafraseado pelo
    modelo faz o revisor comparar a pergunta com um texto que não é o do
    PDF, que é exatamente o erro que o campo existe para evitar.
    """
    if not trecho:
        return False
    return _normalizar(trecho) in _normalizar(texto)


def montar_casos(brutos: list[dict], documento: str, texto: str, proximo_id: int) -> list[dict]:
    """Converte a saída do LLM nos casos do `dataset.json`."""
    casos = []
    for i, bruto in enumerate(brutos):
        pergunta = (bruto.get("pergunta") or "").strip()
        resposta = (bruto.get("resposta_esperada") or "").strip()
        if not pergunta or not resposta:
            continue
        trecho = (bruto.get("trecho_origem") or "").strip()[:MAX_CHARS_TRECHO]
        dificuldade = bruto.get("dificuldade") or "media"
        casos.append(
            {
                "id": proximo_id + i,
                "pergunta": pergunta,
                "dificuldade": dificuldade
                if dificuldade in {"facil", "media", "dificil"}
                else "media",
                "documento_origem": documento,
                "resposta_esperada": resposta,
                "trecho_origem": trecho,
                "trecho_confere": trecho_confere(trecho, texto),
                "sem_resposta": False,
                "revisao": {"status": "pendente", "em": None},
            }
        )
    return casos


def montar_casos_sem_resposta(brutos: list[dict], proximo_id: int) -> list[dict]:
    casos = []
    for i, bruto in enumerate(brutos):
        pergunta = (bruto.get("pergunta") or "").strip()
        if not pergunta:
            continue
        casos.append(
            {
                "id": proximo_id + i,
                "pergunta": pergunta,
                "dificuldade": bruto.get("dificuldade") or "media",
                # Vazio de propósito: `run_eval.py` compara a fonte
                # recuperada com este campo, e aqui não existe fonte certa.
                "documento_origem": "",
                "resposta_esperada": RESPOSTA_SEM_RESPOSTA,
                "motivo_ausencia": (bruto.get("motivo_ausencia") or "").strip(),
                "sem_resposta": True,
                "revisao": {"status": "pendente", "em": None},
            }
        )
    return casos


def _parse_array(texto: str) -> list[dict]:
    dados = json.loads(strip_code_fence(texto))
    if isinstance(dados, dict):
        # Modelo pequeno às vezes embrulha o array num objeto.
        for valor in dados.values():
            if isinstance(valor, list):
                return [v for v in valor if isinstance(v, dict)]
        return []
    return [d for d in dados if isinstance(d, dict)]


async def _gerar(client, prompt: str) -> list[dict]:
    """Uma chamada ao LLM, com backoff em 429 (tier `:free`)."""
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
        return _parse_array(resposta.text)
    except (ValueError, TypeError) as exc:
        print(f"    JSON inválido do modelo: {exc}")
        return []


def carregar_existente(saida: Path) -> dict:
    if not saida.exists():
        return {}
    try:
        return json.loads(saida.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def envelope(casos: list[dict], modelo: str, corpus: str) -> dict:
    respondiveis = [c for c in casos if not c.get("sem_resposta")]
    sem_resposta = [c for c in casos if c.get("sem_resposta")]
    return {
        "descricao": (
            "Conjunto de RAG documentos da Estratégia A (Fase 10): perguntas "
            "sobre os manuais e datasheets do corpus, mais perguntas sem "
            "resposta no corpus para medir alucinação."
        ),
        "observacao": (
            f"Rascunho gerado por {modelo} sobre {corpus}. Todo item nasce "
            "`revisao.status = pendente`: o gabarito só vale depois da "
            "revisão humana em /admin/datasets. `trecho_confere = false` "
            "marca trecho que não foi localizado no texto do PDF e precisa "
            "de atenção redobrada."
        ),
        "respondiveis": len(respondiveis),
        "sem_resposta": len(sem_resposta),
        "casos": casos,
    }


def salvar(saida: Path, casos: list[dict], modelo: str, corpus: str) -> None:
    saida.write_text(
        json.dumps(envelope(casos, modelo, corpus), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def executar(args) -> int:
    auditoria_path = Path(args.auditoria)
    if not auditoria_path.exists():
        print(f"Auditoria não encontrada: {auditoria_path}. Rode a Etapa 0 antes.")
        return 1
    auditoria = json.loads(auditoria_path.read_text(encoding="utf-8"))
    corpus = Path(auditoria["corpus"])
    raiz = BASE_DIR.parent.parent.parent

    saida = Path(args.saida)
    anterior = carregar_existente(saida)
    casos: list[dict] = []
    if anterior.get("respondiveis") is not None and not args.forcar:
        # Retomada: o que já foi gerado fica, e os documentos já cobertos
        # são pulados. Sem isso, um 429 no documento 70 jogaria fora 69
        # documentos de chamadas pagas em tempo de rate limit.
        casos = list(anterior.get("casos", []))
        print(f"Retomando: {len(casos)} caso(s) já no arquivo.")
    elif anterior and not args.forcar:
        print(
            f"{saida.name} existe no formato antigo ({len(anterior.get('casos', []))} casos "
            "do conjunto invalidado). Use --forcar para sobrescrever."
        )
        return 1

    cobertos = {c.get("documento_origem") for c in casos if not c.get("sem_resposta")}
    docs = documentos_elegiveis(auditoria)
    if args.limite_docs:
        docs = docs[: args.limite_docs]
    plano = cota_por_documento(docs, args.total, args.por_documento)

    settings = get_settings()
    modelo = args.modelo or settings.external_model_name
    if not modelo:
        print("EXTERNAL_MODEL_NAME vazio: configure o modelo do rascunho no .env.")
        return 1
    client = OpenRouterClient(
        base_url=settings.external_model_base_url,
        api_key=settings.external_model_api_key,
        model=modelo,
        timeout_s=settings.external_llm_timeout_s,
    )
    print(f"Modelo do rascunho: {modelo}")
    print(
        f"{len(plano)} documento(s) no plano, meta de {args.total} pergunta(s) respondível(is).\n"
    )

    try:
        for indice, (doc, n) in enumerate(plano, start=1):
            arquivo = doc["arquivo"]
            nome = Path(arquivo).name
            if nome in cobertos:
                continue
            caminho = raiz / corpus / arquivo
            if not caminho.exists():
                print(f"[{indice}/{len(plano)}] {nome}: arquivo ausente, pulando.")
                continue

            texto = extract_text_from_pdf(caminho)[:MAX_CHARS_PROMPT]
            if len(texto) < 200:
                print(f"[{indice}/{len(plano)}] {nome}: texto curto demais, pulando.")
                continue

            print(f"[{indice}/{len(plano)}] {nome} ({len(texto)} chars) -> {n} pergunta(s)")
            brutos = await _gerar(
                client,
                _PROMPT_PERGUNTAS.format(
                    documento=nome, texto=texto, n=n, max_trecho=MAX_CHARS_TRECHO
                ),
            )
            proximo_id = max((c["id"] for c in casos), default=0) + 1
            novos = montar_casos(brutos[:n], nome, texto, proximo_id)
            sem_trecho = sum(1 for c in novos if not c["trecho_confere"])
            casos.extend(novos)
            salvar(saida, casos, modelo, str(corpus))
            print(
                f"    {len(novos)} caso(s) gravado(s)"
                + (f", {sem_trecho} com trecho não localizado" if sem_trecho else "")
            )

        faltam = args.sem_resposta - sum(1 for c in casos if c.get("sem_resposta"))
        if faltam > 0:
            pastas = sorted({Path(d["arquivo"]).parts[0] for d in documentos_elegiveis(auditoria)})
            print(f"\nPerguntas sem resposta no corpus: {faltam} a gerar")
            brutos = await _gerar(
                client,
                _PROMPT_SEM_RESPOSTA.format(produtos="\n".join(f"- {p}" for p in pastas), n=faltam),
            )
            proximo_id = max((c["id"] for c in casos), default=0) + 1
            casos.extend(montar_casos_sem_resposta(brutos[:faltam], proximo_id))
            salvar(saida, casos, modelo, str(corpus))
    finally:
        # Mesmo com erro no meio, o que já foi gerado fica no arquivo: no
        # tier `:free` uma rodada interrompida custa relógio, não dinheiro,
        # mas refazer tudo custaria as duas coisas.
        salvar(saida, casos, modelo, str(corpus))

    respondiveis = sum(1 for c in casos if not c.get("sem_resposta"))
    sem_resp = sum(1 for c in casos if c.get("sem_resposta"))
    sem_trecho = sum(1 for c in casos if not c.get("sem_resposta") and not c.get("trecho_confere"))
    print(f"\n{saida}: {respondiveis} respondível(is) + {sem_resp} sem resposta")
    if sem_trecho:
        print(f"Atenção: {sem_trecho} caso(s) com `trecho_confere = false`.")
    print("Todos nascem pendentes: revise em /admin/datasets antes de rodar a avaliação.")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--auditoria", default=str(AUDITORIA_PADRAO))
    parser.add_argument("--saida", default=str(SAIDA_PADRAO))
    parser.add_argument("--total", type=int, default=TOTAL_RESPONDIVEIS)
    parser.add_argument("--sem-resposta", type=int, default=TOTAL_SEM_RESPOSTA)
    parser.add_argument("--por-documento", type=int, default=POR_DOCUMENTO)
    parser.add_argument("--modelo", default=None, help="padrão: EXTERNAL_MODEL_NAME do .env")
    parser.add_argument("--limite-docs", type=int, default=None, help="só para teste rápido")
    parser.add_argument("--forcar", action="store_true", help="sobrescreve o arquivo existente")
    args = parser.parse_args(argv[1:])
    return asyncio.run(executar(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
