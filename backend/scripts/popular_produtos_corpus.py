"""Popula `produtos` e `produto_estoque` com uma linha por produto do corpus
ControlId (Fase 10, Estratégia A — `docs/EVALUATION.md` Seção 0).

O conjunto de RAG banco (80 perguntas) tem gabarito exato por construção: as
perguntas são geradas a partir destas linhas. A identificação por imagem
também depende delas — o fluxo de produção resolve o produto pelo
`produto_id` do ponto CLIP (`app.rag.image_identification`) e só cai no nome
como fallback.

# MVP: preço, estoque e prazo de reposição são **inventados** (autorizado
# pelo dono em 2026-10-17). A empresa é fictícia e não existe tabela de
# preços real; o que importa para a avaliação é que o gabarito seja
# verificável, não que o número seja de mercado.

Os valores são **determinísticos**: derivam de um hash do nome da pasta, não
de `random`. Rodar o script duas vezes produz o mesmo catálogo, e um conjunto
de perguntas já gerado continua valendo. O script também é idempotente —
produto que já existe não é alterado, nem o preço — justamente para não
invalidar gabarito gerado antes.

Uso (a partir de `backend/`, exige Postgres no ar):

    .venv/bin/python scripts/popular_produtos_corpus.py --dry-run
    .venv/bin/python scripts/popular_produtos_corpus.py
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parent / "src"))

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db.engine import create_db_engine, create_session_factory  # noqa: E402
from app.db.models import Produto, ProdutoEstoque  # noqa: E402

AUDITORIA = BASE_DIR.parent / "eval" / "rag_ingestion" / "auditoria_corpus.json"
CENTROS = ("CD-Matriz", "CD-SP", "CD-RJ")

# Pastas do corpus que não viram produto, com o motivo — a lista é o registro
# da decisão, não um filtro silencioso.
NAO_PRODUTO: dict[str, str] = {
    "Suporte": "documentação de suporte do fornecedor, não é item de catálogo",
    "iDflexpro": "pasta sem material (0 PDFs úteis, 0 imagens válidas)",
}

# Pasta já coberta por linha existente no banco: o catálogo tem o SKU, e criar
# uma linha com o nome da pasta deixaria duas respostas certas para "qual o
# preço do iDFace?" — a mesma ambiguidade que invalidou perguntas do RAG.
JA_NO_CATALOGO: dict[str, str] = {"iDFace": "IDFACE/FP/A"}

# (categoria, faixa de preço em R$). Faixa plausível para o mercado
# brasileiro de controle de acesso, por tipo de equipamento.
CATEGORIAS: dict[str, tuple[str, tuple[int, int]]] = {
    "IDBlock": ("Catraca e Torniquete", (6_000, 14_000)),
    "IDBlock Facial": ("Catraca e Torniquete", (9_000, 18_000)),
    "iDBlock Next": ("Catraca e Torniquete", (9_000, 18_000)),
    "iDBlockBio": ("Catraca e Torniquete", (8_000, 16_000)),
    "Torniquetes": ("Catraca e Torniquete", (7_000, 16_000)),
    "REP iDClass": ("Relógio de Ponto", (2_500, 5_500)),
    "REP iDClass Facial": ("Relógio de Ponto", (3_500, 6_500)),
    "Print iD": ("Impressora de Crachá", (4_000, 9_000)),
    "Print iD Touch": ("Impressora de Crachá", (5_000, 10_000)),
    "iDSecure Cloud": ("Software e Licença", (600, 3_500)),
    "RHiD": ("Software e Licença", (500, 3_000)),
    "SAT iD": ("Software e Licença", (800, 3_200)),
    "Tags": ("Acessório", (8, 120)),
    "IDPower": ("Fonte e Energia", (300, 1_200)),
    "iDBell": ("Vídeo Porteiro", (700, 1_800)),
    "iDdLock": ("Fechadura Eletrônica", (900, 2_500)),
    "Leitor  QR Code": ("Leitor", (600, 1_600)),
    "iDProx": ("Leitor", (500, 1_500)),
    "iDUHF": ("Leitor", (1_200, 3_000)),
    "iDUHF Lite": ("Leitor", (900, 2_200)),
}
CATEGORIA_PADRAO = ("Controle de Acesso", (800, 3_500))

# Prazo de reposição/entrega em dias (`dias_alerta_estoque`): equipamento
# grande demora mais que licença.
PRAZO_POR_CATEGORIA: dict[str, int] = {
    "Catraca e Torniquete": 30,
    "Impressora de Crachá": 21,
    "Relógio de Ponto": 15,
    "Software e Licença": 5,
    "Acessório": 7,
}
PRAZO_PADRAO = 15


def _semente(nome: str) -> int:
    """Inteiro estável a partir do nome — nada de `random`, para o catálogo
    ser o mesmo em qualquer máquina e em qualquer rodada."""
    return int(hashlib.sha256(nome.encode("utf-8")).hexdigest()[:12], 16)


def categoria_e_preco(pasta: str) -> tuple[str, Decimal]:
    categoria, (minimo, maximo) = CATEGORIAS.get(pasta, CATEGORIA_PADRAO)
    bruto = minimo + _semente(pasta) % (maximo - minimo)
    # Termina em 0 ou 90 centavos: preço de catálogo não é número redondo.
    centavos = 90 if _semente(pasta) % 2 else 0
    return categoria, Decimal(f"{bruto}.{centavos:02d}")


def estoque_por_cd(pasta: str) -> dict[str, int]:
    """Quantidade por centro de distribuição.

    Um em cada seis produtos fica zerado nos três CDs de propósito: sem item
    sem estoque, o conjunto de perguntas do banco não teria como cobrir
    "está disponível?" com resposta negativa, e a avaliação mediria só o
    caminho felizmente abastecido.
    """
    semente = _semente(pasta)
    if semente % 6 == 0:
        return {cd: 0 for cd in CENTROS}
    return {cd: (semente >> (4 * i)) % 40 for i, cd in enumerate(CENTROS)}


def produtos_do_corpus(auditoria: dict) -> list[str]:
    pastas = sorted({i["arquivo"].split("/")[0] for i in auditoria["itens_pdfs"]})
    pastas += [i["pasta"] for i in auditoria["itens_pastas"] if i["pasta"] not in pastas]
    return [p for p in sorted(set(pastas)) if p not in NAO_PRODUTO and p not in JA_NO_CATALOGO]


def descricao(pasta: str, categoria: str) -> str:
    return (
        f"{pasta} — linha {categoria.lower()} do catálogo ControlId. "
        "Especificações técnicas completas no manual e no datasheet do produto, "
        "indexados no RAG de documentos."
    )


async def executar(args) -> int:
    auditoria = json.loads(AUDITORIA.read_text(encoding="utf-8"))
    pastas = produtos_do_corpus(auditoria)

    settings = get_settings()
    engine = create_db_engine(settings.postgres_dsn)
    Session = create_session_factory(engine)

    criados, existentes, estoques = 0, 0, 0
    async with Session() as session:
        nomes_no_banco = set((await session.execute(select(Produto.nome))).scalars())
        for pasta in pastas:
            categoria, preco = categoria_e_preco(pasta)
            prazo = PRAZO_POR_CATEGORIA.get(categoria, PRAZO_PADRAO)
            quantidades = estoque_por_cd(pasta)
            if pasta in nomes_no_banco:
                existentes += 1
                print(f"= {pasta}: já no catálogo, intacto")
                continue
            print(
                f"+ {pasta}: {categoria} | R$ {preco} | prazo {prazo}d | "
                + ", ".join(f"{cd}={q}" for cd, q in quantidades.items())
            )
            criados += 1
            if args.dry_run:
                continue
            produto = Produto(
                nome=pasta,
                descricao=descricao(pasta, categoria),
                preco=preco,
                categoria=categoria,
                dias_alerta_estoque=prazo,
            )
            session.add(produto)
            await session.flush()
            for cd, quantidade in quantidades.items():
                session.add(
                    ProdutoEstoque(
                        produto_id=produto.id, centro_distribuicao=cd, quantidade=quantidade
                    )
                )
                estoques += 1
        if not args.dry_run:
            await session.commit()

    await engine.dispose()
    rotulo = "(dry-run) " if args.dry_run else ""
    print(f"\n{rotulo}{criados} produto(s) a criar, {existentes} já existente(s).")
    if not args.dry_run:
        print(f"{estoques} linha(s) de estoque gravada(s) em {len(CENTROS)} CDs.")
    for pasta, motivo in NAO_PRODUTO.items():
        print(f"fora: {pasta} — {motivo}")
    for pasta, sku in JA_NO_CATALOGO.items():
        print(f"fora: {pasta} — já coberta pelo SKU {sku}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv[1:])
    return asyncio.run(executar(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
