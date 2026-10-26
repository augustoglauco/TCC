"""Cria e ativa a collection de chat com o perfil vencedor da Fase 10 (R4).

Perfil medido nas Etapas 2–3 (`docs/EVALUATION.md` §2.1): `BAAI/bge-m3`, chunk de
768 tokens com overlap de 115, cosine. Ingere o mesmo corpus auditado das
Etapas 1–5 (`carregar_arquivos_a_ingerir`) com `origin="corpus_avaliacao"` e
`domain="suporte"`, como a collection anterior (`docs_texto_gemma512`), que
fica **inativa e intacta** para reverter (reativar pela tela de collections).

Só ativa depois que a ingestão termina sem erro. Recusa rodar se o nome existe.

Uso (a partir de `backend/`, com Qdrant e Postgres no ar):

    .venv/bin/python -u eval/rag_ingestion/criar_collection_vencedora.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parents[1] / "src"))
sys.path.insert(0, str(BASE_DIR))

from dataset import carregar_dataset  # noqa: E402
from run_etapa1 import HNSW_PADRAO, carregar_arquivos_a_ingerir  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db.engine import create_db_engine, create_session_factory  # noqa: E402
from app.rag.collections_registry import (  # noqa: E402
    activate_collection,
    create_collection,
    get_collection_by_name,
)
from app.rag.embedders_registry import EmbedderRegistry  # noqa: E402
from app.rag.ingest import ingest_file  # noqa: E402
from app.rag.qdrant_client import QdrantRAGClient  # noqa: E402

NOME = "docs_texto_bge768"
MODELO = "BAAI/bge-m3"
CHUNK_SIZE = 768
CHUNK_OVERLAP = 115
DOMINIO = "suporte"
ORIGEM = "corpus_avaliacao"


async def main() -> int:
    settings = get_settings()
    qdrant = QdrantRAGClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        timeout_s=settings.qdrant_timeout_s,
        search_domain_fallback=settings.rag_search_domain_fallback,
    )
    session_factory = create_session_factory(create_db_engine(settings.postgres_dsn))
    embedder = EmbedderRegistry().get(MODELO)
    dimensao = await embedder.get_dimension()
    arquivos = carregar_arquivos_a_ingerir(carregar_dataset()["_pastas"])
    print(f"{len(arquivos)} arquivos; modelo {MODELO} ({dimensao} dims)")

    async with session_factory() as session:
        if await get_collection_by_name(session, NOME):
            print(f"ERRO: a collection {NOME} já existe", file=sys.stderr)
            return 1
        collection = await create_collection(
            session,
            name=NOME,
            embedding_model=MODELO,
            vector_dimension=dimensao,
            distance_metric="cosine",
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            quantization_type="none",
            quantization_config={},
            payload_indexes=[],
            purpose="chat",
            is_active=False,
            **HNSW_PADRAO,
        )
        for caminho in arquivos:
            await ingest_file(
                qdrant,
                embedder,
                collection,
                Path(settings.rag_uploads_dir),
                caminho,
                domain=DOMINIO,
                session=session,
                origin=ORIGEM,
            )
        await activate_collection(session, collection.id)
    print(f"collection {NOME} criada e ativada")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
