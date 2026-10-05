# Download de Documentos RAG de Origem Direta no Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement direct document download capability in the chat via rich UI cards when RAG search matches documents above a confidence threshold.

**Architecture:** Extend FastAPI RAG API with a secure file download endpoint (`GET /api/rag/documents/{id}/download`), update `ChatCard` union with `CardDocumentoDownload`, add score threshold detection (`rag_download_confidence_threshold` default `0.65`) in the Orchestrator, and render interactive download cards in the Next.js chat widget (`DocumentDownloadCard.tsx`).

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, AsyncPG / PostgreSQL, Pydantic v2, Next.js 14 (App Router, TypeScript, Tailwind CSS, Lucide icons, Vitest, pytest).

**Spec:** [`docs/superpowers/specs/2026-10-04-download-documentos-rag-chat-design.md`](docs/superpowers/specs/2026-10-04-download-documentos-rag-chat-design.md)

## Global Constraints

- Python backend: strict type annotations, async SQLAlchemy sessions, Pydantic v2 schemas.
- File security: validate file paths against directory traversal (`storage_path`), require admin auth token for documents from `purpose="admin"` collections.
- Frontend: Next.js App Router, Tailwind CSS, standard TypeScript interfaces.
- Testing: All backend logic covered by `pytest`, all frontend components covered by `vitest`.

## Review Focus

- Non-existent or deleted file on disk: return clean HTTP 404 with detailed JSON error message instead of 500 crash.
- Security access control: documents belonging to `purpose="admin"` collections must refuse unauthenticated requests with HTTP 401/403.
- Content-Disposition header: download response must include explicit `attachment; filename="{filename}"` header for clean browser download behavior.
- RAG threshold boundary: chunks with scores below 0.65 must not emit a download card to avoid irrelevant file attachments.

---

### Task 1: Secure RAG Document Download Endpoint (`GET /api/rag/documents/{id}/download`)

**Files:**
- Modify: `backend/src/app/api/rag.py`
- Test: `backend/tests/test_rag_document_download_api.py`

**Interfaces:**
- Consumes: `RagDocument` and `RagCollection` models from `app.db.models`.
- Produces: `GET /api/rag/documents/{id}/download` HTTP endpoint returning `FileResponse`.

- [ ] **Step 1: Write failing test for document download endpoint**

```python
import pytest
import uuid
from httpx import AsyncClient
from app.db.models import RagDocument, RagCollection

@pytest.mark.asyncio
async def test_download_rag_document_success(async_client: AsyncClient, db_session, tmp_path):
    # Setup mock file
    test_file = tmp_path / "manual_teste.pdf"
    test_file.write_bytes(b"%PDF-1.4 mock content")

    col = RagCollection(id=uuid.uuid4(), name="test_col", purpose="chat", embedding_model="m", vector_dimension=384, distance_metric="cosine", chunk_size=500, chunk_overlap=50, hnsw_m=16, hnsw_ef_construct=100, hnsw_full_scan_threshold=10000, hnsw_max_indexing_threads=0, hnsw_on_disk=False, quantization_type="none")
    doc = RagDocument(id=uuid.uuid4(), collection_id=col.id, filename="manual_teste.pdf", domain="suporte", chunk_count=5, storage_path=str(test_file), origin="upload")
    db_session.add_all([col, doc])
    await db_session.commit()

    response = await async_client.get(f"/api/rag/documents/{doc.id}/download")
    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="manual_teste.pdf"'
    assert response.content == b"%PDF-1.4 mock content"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=backend/src backend/.venv/bin/pytest backend/tests/test_rag_document_download_api.py -v`
Expected: FAIL 404 Not Found.

- [ ] **Step 3: Implement endpoint in `app/api/rag.py`**

```python
from fastapi.responses import FileResponse
from app.api.auth import verificar_admin_por_token

@router.get("/documents/{document_id}/download")
async def download_rag_document(
    document_id: uuid.UUID,
    auth_token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    doc_res = await db.execute(select(RagDocument).where(RagDocument.id == document_id))
    doc = doc_res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    col_res = await db.execute(select(RagCollection).where(RagCollection.id == doc.collection_id))
    col = col_res.scalar_one_or_none()
    if col and col.purpose == "admin":
        if not auth_token or not verificar_admin_por_token(auth_token):
            raise HTTPException(status_code=403, detail="Acesso restrito a administradores.")

    if not doc.storage_path or not os.path.exists(doc.storage_path):
        raise HTTPException(status_code=404, detail="Arquivo físico do documento não encontrado no servidor.")

    return FileResponse(
        path=doc.storage_path,
        filename=doc.filename,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{doc.filename}"'}
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=backend/src backend/.venv/bin/pytest backend/tests/test_rag_document_download_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/api/rag.py backend/tests/test_rag_document_download_api.py
git commit -m "feat(rag): add secure GET /api/rag/documents/{id}/download endpoint"
```

