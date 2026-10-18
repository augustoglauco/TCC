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
import json
import sys
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


def imagens_validas(auditoria: dict) -> list[dict]:
    return [i for i in auditoria.get("itens_imagens", []) if i.get("classificacao") == "valida"]


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

    indexadas, sem_produto, ja_tinham, falhas = 0, 0, 0, 0
    async with Session() as session:
        produtos = {
            nome: pid
            for pid, nome in (await session.execute(select(Produto.id, Produto.nome))).all()
        }
        ja_indexadas = set((await session.execute(select(ProdutoImagem.imagem_url))).scalars())

        for item in imagens:
            arquivo = item["arquivo"]
            pasta = arquivo.split("/")[0]
            nome_produto = PASTA_PARA_PRODUTO.get(pasta, pasta)
            produto_id = produtos.get(nome_produto)
            if produto_id is None:
                # Pasta sem produto no catálogo (`Suporte`, por exemplo): a
                # foto não entra, senão o gabarito aponta para nada.
                sem_produto += 1
                print(f"- {arquivo}: pasta '{pasta}' sem produto no catálogo, fora")
                continue

            caminho = raiz / corpus / arquivo
            if not caminho.exists():
                falhas += 1
                print(f"! {arquivo}: arquivo ausente")
                continue

            print(f"+ {arquivo} -> {nome_produto} (produto {produto_id})")
            if args.dry_run:
                indexadas += 1
                continue

            conteudo = caminho.read_bytes()
            url, _ = salvar_imagem_produto(conteudo, f"corpus_{produto_id}_{caminho.name}")
            if url in ja_indexadas:
                ja_tinham += 1
                continue
            try:
                clip_id = await store.upsert_image(
                    embedder=embedder,
                    image_bytes=conteudo,
                    filename=nome_produto,
                    domain="vendas",
                    produto_id=produto_id,
                    imagem_url=url,
                )
            except Exception as exc:  # noqa: BLE001
                falhas += 1
                print(f"! {arquivo}: falha ao indexar no CLIP: {exc}")
                continue
            session.add(ProdutoImagem(produto_id=produto_id, imagem_url=url, clip_image_id=clip_id))
            indexadas += 1
            if indexadas % 10 == 0:
                await session.commit()
                print(f"    ... {indexadas} indexada(s)")

        if not args.dry_run:
            await session.commit()

    await engine.dispose()
    rotulo = "(dry-run) " if args.dry_run else ""
    print(
        f"\n{rotulo}{indexadas} imagem(ns) indexada(s), {sem_produto} sem produto, "
        f"{ja_tinham} já estavam, {falhas} falha(s). Total de válidas: {len(imagens)}."
    )
    return 1 if falhas else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv[1:])
    return asyncio.run(executar(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
