# Gestão de Produtos no Admin, Ingestão de Catálogos (PDF/Imagens) e RAG Visual CLIP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar no Admin a gestão de produtos com `preco_base_fornecedor`, associação de imagens físicas e vetoriais (Qdrant CLIP `catalogo_imagens`), pipeline de extração inteligente de catálogos multipáginas (PDF e imagens) via streaming SSE com Human-in-the-Loop, e a interface frontend correspondente em `/admin/produtos`.

**Architecture:** A camada de dados estende `produtos` e cria `produto_imagens` no Postgres via Alembic; FastAPI serve imagens estáticas e expõe rotas CRUD e endpoints SSE de extração de catálogos; a extração página a página avalia texto nativo via `pdfplumber` + Ollama local e conta com fallback/alternância para visão multimodal via OpenRouter; as fotos são vetorizadas pelo `ClipEmbedder` na collection `catalogo_imagens` e vinculadas ao `produto_id`; o frontend Next.js 16 consome o backend em `/admin/produtos` com tabela responsiva e modal de importação com barra de progresso ao vivo.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2, Qdrant (CLIP ViT-B/32), pdfplumber, Pillow, Ollama (`gemma4:12b-it-q4_K_M`), OpenRouter Vision (`google/gemini-2.5-flash`), Next.js 16 (App Router), TypeScript, Tailwind CSS, Vitest / Pytest.

