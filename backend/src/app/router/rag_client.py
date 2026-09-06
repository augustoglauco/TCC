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
    # MVP: stub sem implementação real — RAG de verdade (Qdrant) entra na
    # Fase 2 (ver docs/ROADMAP.md), sem alterar o orchestrator.
    async def search(self, query: str, domain: str) -> list[Document]:
        return []
