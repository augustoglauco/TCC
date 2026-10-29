"""Métricas de recuperação da Etapa 1 (Fase 10, R4 — `docs/EVALUATION.md`
Seção 2.1).

Funções **puras**: recebem o gabarito e a lista ordenada de fontes
recuperadas, devolvem número. Nenhuma I/O, nenhum Qdrant, nenhum modelo —
é o que permite testá-las sem infraestrutura no ar (`docs/CONVENTIONS.md`,
seção "Testes") e o que torna a Etapa 1 barata: medir uma configuração não
custa chamada de API nenhuma, ao contrário de `eval/rag_quality/`, que gasta
uma chamada de LLM-as-judge por pergunta.

**Granularidade: documento, não chunk.** O gabarito nomeia o PDF que contém
a resposta, não o pedaço de texto, então a relevância é avaliada no nível do
arquivo de origem. Como vários chunks recuperados podem vir do mesmo PDF, as
fontes são deduplicadas preservando a melhor posição antes de medir — senão
um PDF que aparece nas posições 1, 2 e 3 contaria três vezes e inflaria o
nDCG.

**Caso negativo.** Pergunta com `fontes_aceitas` vazia é uma pergunta *sem
resposta no corpus* (20 das 180 da Estratégia A). Para ela, o acerto é
devolver **nada**, e as métricas de ranking não se aplicam — por isso
`avaliar_conjunto` reporta positivas e negativas em separado, nunca numa
média única. Misturar as duas produziria um número que sobe quando o sistema
fica mais calado e quando fica mais acertivo, sem distinguir os dois.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass


def deduplicar_com_score(pares: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Mantém a primeira ocorrência de cada fonte, com o score dela.

    A entrada vem na ordem de recuperação (melhor score primeiro), então a
    primeira ocorrência de um documento é a sua melhor posição, e é o score
    dela que fica. Devolver os pares (em vez de só as fontes) existe porque a
    varredura offline de `score_threshold` (Etapa 4) precisa saber com que
    score cada *documento* entrou — guardar a lista de fontes deduplicada
    ao lado da lista de scores crua desalinha as duas (5 chunks podem virar
    3 fontes) e inviabiliza a varredura.
    """
    vistas: set[str] = set()
    saida: list[tuple[str, float]] = []
    for fonte, score in pares:
        if fonte not in vistas:
            vistas.add(fonte)
            saida.append((fonte, score))
    return saida


def aplicar_threshold(
    pares: list[tuple[str, float]], score_threshold: float, top_k: int | None = None
) -> list[str]:
    """Filtra `pares` por score e corta em `top_k` — a varredura da Etapa 4
    sem reingerir nada.

    Pressupõe `pares` em ordem decrescente de score (como o Qdrant devolve),
    e que o `score_threshold` usado na busca que os gerou era **menor ou
    igual** a este: não se pode recuperar, offline, um documento que a busca
    original já cortou. Daí a rodada-base usar um threshold baixo.
    """
    fontes = [fonte for fonte, score in pares if score >= score_threshold]
    return fontes[:top_k] if top_k is not None else fontes


_EXTENSOES_DOCUMENTO = re.compile(r"\.(pdf|md|txt)$")


def chave_fonte(nome: str) -> str:
    """Identidade de um documento sem a extensão: o mesmo conteúdo em `.pdf`
    e em `.md` (ingestão tratada) conta como a mesma fonte."""
    return _EXTENSOES_DOCUMENTO.sub("", re.sub(r"\s+", " ", nome.lower()).strip())


def acerta_fonte(fonte: str, aceitas: set[str]) -> bool:
    return chave_fonte(fonte) in {chave_fonte(a) for a in aceitas}


def recall_at_k(recuperadas: list[str], aceitas: set[str], k: int) -> float:
    """1.0 se alguma fonte aceita está entre as `k` primeiras, senão 0.0.

    Binário por pergunta (não a fração de fontes aceitas encontradas):
    o que interessa é se o gerador recebeu a fonte certa no contexto, e
    basta uma. A média sobre as perguntas é a taxa de recuperação.
    """
    if k <= 0:
        raise ValueError("k deve ser positivo")
    if not aceitas:
        raise ValueError("recall_at_k não se aplica a caso negativo (aceitas vazio)")
    return 1.0 if any(acerta_fonte(f, aceitas) for f in recuperadas[:k]) else 0.0


