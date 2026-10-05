"""Script para zerar totalmente os produtos no Postgres e os pontos no Qdrant.

Útil para reiniciar o ambiente antes de realizar testes manuais do zero.

Uso (a partir da pasta `backend/` ou da raiz do projeto):
    python scripts/reset_produtos_e_qdrant.py
    # ou
    uv run python scripts/reset_produtos_e_qdrant.py
    # ou sem confirmação interativa:
    python scripts/reset_produtos_e_qdrant.py --sim
"""

import argparse
import asyncio
import sys

import httpx
from sqlalchemy import text

from app.config import get_settings
from app.db.engine import create_db_engine


async def reset_ambiente(sim: bool = False) -> None:
    if not sim:
        confirmacao = input("Deseja ZERAR todos os produtos no Postgres e limpar o Qdrant? [s/N] ")
        if confirmacao.strip().lower() != "s":
            print("Operação cancelada.")
            return

    settings = get_settings()
    engine = create_db_engine(settings.postgres_dsn)

    print("\n[1/2] Limpando tabelas do PostgreSQL...")
    async with engine.begin() as conn:
        # Executa TRUNCATE com CASCADE para zerar produtos e tabelas dependentes
        await conn.execute(
            text(
                "TRUNCATE TABLE produtos, rag_documents RESTART IDENTITY CASCADE;"
            )
        )
        # Remove coleções residuais de teste no banco relacional
        await conn.execute(
            text(
                "DELETE FROM rag_collections WHERE name LIKE 'test_%' OR name = 'xxxx';"
            )
        )
    await engine.dispose()
    print("   ✓ PostgreSQL zerado com sucesso!")

    print("\n[2/2] Limpando coleções do Qdrant...")
    qdrant_url = f"http://{settings.qdrant_host}:{settings.qdrant_port}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{qdrant_url}/collections")
            resp.raise_for_status()
            cols = [c["name"] for c in resp.json().get("result", {}).get("collections", [])]

            for col in cols:
                if col.startswith("test_") or col == "xxxx":
                    r = await client.delete(f"{qdrant_url}/collections/{col}")
                    print(f"   ✓ Coleção temporária '{col}' excluída (status {r.status_code})")
                else:
                    # Deleta todos os vetores/pontos mantendo a coleção ativa
                    r = await client.post(
                        f"{qdrant_url}/collections/{col}/points/delete",
                        json={"filter": {}},
                    )
                    print(f"   ✓ Coleção '{col}' limpa (status {r.status_code})")
        except Exception as e:
            print(f"   ⚠️ Erro ao conectar ao Qdrant ({qdrant_url}): {e}")

    print("\n✨ Ambiente 100% zerado e pronto para testes manuais!\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sim",
        "-y",
        action="store_true",
        help="Executa a limpeza sem solicitar confirmação interativa",
    )
    args = parser.parse_args()

    try:
        asyncio.run(reset_ambiente(sim=args.sim))
    except KeyboardInterrupt:
        print("\nOperação cancelada pelo usuário.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
