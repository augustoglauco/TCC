"""Gera as 80 perguntas do conjunto de banco (R12, Fase 10).

**Sem LLM e sem revisão humana.** As perguntas são montadas por template a
partir das próprias linhas de `produtos`/`produto_estoque`, então o gabarito é
exato por construção — é a decisão de desenho que derruba a revisão humana da
Estratégia A de 12 h para ~4,5 h (`docs/EVALUATION.md` Seção 0).

**Que caminho isto mede.** Em produção, "quanto custa o iDTouch?" não passa
pelo conector de banco do RAG: cai no domínio de Vendas e é respondida pelo
`app.router.sales_catalog` (`extract_sales_slots` -> `consultar_detalhes`).
É esse caminho que o conjunto exercita — o `app.rag.db_connector` é a outra
feature do R4 (ingerir tabela como texto) e tem outro propósito.

Cada caso carrega o valor cru que o gabarito afirma (`gabarito_bruto`), para
a conferência ser aritmética e não interpretação: se o preço no banco mudar, o
caso fica detectavelmente velho em vez de silenciosamente errado.

Uso (a partir de `backend/`, exige Postgres no ar):

    .venv/bin/python eval/rag_banco/gerar_dataset.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR.parent.parent / "src"))

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db.engine import create_db_engine, create_session_factory  # noqa: E402
from app.db.models import Produto, ProdutoEstoque  # noqa: E402

SAIDA_PADRAO = BASE_DIR / "dataset.json"
# 80 perguntas: a divisão cobre os quatro recursos estruturados do R12
# (preço, estoque consolidado, estoque por CD, prazo) mais duas formas que
# exigem o LLM compor a resposta (comparação e listagem por categoria).
TOTAL_ALVO = 80
COTAS = {
    "preco": 20,
    "estoque_total": 12,
    "estoque_cd": 12,
    "prazo": 12,
    "comparacao_preco": 12,
    "categoria": 12,
}


def _brl(valor: Decimal) -> str:
    return f"R$ {valor:.2f}".replace(".", ",")


def caso(indice: int, tipo: str, pergunta: str, resposta: str, bruto: dict, produto: str) -> dict:
    return {
        "id": indice,
        "tipo": tipo,
        "pergunta": pergunta,
        "resposta_esperada": resposta,
        "gabarito_bruto": bruto,
        "produto": produto,
        # Gabarito exato por construção: a tela mostra como aprovado e não
        # abre fila de revisão para este conjunto.
        "revisao": {"status": "aprovado", "em": None},
    }


Especificacao = tuple[str, str, str, dict, str]  # tipo, pergunta, resposta, bruto, produto


def _girar(ordenados: list[dict], n: int, offset: int) -> list[dict]:
    if not ordenados:
        return []
    return [ordenados[(offset + i) % len(ordenados)] for i in range(n)]


def _spec_preco(p: dict) -> Especificacao:
    return (
        "preco",
        f"Quanto custa o {p['nome']}?",
        _brl(p["preco"]),
        {"preco": str(p["preco"])},
        p["nome"],
    )


def _specs_estoque_total(ordenados: list[dict], estoques: dict[int, dict[str, int]]):
    specs: list[Especificacao] = []
    for p in _girar(ordenados, COTAS["estoque_total"], 7):
        total = sum(estoques.get(p["id"], {}).values())
        resposta = (
            f"Sim, {total} unidades disponíveis somando os centros de distribuição."
            if total > 0
            else "Não há unidades disponíveis em nenhum centro de distribuição."
        )
        bruto = {"estoque_total": total, "por_cd": estoques.get(p["id"], {})}
        specs.append(
            ("estoque_total", f"Vocês têm {p['nome']} em estoque?", resposta, bruto, p["nome"])
        )
    return specs


def _specs_estoque_cd(ordenados: list[dict], estoques: dict[int, dict[str, int]]):
    specs: list[Especificacao] = []
    for i, p in enumerate(_girar(ordenados, COTAS["estoque_cd"], 19)):
        por_cd = estoques.get(p["id"], {})
        if not por_cd:
            continue
        cd = sorted(por_cd)[i % len(por_cd)]
        specs.append(
            (
                "estoque_cd",
                f"Quantas unidades de {p['nome']} tem no {cd}?",
                f"{por_cd[cd]} unidades no {cd}.",
                {"centro_distribuicao": cd, "quantidade": por_cd[cd]},
                p["nome"],
            )
        )
    return specs


def _specs_prazo(ordenados: list[dict]) -> list[Especificacao]:
    return [
        (
            "prazo",
            f"Qual o prazo de reposição do {p['nome']}?",
            f"{p['dias_alerta_estoque']} dias.",
            {"dias": p["dias_alerta_estoque"]},
            p["nome"],
        )
        for p in _girar(ordenados, COTAS["prazo"], 31)
    ]


def _specs_comparacao(ordenados: list[dict]) -> list[Especificacao]:
    """Exige o LLM trazer dois produtos e comparar, não só repetir um campo. O
    gabarito continua exato, porque sai de dois números."""
    specs: list[Especificacao] = []
    for i, p in enumerate(_girar(ordenados, COTAS["comparacao_preco"], 5)):
        outro = ordenados[(5 + i + len(ordenados) // 2) % len(ordenados)]
        if outro["nome"] == p["nome"]:
            continue
        mais_caro = p if p["preco"] >= outro["preco"] else outro
        specs.append(
            (
                "comparacao_preco",
                f"O {p['nome']} é mais caro que o {outro['nome']}?",
                f"{'Sim' if mais_caro['nome'] == p['nome'] else 'Não'}: "
                f"{p['nome']} custa {_brl(p['preco'])} e {outro['nome']} custa "
                f"{_brl(outro['preco'])}.",
                {
                    "preco_a": str(p["preco"]),
                    "preco_b": str(outro["preco"]),
                    "mais_caro": mais_caro["nome"],
                },
                f"{p['nome']} x {outro['nome']}",
            )
        )
    return specs


def _specs_categoria(ordenados: list[dict]) -> list[Especificacao]:
    categorias: dict[str, list[str]] = {}
    for p in ordenados:
        categorias.setdefault(p["categoria"], []).append(p["nome"])
    return [
        (
            "categoria",
            f"Quais produtos vocês têm na categoria {categoria}?",
            f"{len(categorias[categoria])} produto(s): " + ", ".join(categorias[categoria]) + ".",
            {"categoria": categoria, "produtos": categorias[categoria]},
            categoria,
        )
        for categoria in sorted(categorias)[: COTAS["categoria"]]
    ]


def _completar_com_preco(ordenados: list[dict], specs: list[Especificacao]) -> None:
    """As categorias distintas são finitas (10 hoje): se a cota de categoria não
    fecha, o total é completado com perguntas de preço sobre os produtos que
    ainda não entraram, para o conjunto ter exatamente TOTAL_ALVO itens."""
    offset = COTAS["preco"]
    while len(specs) < TOTAL_ALVO and ordenados:
        p = ordenados[offset % len(ordenados)]
        offset += 1
        if any(s[0] == "preco" and s[4] == p["nome"] for s in specs):
            if offset > COTAS["preco"] + 2 * len(ordenados):
                break
            continue
        specs.append(_spec_preco(p))


def montar(produtos: list[dict], estoques: dict[int, dict[str, int]]) -> list[dict]:
    """Monta os casos de forma determinística: a ordem é a do nome do produto,
    e cada cota consome a lista em rodízio. Rodar duas vezes dá o mesmo
    conjunto."""
    ordenados = sorted(produtos, key=lambda p: p["nome"])
    specs: list[Especificacao] = [_spec_preco(p) for p in _girar(ordenados, COTAS["preco"], 0)]
    specs += _specs_estoque_total(ordenados, estoques)
    specs += _specs_estoque_cd(ordenados, estoques)
    specs += _specs_prazo(ordenados)
    specs += _specs_comparacao(ordenados)
    specs += _specs_categoria(ordenados)
    _completar_com_preco(ordenados, specs)
    return [caso(i, *spec) for i, spec in enumerate(specs, start=1)]


def envelope(casos: list[dict], total_produtos: int) -> dict:
    tipos: dict[str, int] = {}
    for c in casos:
        tipos[c["tipo"]] = tipos.get(c["tipo"], 0) + 1
    return {
        "descricao": (
            "Conjunto de banco da Estratégia A (Fase 10): perguntas de preço, "
            "estoque, prazo, comparação e categoria montadas a partir das "
            "linhas de `produtos`/`produto_estoque`."
        ),
        "observacao": (
            "Gerado por template, sem LLM: o gabarito é exato por construção e "
            "o conjunto não passa por revisão humana. Exercita o caminho de "
            "produção do domínio de Vendas (`app.router.sales_catalog`), não o "
            "conector de banco do RAG. `gabarito_bruto` guarda o valor cru de "
            f"cada afirmação. Base: {total_produtos} produtos no catálogo."
        ),
        "total": len(casos),
        "por_tipo": tipos,
        "casos": casos,
    }


async def executar(args) -> int:
    settings = get_settings()
    engine = create_db_engine(settings.postgres_dsn)
    Session = create_session_factory(engine)
    async with Session() as session:
        produtos = [
            {
                "id": p.id,
                "nome": p.nome,
                "preco": p.preco,
                "categoria": p.categoria,
                "dias_alerta_estoque": p.dias_alerta_estoque,
            }
            for p in (await session.execute(select(Produto))).scalars().all()
        ]
        estoques: dict[int, dict[str, int]] = {}
        for linha in (await session.execute(select(ProdutoEstoque))).scalars().all():
            estoques.setdefault(linha.produto_id, {})[linha.centro_distribuicao] = linha.quantidade
    await engine.dispose()

    casos = montar(produtos, estoques)
    saida = Path(args.saida)
    if not args.dry_run:
        saida.write_text(
            json.dumps(envelope(casos, len(produtos)), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    env = envelope(casos, len(produtos))
    print(f"{len(casos)} caso(s) sobre {len(produtos)} produto(s): {env['por_tipo']}")
    if not args.dry_run:
        print(f"gravado em {saida}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", default=str(SAIDA_PADRAO))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv[1:])
    return asyncio.run(executar(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