def posicao_do_primeiro_acerto(recuperadas: list[str], aceitas: set[str]) -> int | None:
    """Posição 1-indexada da primeira fonte aceita, ou `None` se não houver."""
    for posicao, fonte in enumerate(recuperadas, start=1):
        if acerta_fonte(fonte, aceitas):
            return posicao
    return None


def reciprocal_rank(recuperadas: list[str], aceitas: set[str]) -> float:
    """1/posição da primeira fonte aceita; 0.0 se nenhuma foi recuperada.
    A média sobre as perguntas é o MRR."""
    if not aceitas:
        raise ValueError("reciprocal_rank não se aplica a caso negativo")
    posicao = posicao_do_primeiro_acerto(recuperadas, aceitas)
    return 1.0 / posicao if posicao else 0.0


def ndcg_at_k(recuperadas: list[str], aceitas: set[str], k: int = 10) -> float:
    """nDCG@k com relevância binária no nível de documento.

    DCG = Σ rel_i / log2(i+1) sobre as `k` primeiras posições. O IDCG é o
    DCG do ranking ideal, em que as `min(len(aceitas), k)` primeiras
    posições são todas relevantes — o que faz a métrica valer 1.0 quando
    todas as fontes aceitas vêm no topo, inclusive quando são várias.
    Métrica principal de comparação entre configurações, e a mesma que o
    MTEB-BR usa, o que permite comparar a ordem de grandeza com a
    literatura.
    """
    if k <= 0:
        raise ValueError("k deve ser positivo")
    if not aceitas:
        raise ValueError("ndcg_at_k não se aplica a caso negativo")
    dcg = sum(
        1.0 / math.log2(posicao + 1)
        for posicao, fonte in enumerate(recuperadas[:k], start=1)
        if acerta_fonte(fonte, aceitas)
    )
    idcg = sum(1.0 / math.log2(posicao + 1) for posicao in range(1, min(len(aceitas), k) + 1))
    return dcg / idcg if idcg else 0.0


@dataclass(frozen=True)
class ResultadoPergunta:
    """Uma pergunta avaliada. `recuperadas` já vem deduplicada por fonte."""

    id: str
    negativa: bool
    recuperadas: list[str]
    aceitas: set[str]

    @property
    def vazio(self) -> bool:
        return not self.recuperadas

    @property
    def acertou_negativa(self) -> bool:
        """Para caso negativo, acerto é não devolver nada."""
        return self.negativa and self.vazio


def avaliar_conjunto(
    resultados: list[ResultadoPergunta], ks: tuple[int, ...] = (1, 3, 5, 10)
) -> dict:
    """Agrega as métricas de um conjunto, separando positivas de negativas.

    Devolve `None` (não 0.0) para uma métrica sem amostra — um conjunto sem
    caso negativo não tem "taxa de acerto negativo" igual a zero, não tem
    taxa nenhuma, e reportar 0,0 ali faria parecer falha total.
    """
    positivas = [r for r in resultados if not r.negativa]
    negativas = [r for r in resultados if r.negativa]

    def media(valores: list[float]) -> float | None:
        return sum(valores) / len(valores) if valores else None

    return {
        "n_total": len(resultados),
        "n_positivas": len(positivas),
        "n_negativas": len(negativas),
        "recall": {
            f"@{k}": media([recall_at_k(r.recuperadas, r.aceitas, k) for r in positivas])
            for k in ks
        },
        "ndcg@10": media([ndcg_at_k(r.recuperadas, r.aceitas, 10) for r in positivas]),
        "mrr": media([reciprocal_rank(r.recuperadas, r.aceitas) for r in positivas]),
        # Numa positiva, vazio é falha de recuperação (nada passou do
        # score_threshold). Numa negativa, é o acerto. São grandezas
        # diferentes e ficam em campos diferentes de propósito.
        "taxa_vazio_positivas": media([1.0 if r.vazio else 0.0 for r in positivas]),
        "acerto_negativas": media([1.0 if r.acertou_negativa else 0.0 for r in negativas]),
    }
