from typing import Protocol

from pydantic import BaseModel


class Document(BaseModel):
    content: str
    source: str
    score: float


class RAGConnectionError(Exception):
    """Erro de infraestrutura na busca (ex.: Qdrant fora do ar).

    Distinto de uma busca que rodou normalmente e não achou nada relevante
    — essa distinção importa para o orchestrator (ver spec §2.4): busca
    vazia é sinal de negócio válido para escalar ao externo, erro de
    infraestrutura não é.
    """


class RAGClient(Protocol):
    async def search(self, query: str, domain: str) -> list[Document]: ...


class NullRAGClient:
    """Stub que sempre devolve lista vazia — sem RAG de verdade.

    A implementação real (`app.rag.qdrant_client.QdrantRAGClient`) foi
    implementada na Fase 2 (ver docs/ROADMAP.md) e é o que `app.main` usa em
    produção/dev. `NullRAGClient` segue existindo como stub simples para
    testes e para cenários em que não se quer depender do Qdrant.
    """

    async def search(self, query: str, domain: str) -> list[Document]:
        return []