---

### Task 2: `CardDocumentoDownload` Pydantic Schema & Orchestrator Detection

**Files:**
- Modify: `backend/src/app/models/chat.py`
- Modify: `backend/src/app/router/orchestrator.py`
- Test: `backend/tests/test_orchestrator_document_download_card.py`

**Interfaces:**
- Consumes: `RagDocument` and `RagCollection` DB models, RAG search results.
- Produces: `CardDocumentoDownload` rich card in SSE `done` event.

- [ ] **Step 1: Write failing test for Orchestrator document card emission**

```python
import pytest
from app.models.chat import CardDocumentoDownload

def test_card_documento_download_schema():
    card = CardDocumentoDownload(
        documento_id="123e4567-e89b-12d3-a456-426614174000",
        filename="Manual_GD30.pdf",
        domain="suporte",
        score=0.88,
        download_url="/api/rag/documents/123e4567-e89b-12d3-a456-426614174000/download",
        file_size_bytes=2450000
    )
    assert card.tipo == "documento_download"
    assert card.filename == "Manual_GD30.pdf"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=backend/src backend/.venv/bin/pytest backend/tests/test_orchestrator_document_download_card.py -v`
Expected: FAIL with ImportError "CardDocumentoDownload not found".

- [ ] **Step 3: Update `chat.py` schema and `orchestrator.py` logic**

In `backend/src/app/models/chat.py`:
Add `CardDocumentoDownload` model and include it in `ChatCard` union discriminator.

In `backend/src/app/router/orchestrator.py`:
In `handle_message`, after RAG retrieval:
If `melhor_chunk` has `score >= 0.65`, look up corresponding `RagDocument` from `db_sessionmaker`. If valid, create `CardDocumentoDownload` and attach to `RouterDecision` card.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=backend/src backend/.venv/bin/pytest backend/tests/test_orchestrator_document_download_card.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/models/chat.py backend/src/app/router/orchestrator.py backend/tests/test_orchestrator_document_download_card.py
git commit -m "feat(orchestrator): emit CardDocumentoDownload when RAG match score >= 0.65"
```

---

### Task 3: Frontend `DocumentDownloadCard.tsx` & Message Bubble Integration

**Files:**
- Create: `frontend/components/chat/DocumentDownloadCard.tsx`
- Modify: `frontend/components/chat/MessageBubble.tsx`
- Test: `frontend/tests/components/DocumentDownloadCard.test.tsx`

**Interfaces:**
- Consumes: `CardDocumentoDownload` payload from SSE `done` event.
- Produces: Interactive document download card in the chat UI.

- [ ] **Step 1: Write failing test for DocumentDownloadCard UI**

```tsx
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { DocumentDownloadCard } from '@/components/chat/DocumentDownloadCard'

describe('DocumentDownloadCard', () => {
  it('renders document metadata and download link correctly', () => {
    render(
      <DocumentDownloadCard
        card={{
          tipo: 'documento_download',
          documento_id: 'doc-123',
          filename: 'Manual_GD30.pdf',
          domain: 'suporte',
          score: 0.88,
          download_url: '/api/rag/documents/doc-123/download',
          file_size_bytes: 2450000,
        }}
      />
    )
    expect(screen.getByText('Manual_GD30.pdf')).toBeDefined()
    expect(screen.getByText('Relevância: 88%')).toBeDefined()
    expect(screen.getByRole('link', { name: /baixar documento/i })).toBeDefined()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend test frontend/tests/components/DocumentDownloadCard.test.tsx`
Expected: FAIL missing component.

- [ ] **Step 3: Implement `DocumentDownloadCard.tsx` & integrate in `MessageBubble.tsx`**

Create `frontend/components/chat/DocumentDownloadCard.tsx`:
Render card with PDF/file icon, formatted file size, relevance percentage badge, and `<a>` download button.
Update `MessageBubble.tsx` to handle `card.tipo === "documento_download"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend test frontend/tests/components/DocumentDownloadCard.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/components/chat/DocumentDownloadCard.tsx frontend/components/chat/MessageBubble.tsx frontend/tests/components/DocumentDownloadCard.test.tsx
git commit -m "feat(frontend): create DocumentDownloadCard component for interactive RAG file downloads"
```
