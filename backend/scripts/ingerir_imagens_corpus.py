"""Ingere as fotos do corpus ControlId no CLIP, uma por produto (Fase 10).

O conjunto de RAG imagem (77 produto + 30 não-produto) tem gabarito exato por
construção: o produto certo é o da **pasta** de onde a foto saiu. Para a
avaliação medir o caminho de produção, e não o fallback, cada ponto no CLIP
precisa do `produto_id` — `app.rag.image_identification` resolve o produto por
ele e só cai no nome quando não há.

Espelha o fluxo real de `app.api.admin_products`: salva a imagem no diretório
servido, grava em `produto_imagens` com o `clip_image_id` e indexa no CLIP com
`filename` = nome do produto e `domain` = "vendas".

# MVP: a associação foto -> produto é pelo nome da pasta do fornecedor. É o
# gabarito que `docs/EVALUATION.md` Seção 0 já definiu para o conjunto de
# imagem, e é o que dispensa revisão humana nesse conjunto.

Uso (a partir de `backend/`, exige Postgres e Qdrant no ar):

    .venv/bin/python scripts/ingerir_imagens_corpus.py --dry-run
    .venv/bin/python scripts/ingerir_imagens_corpus.py
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parent / "src"))

from sqlalchemy import select  # noqa: E402

from app.api.uploads import salvar_imagem_produto  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db.engine import create_db_engine, create_session_factory  # noqa: E402
from app.db.models import Produto, ProdutoImagem  # noqa: E402
from app.rag.clip_embedder import ClipEmbedder  # noqa: E402
from app.rag.image_search import ClipImageStore  # noqa: E402
from app.rag.qdrant_client import QdrantRAGClient  # noqa: E402

AUDITORIA = BASE_DIR.parent / "eval" / "rag_ingestion" / "auditoria_corpus.json"
# Mesmo mapeamento de `popular_produtos_corpus.py`: a pasta do iDFace já é
# coberta pelo SKU existente no catálogo.
PASTA_PARA_PRODUTO: dict[str, str] = {"iDFace": "IDFACE/FP/A"}


HOLDOUT_SAIDA = BASE_DIR.parent / "eval" / "model_benchmark" / "imagens" / "holdout.json"


def imagens_validas(auditoria: dict) -> list[dict]:
    return [i for i in auditoria.get("itens_imagens", []) if i.get("classificacao") == "valida"]


def escolher_holdout(imagens: list[dict]) -> dict[str, str]:
    """Uma foto de consulta por pasta com 2+ fotos.

    Consultar o CLIP com uma foto que está indexada devolve score 1,000 e
    acerto garantido — mede identidade, não reconhecimento (medido em
    2026-10-17: 5 de 5). A foto escolhida fica **fora** do índice e vira a
    consulta do conjunto de imagem.

    A escolha é a última em ordem alfabética, não aleatória: rodar de novo dá
    o mesmo conjunto, e um resultado antigo continua comparável.

    Pasta com uma só foto não entra: ou a foto está no índice (e não há
    consulta) ou é a consulta (e o produto não está no índice).
    """
    por_pasta: dict[str, list[str]] = {}
    for item in imagens:
        pasta, _, _ = item["arquivo"].partition("/")
        por_pasta.setdefault(pasta, []).append(item["arquivo"])
    return {
        pasta: sorted(arquivos)[-1] for pasta, arquivos in por_pasta.items() if len(arquivos) >= 2
    }


async def limpar_duplicatas_das_consultas(session, store, holdout, corpus_dir) -> int:
    """Remove do índice qualquer cópia byte-idêntica de uma foto de consulta.

    Achado de 2026-10-17: o holdout tirou do índice as fotos do `iDFace`, mas
    `IDFACE/FP/M` guardava **as mesmas duas imagens** de uma ingestão de teste
    antiga — e a consulta voltou a casar com score 1,000, agora apontando para
    o produto errado. Tirar a foto de uma pasta não basta se a mesma imagem
    está indexada em outro lugar: o vazamento de identidade volta por fora.

    A comparação é por SHA-256 do arquivo, não por nome: o upload renomeia
    tudo para UUID.
    """
    alvos = {
        hashlib.sha256((corpus_dir / arquivo).read_bytes()).hexdigest()
        for arquivo in holdout.values()
        if (corpus_dir / arquivo).exists()
    }
    if not alvos:
        return 0
    base = Path(get_settings().product_images_dir)
    removidas = 0
    linhas = (await session.execute(select(ProdutoImagem))).scalars().all()
    for linha in linhas:
        caminho = base / Path(linha.imagem_url).name
        if not caminho.exists():
            continue
        if hashlib.sha256(caminho.read_bytes()).hexdigest() not in alvos:
            continue
        if linha.clip_image_id:
            await store.delete_image(linha.clip_image_id)
        await session.delete(linha)
        removidas += 1
    if removidas:
        await session.commit()
    return removidas


@dataclass
class Contagem:
    indexadas: int = 0
    sem_produto: int = 0
    ja_tinham: int = 0
    falhas: int = 0


@dataclass
class ContextoIngestao:
    dry_run: bool
    session: object
    store: ClipImageStore
    embedder: ClipEmbedder
    produtos: dict[str, int]
    ja_indexadas: set[str]
    raiz: Path
    corpus: Path


async def _liberar_produtos_do_holdout(args, ctx: ContextoIngestao, holdout: dict[str, str]):
    """Tira do índice as fotos dos produtos com holdout, para reindexar sem a
    foto de consulta. Devolve o novo conjunto de `ja_indexadas`."""
    print(f"-- holdout: {len(holdout)} pasta(s) com 2+ fotos cedem 1 consulta cada --")
    alvos = {
        ctx.produtos[PASTA_PARA_PRODUTO.get(pasta, pasta)]
        for pasta in holdout
        if PASTA_PARA_PRODUTO.get(pasta, pasta) in ctx.produtos
    }
    removidos = 0
    for pid in sorted(alvos):
        if args.dry_run:
            continue
        await ctx.store.delete_images_by_product_id(pid)
        for linha in (
            (
                await ctx.session.execute(
                    select(ProdutoImagem).where(ProdutoImagem.produto_id == pid)
                )
            )
            .scalars()
            .all()
        ):
            await ctx.session.delete(linha)
            removidos += 1
    ja_indexadas = ctx.ja_indexadas
    if not args.dry_run:
        await ctx.session.commit()
        ja_indexadas = set()
    print(
        f"   {removidos} linha(s) de produto_imagens e os pontos CLIP "
        f"de {len(alvos)} produto(s) removidos para reindexar"
    )
    return ja_indexadas


async def _indexar_imagem(
    ctx: ContextoIngestao, arquivo: str, caminho: Path, nome_produto: str, produto_id: int
) -> str:
    """Salva e indexa uma foto. Devolve "indexada", "ja_tinha" ou "falha"."""
    conteudo = caminho.read_bytes()
    url, _ = salvar_imagem_produto(conteudo, f"corpus_{produto_id}_{caminho.name}")
    if url in ctx.ja_indexadas:
        return "ja_tinha"
    try:
        clip_id = await ctx.store.upsert_image(
            embedder=ctx.embedder,
            image_bytes=conteudo,
            filename=nome_produto,
            domain="vendas",
            produto_id=produto_id,
            imagem_url=url,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"! {arquivo}: falha ao indexar no CLIP: {exc}")
        return "falha"
    ctx.session.add(ProdutoImagem(produto_id=produto_id, imagem_url=url, clip_image_id=clip_id))
    return "indexada"


async def _processar_imagem(
    ctx: ContextoIngestao,
    item: dict,
    holdout: dict[str, str],
    consultas: list[dict],
    cont: Contagem,
) -> None:
    arquivo = item["arquivo"]
    pasta = arquivo.partition("/")[0]
    if holdout.get(pasta) == arquivo:
        # Fica fora do índice de propósito: é a consulta do conjunto.
        consultas.append(
            {
                "arquivo": arquivo,
                "pasta": pasta,
                "produto_esperado": PASTA_PARA_PRODUTO.get(pasta, pasta),
                "e_do_portfolio": True,
            }
        )
        print(f"H {arquivo}: reservada como consulta ({pasta})")
        return
    nome_produto = PASTA_PARA_PRODUTO.get(pasta, pasta)
    produto_id = ctx.produtos.get(nome_produto)
    if produto_id is None:
        # Pasta sem produto no catálogo (`Suporte`, por exemplo): a
        # foto não entra, senão o gabarito aponta para nada.
        cont.sem_produto += 1
        print(f"- {arquivo}: pasta '{pasta}' sem produto no catálogo, fora")
        return

    caminho = ctx.raiz / ctx.corpus / arquivo
    if not caminho.exists():
        cont.falhas += 1
        print(f"! {arquivo}: arquivo ausente")
        return

    print(f"+ {arquivo} -> {nome_produto} (produto {produto_id})")
    if ctx.dry_run:
        cont.indexadas += 1
        return

    resultado = await _indexar_imagem(ctx, arquivo, caminho, nome_produto, produto_id)
    if resultado == "ja_tinha":
        cont.ja_tinham += 1
    elif resultado == "falha":
        cont.falhas += 1
    else:
        cont.indexadas += 1
        if cont.indexadas % 10 == 0:
            await ctx.session.commit()
            print(f"    ... {cont.indexadas} indexada(s)")


def _gravar_manifesto_holdout(consultas: list[dict]) -> None:
    HOLDOUT_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    HOLDOUT_SAIDA.write_text(
        json.dumps(
            {
                "descricao": (
                    "Fotos reservadas como consulta do conjunto de RAG imagem: "
                    "ficam FORA do índice CLIP, uma por pasta com 2+ fotos."
                ),
                "observacao": (
                    "Sem holdout, consultar com foto indexada dá score 1,000 e "
                    "acerto garantido — identidade, não reconhecimento. Escolha "
                    "determinística (última em ordem alfabética da pasta)."
                ),
                "total": len(consultas),
                "consultas": consultas,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nmanifesto de consultas: {HOLDOUT_SAIDA} ({len(consultas)} itens)")


async def executar(args) -> int:
    auditoria = json.loads(AUDITORIA.read_text(encoding="utf-8"))
    corpus = Path(auditoria["corpus"])
    raiz = BASE_DIR.parent.parent
    imagens = imagens_validas(auditoria)

    settings = get_settings()
    engine = create_db_engine(settings.postgres_dsn)
    Session = create_session_factory(engine)
    qdrant = QdrantRAGClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        timeout_s=settings.qdrant_timeout_s,
    )
    store = ClipImageStore(qdrant.async_client)
    embedder = ClipEmbedder(timeout_s=settings.clip_timeout_s)

    cont = Contagem()
    consultas: list[dict] = []
    async with Session() as session:
        ctx = ContextoIngestao(
            dry_run=args.dry_run,
            session=session,
            store=store,
            embedder=embedder,
            produtos={
                nome: pid
                for pid, nome in (await session.execute(select(Produto.id, Produto.nome))).all()
            },
            ja_indexadas=set((await session.execute(select(ProdutoImagem.imagem_url))).scalars()),
            raiz=raiz,
            corpus=corpus,
        )

        holdout = escolher_holdout(imagens) if args.holdout else {}
        if args.holdout:
            ctx.ja_indexadas = await _liberar_produtos_do_holdout(args, ctx, holdout)

        if args.holdout and not args.dry_run:
            removidas = await limpar_duplicatas_das_consultas(
                session, store, holdout, raiz / corpus
            )
            if removidas:
                print(f"   {removidas} cópia(s) de foto de consulta removida(s) do índice")

        for item in imagens:
            await _processar_imagem(ctx, item, holdout, consultas, cont)

        if not args.dry_run:
            await session.commit()

    if args.holdout and not args.dry_run:
        _gravar_manifesto_holdout(consultas)

    await engine.dispose()
    rotulo = "(dry-run) " if args.dry_run else ""
    print(
        f"\n{rotulo}{cont.indexadas} imagem(ns) indexada(s), {cont.sem_produto} sem produto, "
        f"{cont.ja_tinham} já estavam, {cont.falhas} falha(s). Total de válidas: {len(imagens)}."
    )
    return 1 if cont.falhas else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--holdout",
        action="store_true",
        help="reindexa deixando 1 foto por pasta fora do índice, como consulta do conjunto",
    )
    args = parser.parse_args(argv[1:])
    return asyncio.run(executar(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
