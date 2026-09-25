# Design — Gestão de Produtos no Admin, Ingestão de Catálogos (PDF/Imagens) e RAG Visual CLIP

> Spec resultante de sessão de brainstorm arquitetural com o desenvolvedor em 2026-09-25.
> Cobre:
> 1. Extensão do modelo de dados (`produtos` com `preco_base_fornecedor` e `imagem_url`).
> 2. Associação explícita produto-imagem no Postgres (`produto_imagens`) e no catálogo vetorial visual CLIP (`catalogo_imagens`).
> 3. Pipeline de extração recorrente de catálogos em PDF multipáginas e coleções de imagens (híbrido local + visão externa realtime) com validação Human-in-the-Loop.
> 4. Nova interface administrativa no frontend em `/admin/produtos`.

---

## 1. Objetivo e Motivação

Atualmente, o banco de dados possui o catálogo de produtos (`produtos`, `app.db.catalog`), mas:
- Falta rastreabilidade de custo de aquisição (`preco_base_fornecedor`) para cálculo de margem e precificação.
- Falta associação direta entre os produtos do catálogo e suas imagens fotográficas no banco e no catálogo visual CLIP (`catalogo_imagens`), o que limita a capacidade de o cliente enviar uma foto de um produto no chat e o assistente identificá-lo de imediato com preço e estoque.
- O cadastro de produtos em volume (catálogos de fabricantes como Intelbras/Control ID com dezenas de páginas) é inviável manualmente.

Esta entrega unifica a gestão cadastral, o pipeline de ingestão visual multimodal e a extração automática orientada por IA em uma experiência administrativa fluida.

---

## 2. Modelo de Dados & Migração Alembic

### 2.1 Migração `0013_produto_preco_fornecedor_imagem.py`
A migração estende a tabela `produtos` e introduz a tabela `produto_imagens`:

```python
# Tabela produtos (alteração)
sa.Column("preco_base_fornecedor", sa.Numeric(10, 2), nullable=True)
sa.Column("imagem_url", sa.String(500), nullable=True)

# Tabela produto_imagens (nova)
sa.Table(
    "produto_imagens",
    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id", ondelete="CASCADE"), nullable=False),
    sa.Column("imagem_url", sa.String(500), nullable=False),
    sa.Column("clip_image_id", sa.String(64), nullable=True),
    sa.Column("is_principal", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)
```

### 2.2 Modelos SQLAlchemy (`backend/src/app/db/models.py`)
```python
class Produto(Base):
    __tablename__ = "produtos"

    # ... campos existentes (id, nome, descricao, preco, categoria, etc.) ...
    preco_base_fornecedor: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    imagem_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    imagens: Mapped[list["ProdutoImagem"]] = relationship(
        back_populates="produto", cascade="all, delete-orphan", lazy="selectin"
    )


class ProdutoImagem(Base):
    __tablename__ = "produto_imagens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    produto_id: Mapped[int] = mapped_column(
        ForeignKey("produtos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    imagem_url: Mapped[str] = mapped_column(String(500), nullable=False)
    clip_image_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_principal: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    produto: Mapped["Produto"] = relationship(back_populates="imagens")
```

### 2.3 Schemas Pydantic (`backend/src/app/models/catalog.py`)
- `ProdutoImagemOut`: `id`, `imagem_url`, `clip_image_id`, `is_principal`, `criado_em`.
- `ProdutoOut`: inclui `preco_base_fornecedor: Decimal | None`, `imagem_url: str | None`, `imagens: list[ProdutoImagemOut] = []`.
- `ProdutoCreate`: aceita `preco_base_fornecedor: Decimal | None = None` e `imagem_url: str | None = None`.
- `ProdutoUpdate`: suporta atualização parcial de ambos os campos.

---

## 3. Armazenamento Físico e Servimento de Imagens

- **Diretório de upload:** configurável via `Settings.product_images_dir` (default: `./data/product_images`).
- **Diretório temporário de catálogos:** `./data/product_images/temp` (para recortes de páginas antes da aprovação).
- **Servimento HTTP:** o FastAPI monta rota estática ou endpoint de streaming de arquivos:
  `GET /api/uploads/produtos/{filename}` servindo com validação de tipos MIME (`image/png`, `image/jpeg`, `image/webp`).

