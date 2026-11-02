"""Recria a base de clientes fictícia da migração 0011 (Ana, Bruno, Carla).

A migração `0011_clientes.py` semeia esses três clientes uma única vez; se a
tabela `clientes` for limpa depois, a página `/admin/usuarios` e os cenários
R4 a R7 do `teste_local.py` (suíte `memoria`) ficam sem eles. Este script os
recria sem mexer na migração.

Idempotente: cliente que já existe (pelo e-mail) é pulado, sem duplicar compras.
As datas das compras são relativas a hoje, como na migração. Os produtos da
migração original (geradores) não existem mais no catálogo; as compras usam os
primeiros produtos do catálogo atual, só para terem produto e valor.

# MVP: base de clientes fictícia; e-mails no domínio reservado example.com.

Uso:
    cd backend && uv run python scripts/semear_clientes_ficticios.py
"""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.config import get_settings
from app.db.engine import create_db_engine, create_session_factory
from app.db.models import Cliente, ClienteCompra, Produto

# (e-mail, nome, [(posição no catálogo, quantidade, dias atrás)])
_CLIENTES = [
    # Cliente: 3 compras, a última há 30 dias.
    (
        "ana.recorrente@example.com",
        "Ana Recorrente",
        [(0, 1, 30), (1, 1, 90), (2, 1, 200)],
    ),
    # Esporádico: uma única compra.
    ("bruno.unico@example.com", "Bruno Único", [(3, 1, 60)]),
    # Esporádico: 2 compras, mas a mais recente há mais de 12 meses.
    ("carla.antiga@example.com", "Carla Antiga", [(0, 2, 500), (4, 1, 700)]),
]


async def main() -> None:
    engine = create_db_engine(get_settings().postgres_dsn)
    fabrica = create_session_factory(engine)
    agora = datetime.now(UTC)
    async with fabrica() as session:
        produtos = (await session.scalars(select(Produto).order_by(Produto.id).limit(5))).all()
        for email, nome, itens in _CLIENTES:
            if await session.scalar(select(Cliente.id).where(Cliente.email == email)):
                print(f"já existe: {email}")
                continue
            cliente = Cliente(email=email, nome=nome)
            session.add(cliente)
            await session.flush()
            for posicao, quantidade, dias in itens:
                produto = produtos[posicao] if posicao < len(produtos) else None
                preco = Decimal(str(produto.preco)) if produto else Decimal("0")
                session.add(
                    ClienteCompra(
                        cliente_id=cliente.id,
                        produto_id=produto.id if produto else None,
                        quantidade=quantidade,
                        valor_total=preco * quantidade,
                        comprado_em=agora - timedelta(days=dias),
                    )
                )
            print(f"criado: {email}")
        await session.commit()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
