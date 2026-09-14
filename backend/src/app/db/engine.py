"""Engine/sessão assíncrona do Postgres (SQLAlchemy 2.0).

# MVP: sem singleton/lru_cache global (ao contrário de `app.config.get_settings`)
# — o engine é criado explicitamente por quem precisa dele (`app.main` em
# produção, fixtures nos testes), para não prender uma conexão "morta" entre
# testes que sobem/derrubam o banco. Mesmo espírito do `QdrantRAGClient`, que
# também é instanciado explicitamente em vez de um singleton por config.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_db_engine(dsn: str) -> AsyncEngine:
    return create_async_engine(dsn)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