---

## 4. Associação Produto-Imagem e Catálogo Visual CLIP

### 4.1 Ingestão Vetorial
Ao cadastrar ou atualizar a foto de um produto:
1. O backend salva a imagem em `./data/product_images/<uuid>.<ext>`.
2. Gera o vetor CLIP (512 dimensões, cosine) via `app.state.clip_embedder.embed_images([image_bytes])`.
3. Insere na collection `catalogo_imagens` do Qdrant com payload estruturado:
   ```json
   {
     "image_id": "<uuid>",
     "produto_id": 12,
     "produto_nome": "Câmera Bullet VIP 5200",
     "imagem_url": "/api/uploads/produtos/<uuid>.png",
     "filename": "Câmera Bullet VIP 5200",
     "domain": "vendas"
   }
   ```
4. Salva o `clip_image_id` correspondente na tabela `produto_imagens`.

### 4.2 Desassociação e Exclusão
Se uma imagem for removida ou o produto excluído:
- O backend consulta o `clip_image_id` e chama `clip_store.delete_image(clip_image_id)` (ou `qdrant_client.delete(...)`), mantendo o banco vetorial sempre limpo e sincronizado.

### 4.3 Integração com o Chat Multimodal
Em [`app.rag.image_identification.identify_product_by_image`](file:///home/augusto/Projetos/TCC/backend/src/app/rag/image_identification.py):
- Quando a busca no CLIP retornar um ponto com score >= `image_internal_confidence`, o payload fornece diretamente o `produto_id`. O orquestrador carrega o produto do banco via `SalesCatalogClient` e responde com estoque e preço exatos, sem ambiguidade.

---

## 5. Endpoints Administrativos de Produtos (`app.api.admin_products`)

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `GET` | `/api/admin/produtos` | Lista produtos com filtros (`termo`, `categoria`), paginação e imagens |
| `GET` | `/api/admin/produtos/{id}` | Detalhes de um produto com lista completa de imagens associadas |
| `POST` | `/api/admin/produtos` | Cria produto manual (dados em JSON ou Multipart com upload da foto) |
| `PUT` | `/api/admin/produtos/{id}` | Atualização parcial de dados do produto |
| `DELETE` | `/api/admin/produtos/{id}` | Exclui produto, desassocia imagens e limpa vetores no Qdrant |
| `POST` | `/api/admin/produtos/{id}/imagens` | Adiciona nova foto a um produto existente e gera vetor CLIP |
| `DELETE` | `/api/admin/produtos/{id}/imagens/{img_id}` | Remove imagem e expurga vetor no Qdrant |
| `POST` | `/api/admin/produtos/{id}/imagens/{img_id}/principal` | Define imagem como capa do produto |

---

## 6. Pipeline de Extração Híbrida de Catálogos (PDF e Imagens)

### 6.1 Endpoint SSE de Extração
`POST /api/admin/produtos/catalogo/extrair/stream`
- Recebe arquivo PDF multipáginas ou lista de imagens via `multipart/form-data`.
- Parâmetros adicionais:
  - `provider`: `"local"` (default) ou `"external"` (forçar visão via OpenRouter).
  - `fallback_external`: booleano (default: `True`) para acionar OpenRouter se a página local não extrair produtos ou for puramente imagem/escaneada.

### 6.2 Processamento Recorrente Página a Página
1. Para cada página $P_i$ ($i = 1 \dots N$):
   - **Renderização visual:** gera imagem PNG da página em memória (150 DPI) via `pdfplumber.Page.to_image()`.
   - **Extração textual:** obtém o texto e tabelas nativas via `pdfplumber.Page.extract_text()`.
   - **Avaliação de conteúdo:**
     - Se `provider == "local"` e o texto nativo tiver mais de 50 caracteres:
       - Envia o texto ao modelo local Ollama (`app.state.local_client.generate`) com prompt estruturado solicitando JSON.
     - Se não houver texto legível (PDF escaneado/folheto gráfico) ou se `provider == "external"`:
       - Envia a imagem da página para `app.state.external_client.describe_image` usando prompt especializado de catálogo.
2. **Geração de Miniaturas/Recortes Temporários:**
   - Salva a imagem da página ou de objetos recortados em `./data/product_images/temp/{job_id}_p{page}_{idx}.png`.
   - Cada produto detectado recebe um `temp_image_url`.
3. **Emissão de Eventos SSE:**
   - `event: progresso`: `{"pagina": i, "total": N, "status": "Processando página...", "produtos_parciais": K}`.
   - `event: pagina_concluida`: `{"pagina": i, "produtos": [...]}`.
   - `event: done`: `{"job_id": "...", "total_produtos": T, "produtos": [...]}`.

### 6.3 Confirmação e Ingestão em Lote (Human-in-the-Loop)
`POST /api/admin/produtos/catalogo/confirmar`
- Payload:
  ```json
  {
    "job_id": "...",
    "produtos": [
      {
        "nome": "Câmera Bullet VIP 5200",
        "descricao": "...",
        "categoria": "CFTV",
        "especificacoes_tecnicas": "...",
        "preco_base_fornecedor": 380.00,
        "preco": 549.00,
        "temp_image_url": "/api/uploads/produtos/temp/job1_p1_0.png",
        "selecionado": true
      }
    ]
  }
  ```
- O backend itera sobre os itens com `selecionado == true`:
  1. Cria o produto na tabela `produtos`.
  2. Move o arquivo de `temp/` para o diretório definitivo `data/product_images/`.
  3. Insere o registro em `produto_imagens`.
  4. Gera o embedding no CLIP e grava o ponto em `catalogo_imagens`.

---

## 7. Interface Frontend (`frontend/app/admin/produtos`)

### 7.1 Navegação
- Item adicionado no menu de engrenagem ([`AdminGearMenu.tsx`](file:///home/augusto/Projetos/TCC/frontend/components/layout/AdminGearMenu.tsx)):
  - **📦 Catálogo de Produtos** (`/admin/produtos`).

### 7.2 Tela Principal
- Barra superior de busca e filtro de categoria.
- Botão secundário: **`+ Novo Produto Manual`**.
- Botão primário com destaque: **`📥 Importar Catálogo (PDF / Folder)`**.
- Tabela de produtos com thumbnail, badge `CLIP ⚡`, preços (fornecedor e venda), margem calculada e ações de edição/exclusão.

### 7.3 Modal de Importação de Catálogos (3 Passos)
1. **Passo 1: Upload & Seleção de IA**
   - Drag & Drop para PDF multipáginas ou seleção de fotos.
   - Toggle: "Processamento Local prioritário (Ollama)" vs "Visão Externa (OpenRouter)".
   - Checkbox: "Fallback em tempo real para OpenRouter em páginas escaneadas".
2. **Passo 2: Barra de Progresso SSE**
   - Visualização do andamento por página com contador em tempo real.
   - Botão para forçar visão externa em páginas difíceis.
3. **Passo 3: Tabela de Revisão e Ajuste (Human-in-the-Loop)**
   - Checkbox individual e "Selecionar Todos".
   - Miniatura da foto com botão "Trocar Imagem".
   - Inputs inline para Nome, Categoria, Preço Fornecedor, Preço Venda e Especificações.
   - Botão final: **"Confirmar e Salvar no Catálogo & CLIP"**.

---

## 8. Estratégia de Testes

1. **Testes de Banco & Models (`tests/test_catalog_db.py`):**
   - Criação de produto com `preco_base_fornecedor` e `imagem_url`.
   - Criação, leitura e exclusão em cascata de `ProdutoImagem`.
2. **Testes da API Administrativa (`tests/test_admin_products_api.py`):**
   - Listagem, criação multipart com upload de arquivo, atualização parcial e exclusão.
3. **Testes do CLIP e Associação Visual (`tests/test_admin_products_clip.py`):**
   - Verificação de gravação do ponto com `produto_id` no Qdrant mock/em memória.
   - Verificação de expurgo do vetor ao deletar a imagem.
4. **Testes do Pipeline de Extração de Catálogo (`tests/test_catalog_extraction.py`):**
   - Simulação de leitura de PDF multipáginas com mock de `pdfplumber` e do gerador SSE.
   - Confirmação de lote de produtos com migração de imagens temporárias para definitivas.