**Spec:** [`docs/superpowers/specs/2026-09-25-admin-produtos-catalogo-design.md`](file:///home/augusto/Projetos/TCC/docs/superpowers/specs/2026-09-25-admin-produtos-catalogo-design.md)

## Global Constraints

- Backend roda em Python 3.14 (`uv`, `backend/.venv`).
- Postgres roda na porta 5433 (`backend/docker-compose.yml`); Qdrant na porta 6335 (`AsyncQdrantClient(host="localhost", port=6335)` em dev, `AsyncQdrantClient(location=":memory:")` em testes unitários).
- Migração Alembic desta entrega: `revision = "0013"`, `down_revision = "0012"`.
- As novas colunas na tabela `produtos` devem ser opcionais (`nullable=True`) para preservar compatibilidade com as fixtures existentes (`0003_produtos_fixture.py`).
- Exclusão de produto deve aplicar cascata em `produto_imagens` e expurgar os pontos associados no Qdrant `catalogo_imagens`.
- A rota SSE `/api/admin/produtos/catalogo/extrair/stream` deve usar gerador assíncrono emitindo `event: progresso`, `event: pagina_concluida` e `event: done`.
- O diretório físico de imagens do produto é `./data/product_images` (e temporário `./data/product_images/temp`).

## Review Focus

1. **PDF com páginas sem texto (escaneadas/imagens puras):** `pdfplumber.extract_text()` retorna vazio ou string com menos de 50 caracteres; o pipeline deve ativar automaticamente o fallback para o modelo de visão externa sem quebrar a requisição.
2. **Exclusão de produto com imagens indexadas no CLIP:** a exclusão do produto deve remover as linhas em `produto_imagens` e chamar o Qdrant para deletar os IDs de ponto do CLIP, sem deixar vetores órfãos.
3. **Imagens temporárias não aprovadas pelo Admin:** imagens geradas no passo de extração em `data/product_images/temp/` só devem ser promovidas para a pasta definitiva se o produto estiver com `selecionado: true` na confirmação.
4. **Formato inválido de imagem no upload:** envio de arquivos não suportados (ex.: `.txt` ou `.bmp`) deve retornar 400 Bad Request detalhado.
5. **Busca multimodal no Chat:** envio de imagem no chat deve encontrar o ponto no CLIP e resolver diretamente o `produto_id` no payload sem ambiguidades.

---

### Task 1: Modelo de Dados e Migração Alembic (`produtos` e `produto_imagens`)

**Files:**
- Create: `backend/migrations/versions/0013_produto_preco_fornecedor_imagem.py`
- Modify: `backend/src/app/db/models.py`
- Modify: `backend/src/app/models/catalog.py`
- Modify: `backend/src/app/db/catalog.py`
- Create/Modify: `backend/tests/test_catalog_db.py`

**Interfaces:**
- Produces: `Produto.preco_base_fornecedor: Decimal | None`, `Produto.imagem_url: str | None`, `Produto.imagens: list[ProdutoImagem]` em `app.db.models`.
- Produces: `ProdutoImagem(id, produto_id, imagem_url, clip_image_id, is_principal, criado_em)` em `app.db.models`.
- Produces: `ProdutoImagemOut`, `ProdutoOut(..., preco_base_fornecedor, imagem_url, imagens)` em `app.models.catalog`.
- Produces: `criar_produto(..., preco_base_fornecedor=None, imagem_url=None)` em `app.db.catalog`.

- [ ] **Step 1: Escrever teste de falha para os novos campos e tabela `produto_imagens`**

Em `backend/tests/test_catalog_db.py`, adicionar:
```python
import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.catalog import criar_produto, obter_produto, deletar_produto
from app.db.models import ProdutoImagem

@pytest.mark.asyncio
async def test_criar_produto_com_preco_fornecedor_e_imagem(session: AsyncSession):
    produto = await criar_produto(
        session,
        nome="Câmera IP Teste",
        descricao="Câmera para testes",
        preco=Decimal("299.90"),
        categoria="CFTV",
        preco_base_fornecedor=Decimal("180.00"),
        imagem_url="/api/uploads/produtos/camera.png",
    )
    assert produto.id is not None
    assert produto.preco_base_fornecedor == Decimal("180.00")
    assert produto.imagem_url == "/api/uploads/produtos/camera.png"

    # Adiciona imagem filha em produto_imagens
    img = ProdutoImagem(
        produto_id=produto.id,
        imagem_url="/api/uploads/produtos/camera.png",
        clip_image_id="clip-uuid-123",
        is_principal=True,
    )
    session.add(img)
    await session.commit()

    consultado = await obter_produto(session, produto.id)
    assert consultado is not None
    assert len(consultado.imagens) == 1
    assert consultado.imagens[0].clip_image_id == "clip-uuid-123"

    # Deletar produto deve deletar imagens em cascata
    deleted = await deletar_produto(session, produto.id)
    assert deleted is True
    assert await obter_produto(session, produto.id) is None
```

- [ ] **Step 2: Rodar teste para confirmar a falha**

Run: `cd backend && .venv/bin/pytest tests/test_catalog_db.py::test_criar_produto_com_preco_fornecedor_e_imagem -v`
Expected: FAIL com `TypeError` ou `AttributeError` (campos e relacionamento ainda não existem).

- [ ] **Step 3: Atualizar `app.db.models`, `app.models.catalog` e `app.db.catalog`**

Em `backend/src/app/db/models.py`:
- Adicionar colunas `preco_base_fornecedor` e `imagem_url` na classe `Produto`.
- Adicionar relationship `imagens: Mapped[list["ProdutoImagem"]] = relationship(back_populates="produto", cascade="all, delete-orphan", lazy="selectin")`.
- Criar a classe `ProdutoImagem(Base)`.

Em `backend/src/app/models/catalog.py`:
- Criar `ProdutoImagemOut(BaseModel)`.
- Atualizar `ProdutoOut`, `ProdutoCreate` e `ProdutoUpdate` com `preco_base_fornecedor` e `imagem_url`.

Em `backend/src/app/db/catalog.py`:
- Atualizar assinatura e corpo de `criar_produto` para receber e atribuir `preco_base_fornecedor` e `imagem_url`.
- Em `_produto_query()`, adicionar `selectinload(Produto.imagens)`.
- Em `deletar_produto()`, garantir a remoção de `ProdutoImagem` via `delete(ProdutoImagem).where(ProdutoImagem.produto_id == produto_id)` antes de apagar o produto.

- [ ] **Step 4: Criar arquivo de migração Alembic `0013_produto_preco_fornecedor_imagem.py`**

Em `backend/migrations/versions/0013_produto_preco_fornecedor_imagem.py`:
- `revision = "0013"`
- `down_revision = "0012"`
- Implementar `upgrade()` adicionando colunas em `produtos` e criando a tabela `produto_imagens`.
- Implementar `downgrade()` revertendo a tabela e as colunas.

- [ ] **Step 5: Rodar testes e migração**

Run: `cd backend && .venv/bin/pytest tests/test_catalog_db.py -v`
Expected: PASS.
Run: `cd backend && .venv/bin/alembic upgrade head`
Expected: Migração aplicada com sucesso.

- [ ] **Step 6: Commit**

```bash
git add backend/migrations/versions/0013_produto_preco_fornecedor_imagem.py backend/src/app/db/models.py backend/src/app/models/catalog.py backend/src/app/db/catalog.py backend/tests/test_catalog_db.py
git commit -m "feat(catalog): adiciona preco_base_fornecedor e tabela produto_imagens (0013)"
```

---

### Task 2: Armazenamento Físico de Imagens e Servimento Estático

**Files:**
- Modify: `backend/src/app/config.py`
- Create: `backend/src/app/api/uploads.py`
- Modify: `backend/src/app/main.py`
- Create: `backend/tests/test_uploads_api.py`

**Interfaces:**
- Produces: `Settings.product_images_dir: str = "./data/product_images"` em `app.config`.
- Produces: `GET /api/uploads/produtos/{filename}` retornando o arquivo com MIME correto ou 404.
- Produces: `salvar_imagem_produto(content: bytes, filename: str, is_temp: bool = False) -> tuple[str, Path]` helper de upload seguro.

- [ ] **Step 1: Escrever teste de falha para upload e servimento estático**

Em `backend/tests/test_uploads_api.py`:
```python
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import create_app

@pytest.mark.asyncio
async def test_servimento_imagem_produto_inexistente_retorna_404():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/uploads/produtos/nao_existe.png")
        assert resp.status_code == 404

@pytest.mark.asyncio
async def test_servimento_imagem_produto_existente(tmp_path, monkeypatch):
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "product_images_dir", str(tmp_path))

    # Cria imagem fake
    img_file = tmp_path / "teste.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\nfakecontent")

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/uploads/produtos/teste.png")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content == b"\x89PNG\r\n\x1a\nfakecontent"
```

- [ ] **Step 2: Rodar teste para confirmar a falha**

Run: `cd backend && .venv/bin/pytest tests/test_uploads_api.py -v`
Expected: FAIL com 404 (rota não configurada).

- [ ] **Step 3: Implementar `Settings.product_images_dir` e rota `app/api/uploads.py`**

Em `backend/src/app/config.py`:
- Adicionar `product_images_dir: str = "./data/product_images"`.

Em `backend/src/app/api/uploads.py`:
- Implementar `GET /api/uploads/produtos/{filename}` e `GET /api/uploads/produtos/temp/{filename}` via `FileResponse`.
- Adicionar verificação contra path traversal (`..` no filename).

Em `backend/src/app/main.py`:
- Garantir `Path(settings.product_images_dir).mkdir(parents=True, exist_ok=True)` e `(Path(settings.product_images_dir) / "temp").mkdir(parents=True, exist_ok=True)`.
- Incluir `app.include_router(uploads_router)`.

- [ ] **Step 4: Rodar teste para confirmar sucesso**

Run: `cd backend && .venv/bin/pytest tests/test_uploads_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/config.py backend/src/app/api/uploads.py backend/src/app/main.py backend/tests/test_uploads_api.py
git commit -m "feat(api): adiciona rota de servimento de imagens de produtos e config de diretorios"
```

---

### Task 3: Catálogo Visual CLIP (Associação Produto-Imagem no Qdrant)

**Files:**
- Modify: `backend/src/app/rag/image_search.py`
- Modify: `backend/src/app/rag/image_identification.py`
- Create: `backend/tests/test_admin_products_clip.py`

**Interfaces:**
- Modifies: `ClipImageStore.upsert_image(embedder, image_bytes, filename, domain, produto_id=None, imagem_url=None) -> str`.
- Modifies: `ClipImageStore.delete_image(image_id: str) -> bool`.
- Modifies: `ImageSearchResult` adicionando `produto_id: int | None = None` e `imagem_url: str | None = None`.

- [ ] **Step 1: Escrever teste de falha para upsert com produto_id e delete de imagem no CLIP**

Em `backend/tests/test_admin_products_clip.py`:
```python
import pytest
from unittest.mock import AsyncMock
from qdrant_client import AsyncQdrantClient
from app.rag.image_search import ClipImageStore

@pytest.mark.asyncio
async def test_clip_image_store_upsert_e_delete_com_produto_id():
    client = AsyncQdrantClient(location=":memory:")
    store = ClipImageStore(client)

    embedder = AsyncMock()
    embedder.embed_images = AsyncMock(return_value=[[0.1] * 512])

    image_id = await store.upsert_image(
        embedder=embedder,
        image_bytes=b"fake-bytes",
        filename="Camera VIP",
        domain="vendas",
        produto_id=42,
        imagem_url="/api/uploads/produtos/cam.png",
    )
    assert image_id is not None

    # Busca confirma payload enriquecido
    results = await store.search_by_image(embedder, b"fake-bytes", domain="vendas")
    assert len(results) >= 1
    assert results[0].produto_id == 42
    assert results[0].imagem_url == "/api/uploads/produtos/cam.png"

    # Exclui imagem
    deleted = await store.delete_image(image_id)
    assert deleted is True

    # Busca após delete retorna vazio
    after_delete = await store.search_by_image(embedder, b"fake-bytes", domain="vendas")
    assert len(after_delete) == 0
```

- [ ] **Step 2: Rodar teste para verificar falha**

Run: `cd backend && .venv/bin/pytest tests/test_admin_products_clip.py -v`
Expected: FAIL com `TypeError` ou `AttributeError` (`delete_image` não existe e `produto_id` não aceito).

- [ ] **Step 3: Implementar suporte em `ClipImageStore` e `ImageIdentificationResult`**

Em `backend/src/app/rag/image_search.py`:
- Adicionar `produto_id: int | None = None` e `imagem_url: str | None = None` em `ImageSearchResult`.
- Em `upsert_image`, enriquecer o payload do `PointStruct` com `produto_id` e `imagem_url`.
- Implementar `async def delete_image(self, image_id: str) -> bool`.
- Em `_search()`, mapear `produto_id` e `imagem_url` do payload para `ImageSearchResult`.

Em `backend/src/app/rag/image_identification.py`:
- Adicionar `produto_id: int | None = None` em `ImageIdentificationResult`.
- Mapear `produto_id=melhor.produto_id` quando encontrado internamente no CLIP.

- [ ] **Step 4: Rodar teste para verificar sucesso**

Run: `cd backend && .venv/bin/pytest tests/test_admin_products_clip.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/rag/image_search.py backend/src/app/rag/image_identification.py backend/tests/test_admin_products_clip.py
git commit -m "feat(rag): enriquece payload do CLIP com produto_id e adiciona delete_image"
```

---

### Task 4: Endpoints da API Administrativa de Produtos (CRUD e Imagens)

**Files:**
- Create: `backend/src/app/api/admin_products.py`
- Modify: `backend/src/app/main.py`
- Create: `backend/tests/test_admin_products_api.py`

**Interfaces:**
- Produces: `GET /api/admin/produtos` (suporta `termo`, `categoria`, `limit`, `offset`).
- Produces: `GET /api/admin/produtos/{id}`.
- Produces: `POST /api/admin/produtos` (suporta `application/json` ou `multipart/form-data` com upload de imagem).
- Produces: `PUT /api/admin/produtos/{id}`.
- Produces: `DELETE /api/admin/produtos/{id}`.
- Produces: `POST /api/admin/produtos/{id}/imagens`.
- Produces: `DELETE /api/admin/produtos/{id}/imagens/{img_id}`.

- [ ] **Step 1: Escrever testes da API administrativa de produtos**

Em `backend/tests/test_admin_products_api.py`:
```python
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import create_app

@pytest.mark.asyncio
async def test_crud_admin_produtos():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Cria produto manual
        resp = await client.post(
            "/api/admin/produtos",
            json={
                "nome": "Câmera Dome VIP 3200",
                "descricao": "Câmera Dome IP",
                "preco": "350.00",
                "categoria": "CFTV",
                "preco_base_fornecedor": "220.00",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        prod_id = data["id"]
        assert data["nome"] == "Câmera Dome VIP 3200"
        assert float(data["preco_base_fornecedor"]) == 220.0

        # 2. Lista produtos
        list_resp = await client.get("/api/admin/produtos?termo=Dome")
        assert list_resp.status_code == 200
        assert any(p["id"] == prod_id for p in list_resp.json()["items"])

        # 3. Atualiza produto
        put_resp = await client.put(f"/api/admin/produtos/{prod_id}", json={"preco": "399.00"})
        assert put_resp.status_code == 200
        assert float(put_resp.json()["preco"]) == 399.0

        # 4. Exclui produto
        del_resp = await client.delete(f"/api/admin/produtos/{prod_id}")
        assert del_resp.status_code == 204

        # 5. Confirma 404
        get_resp = await client.get(f"/api/admin/produtos/{prod_id}")
        assert get_resp.status_code == 404
```

- [ ] **Step 2: Rodar teste para verificar falha**

Run: `cd backend && .venv/bin/pytest tests/test_admin_products_api.py -v`
Expected: FAIL com 404 (endpoints ainda não existem).

- [ ] **Step 3: Implementar `app/api/admin_products.py` e plugar no `main.py`**

Em `backend/src/app/api/admin_products.py`:
- Implementar router com prefixo `/api/admin/produtos`.
- Métodos CRUD usando `app.db.catalog` (`listar_produtos`, `obter_produto`, `criar_produto`, `atualizar_produto`, `deletar_produto`).
- Se upload de imagem for fornecido: salvar em `data/product_images/`, chamar `clip_image_store.upsert_image` e persistir em `produto_imagens`.
- Ao excluir produto ou imagem: chamar `clip_image_store.delete_image`.

Em `backend/src/app/main.py`:
- `app.include_router(admin_products_router)`.

- [ ] **Step 4: Rodar teste para verificar sucesso**

Run: `cd backend && .venv/bin/pytest tests/test_admin_products_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/api/admin_products.py backend/src/app/main.py backend/tests/test_admin_products_api.py
git commit -m "feat(api): adiciona rotas administrativas de gestao de produtos e imagens"
```

---

### Task 5: Pipeline de Extração Híbrida de Catálogos (PDF multipáginas e seleção de imagens com SSE)

**Files:**
- Create: `backend/src/app/catalog_extractor/extractor.py`
- Create: `backend/src/app/models/catalog_extractor.py`
- Modify: `backend/src/app/api/admin_products.py`
- Create: `backend/tests/test_catalog_extractor.py`

**Interfaces:**
- Produces: `CatalogPageItem`, `CatalogExtractionResult`, `CatalogConfirmRequest` em `app.models.catalog_extractor`.
- Produces: `async def extract_catalog_stream(files, provider, fallback_external, temp_dir, local_client, vision_client) -> AsyncGenerator[str, None]` em `app.catalog_extractor.extractor`.
- Produces: `POST /api/admin/produtos/catalogo/extrair/stream` (SSE).
- Produces: `POST /api/admin/produtos/catalogo/confirmar`.

- [ ] **Step 1: Escrever teste de falha do extrator de catálogo com mock de LLM e PDF**

Em `backend/tests/test_catalog_extractor.py`:
```python
import pytest
from unittest.mock import AsyncMock
from app.catalog_extractor.extractor import extract_page_products_local

@pytest.mark.asyncio
async def test_extract_page_products_local_retorna_produtos():
    local_client = AsyncMock()
    local_client.generate = AsyncMock(
        return_value=AsyncMock(
            response='[{"nome": "Gravador NVD 1016", "descricao": "Gravador IP 16 canais", "categoria": "CFTV", "preco_base_fornecedor": 550.0, "preco": 799.0, "especificacoes_tecnicas": "16 canais PoE"}]'
        )
    )

    texto_pagina = "Intelbras Gravador NVD 1016 16 canais PoE CFTV Preco R$ 550,00"
    produtos = await extract_page_products_local(texto_pagina, local_client)
    assert len(produtos) == 1
    assert produtos[0]["nome"] == "Gravador NVD 1016"
    assert produtos[0]["preco_base_fornecedor"] == 550.0
```

- [ ] **Step 2: Rodar teste para verificar falha**

Run: `cd backend && .venv/bin/pytest tests/test_catalog_extractor.py -v`
Expected: FAIL com `ModuleNotFoundError`.

- [ ] **Step 3: Implementar schemas e lógica de extração híbrida**

Em `backend/src/app/models/catalog_extractor.py`:
- Modelos Pydantic para os produtos extraídos e requisição de confirmação.

Em `backend/src/app/catalog_extractor/extractor.py`:
- `extract_page_products_local`: envia texto ao Ollama com prompt estrito de JSON.
- `extract_page_products_vision`: envia imagem da página ao OpenRouter multimodal com prompt estrito de JSON.
- `extract_catalog_stream`: itera sobre as páginas do PDF (`pdfplumber`) ou lista de imagens de entrada, renderiza imagem para recorte/preview em `data/product_images/temp/`, tenta local e recorre à visão externa se o texto for curto ou se `provider == "external"`. Emite eventos SSE.

Em `backend/src/app/api/admin_products.py`:
- Adicionar rota `POST /api/admin/produtos/catalogo/extrair/stream` retornando `StreamingResponse(..., media_type="text/event-stream")`.
- Adicionar rota `POST /api/admin/produtos/catalogo/confirmar`: salva produtos selecionados no banco, move fotos de `temp/` para `data/product_images/` e indexa no CLIP.

- [ ] **Step 4: Rodar teste para verificar sucesso**

Run: `cd backend && .venv/bin/pytest tests/test_catalog_extractor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/catalog_extractor/ backend/src/app/models/catalog_extractor.py backend/src/app/api/admin_products.py backend/tests/test_catalog_extractor.py
git commit -m "feat(catalog): adiciona pipeline de extracao hibrida de catalogos e confirmacao em lote"
```

---

### Task 6: Frontend — Cliente de API e Hooks

**Files:**
- Create: `frontend/lib/api/adminProducts.ts`
- Create: `frontend/lib/types/adminProducts.ts`
- Create: `frontend/tests/unit/adminProductsApi.test.ts`

**Interfaces:**
- Produces: `fetchAdminProducts(params)`, `createAdminProduct(data)`, `updateAdminProduct(id, data)`, `deleteAdminProduct(id)` em `frontend/lib/api/adminProducts.ts`.
- Produces: `extractCatalogStream(files, options, callbacks)` para consumir o SSE de extração página a página.
- Produces: `confirmCatalogExtraction(payload)` para envio do lote aprovado.

- [ ] **Step 1: Escrever teste de unidade do cliente frontend**

Em `frontend/tests/unit/adminProductsApi.test.ts`:
```typescript
import { describe, it, expect, vi } from "vitest";
import { fetchAdminProducts } from "@/lib/api/adminProducts";

describe("adminProducts API client", () => {
  it("monta query string com filtros e retorna lista de produtos", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [{ id: 1, nome: "Câmera" }], total: 1 }),
    });
    vi.stubGlobal("fetch", mockFetch);

    const result = await fetchAdminProducts({ termo: "Câmera", categoria: "CFTV" });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/admin/produtos?termo=C%C3%A2mera&categoria=CFTV"),
      expect.any(Object)
    );
    expect(result.items).toHaveLength(1);
    vi.unstubAllGlobals();
  });
});
```

- [ ] **Step 2: Rodar teste para verificar falha**

Run: `cd frontend && npm test tests/unit/adminProductsApi.test.ts`
Expected: FAIL com módulo não encontrado.

- [ ] **Step 3: Implementar tipos e funções da API no frontend**

Em `frontend/lib/types/adminProducts.ts`:
- Definir interfaces `AdminProduct`, `AdminProductImage`, `ExtractedProductItem`, `CatalogExtractionProgress`.

Em `frontend/lib/api/adminProducts.ts`:
- Implementar funções usando `getApiBaseUrl()` (garantindo compatibilidade com LAN/DuckDNS).
- Implementar `extractCatalogStream` usando `response.body.getReader()` para decodificar blocos `event:`/`data:` SSE.

- [ ] **Step 4: Rodar teste para verificar sucesso**

Run: `cd frontend && npm test tests/unit/adminProductsApi.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/types/adminProducts.ts frontend/lib/api/adminProducts.ts frontend/tests/unit/adminProductsApi.test.ts
git commit -m "feat(frontend): adiciona cliente de API e tipos para produtos e extracao de catalogos"
```

---

### Task 7: Frontend — Página Administrativa de Produtos e Modal de Importação

**Files:**
- Modify: `frontend/components/layout/AdminGearMenu.tsx`
- Create: `frontend/components/admin/products/ProductListTable.tsx`
- Create: `frontend/components/admin/products/ProductFormModal.tsx`
- Create: `frontend/components/admin/products/CatalogImportModal.tsx`
- Create: `frontend/app/admin/produtos/page.tsx`

**Interfaces:**
- Produces: Rota acessível em `/admin/produtos`.
- Produces: Item "Catálogo de Produtos" com ícone de caixa 📦 no `AdminGearMenu`.
- Produces: Interface de conferência Human-in-the-Loop no modal de importação com inputs editáveis e checkboxes de seleção.

- [ ] **Step 1: Adicionar o link no `AdminGearMenu.tsx`**

Em `frontend/components/layout/AdminGearMenu.tsx`:
- Adicionar `<Link href="/admin/produtos">` com título "Catálogo de Produtos" e ícone 📦.

- [ ] **Step 2: Criar componentes da listagem de produtos**

Em `frontend/components/admin/products/ProductListTable.tsx`:
- Renderizar tabela com miniatura da imagem (com indicador de CLIP), Nome, Categoria, Preço Fornecedor, Preço Venda, Margem calculada `((preco - preco_fornecedor) / preco_fornecedor * 100)%` e ações de Editar/Excluir.

Em `frontend/components/admin/products/ProductFormModal.tsx`:
- Modal para cadastro e edição manual de produto com upload e preview de foto.

- [ ] **Step 3: Criar o modal de importação inteligente `CatalogImportModal.tsx`**

Em `frontend/components/admin/products/CatalogImportModal.tsx`:
- Passo 1: Seleção de PDF multipáginas ou imagens + seletor de IA (Local vs OpenRouter).
- Passo 2: Barra de progresso SSE ao vivo ("Lendo página 3/10... 6 produtos encontrados").
- Passo 3: Tabela Human-in-the-Loop de conferência com checkboxes, inputs editáveis, botão para trocar imagem e botão "Confirmar e Salvar no Catálogo & CLIP".

- [ ] **Step 4: Criar a página principal `/admin/produtos/page.tsx`**

Em `frontend/app/admin/produtos/page.tsx`:
- Integrar barra de busca, filtro por categoria, botões de ação ("+ Novo Produto" e "📥 Importar Catálogo") e a tabela de produtos com estado dinâmico.

- [ ] **Step 5: Testar build do frontend**

Run: `cd frontend && npm run build`
Expected: Build bem-sucedido sem erros de tipagem TypeScript.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/layout/AdminGearMenu.tsx frontend/components/admin/products/ frontend/app/admin/produtos/page.tsx
git commit -m "feat(frontend): implementa tela de gestao de produtos e modal de importacao de catalogos"
```

---

### Task 8: Verificação Ponta a Ponta e Atualização Documental

**Files:**
- Modify: `docs/ROADMAP.md`
- Modify: `docs/FRONTEND.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `resumo.md`

- [ ] **Step 1: Executar suite de testes completa do backend e frontend**

Run: `cd backend && .venv/bin/pytest -v`
Expected: Todos os testes passando (100%).
Run: `cd frontend && npm test`
Expected: Todos os testes passando (100%).

- [ ] **Step 2: Atualizar documentação do projeto**

- Registrar a nova funcionalidade em `docs/ROADMAP.md`, `docs/ARCHITECTURE.md` e `resumo.md`.

- [ ] **Step 3: Commit final e push**

```bash
git add docs/ROADMAP.md docs/FRONTEND.md docs/ARCHITECTURE.md resumo.md
git commit -m "docs: atualiza documentacao do projeto com a entrega da gestao de produtos e catalogos"
git push origin master
```
