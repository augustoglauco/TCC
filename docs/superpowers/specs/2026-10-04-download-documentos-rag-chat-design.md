# Download de Documentos RAG de Origem Direta no Chat via Cards Ricos

## 1. Visão Geral e Objetivos

Este documento especifica a arquitetura e implementação do recurso de **Download de Documentos de Origem Direta no Chat**.

### 1.1. Motivação
Atualmente, quando o visitante ou administrador faz uma pergunta técnica ou comercial no chat, o RAG pesquisa em manuais, catálogos e documentos ingeridos para compor a resposta em texto. No entanto, o usuário muitas vezes deseja acessar, ler ou guardar o arquivo original completo (PDF, TXT ou relatório) que originou aquela informação.

### 1.2. Principais Funcionalidades
1. **Detecção de Match Relevante**:
   - Durante a busca vetorial no Qdrant, o Orquestrador avalia os scores de similaridade dos chunks encontrados.
   - Chunks com score acima do limiar configurado (ex.: `score >= 0.65`) identificam o documento de origem na tabela `rag_documents`.
2. **Emissão de Card Rico (`CardDocumentoDownload`)**:
   - A resposta SSE do chat envia, junto com o texto da resposta, um card de anexo rico com nome do arquivo, tamanho formatado (MB/KB), porcentagem de relevância e link direto para download.
3. **Endpoint de Download Seguro (`GET /api/rag/documents/{id}/download`)**:
   - Endpoint HTTP dedicado que realiza a transmissão do arquivo original salvo em disco (`storage_path`), definindo os cabeçalhos apropriados de download (`Content-Disposition: attachment`).
4. **Respeito ao Isolamento de Acesso**:
   - Documentos de collections com finalidade `admin` exigem `auth_token` de Administrador válido para autorizar o download.

---

## 2. Endpoint de Download Seguro (`/api/rag/documents/{id}/download`)

### 2.1. Contrato e Regras da API (`app/api/rag.py`)

- **URL**: `GET /api/rag/documents/{id}/download`
- **Query Params (opcional)**: `auth_token` (para documentos restritos ao Admin).
- **Comportamento**:
  1. Busca o registro do documento na tabela `rag_documents` pelo `id`.
  2. Verifica se a collection de origem tem finalidade `purpose="admin"`. Se sim, exige validação do `auth_token` de Administrador (`verificar_admin_por_token`).
  3. Checa a existência física do arquivo em `storage_path`.
  4. Retorna um `FileResponse` da FastAPI com o tipo MIME correto (`application/pdf`, `text/plain`) e o cabeçalho `Content-Disposition: attachment; filename="{filename}"`.

---

## 3. Integração com o Orquestrador e Schemas de Chat

### 3.1. Novo Schema `CardDocumentoDownload` (`app/models/chat.py`)

```python
class CardDocumentoDownload(BaseModel):
    """Card rico de download de documento fonte do RAG (Fase 8)."""

    tipo: Literal["documento_download"] = "documento_download"
    documento_id: str = Field(..., description="UUID do documento na tabela rag_documents.")
    filename: str = Field(..., description="Nome do arquivo (ex.: Manual_GD30.pdf).")
    domain: str = Field(..., description="Domínio do documento (suporte, vendas, etc).")
    score: float = Field(..., description="Score de similaridade do melhor chunk.")
    download_url: str = Field(..., description="URL para download direto no backend.")
    file_size_bytes: int | None = Field(default=None, description="Tamanho do arquivo em bytes.")
```

União discriminada em `ChatCard`:

```python
ChatCard = Annotated[
    CardProduto | CardCotacao | CardAgendamento | CardGrafico | CardDocumentoDownload,
    Field(discriminator="tipo")
]
```

### 3.2. Lógica no Orquestrador (`app/router/orchestrator.py`)

Ao finalizar a busca no RAG:
```python
threshold = settings.rag_download_confidence_threshold  # default 0.65
melhor_chunk = max(rag_chunks, key=lambda c: c.score) if rag_chunks else None

if melhor_chunk and melhor_chunk.score >= threshold:
    doc = await buscar_rag_document_por_filename_ou_id(session, melhor_chunk.source)
    if doc and doc.storage_path e path_exists(doc.storage_path):
        card_documento = CardDocumentoDownload(
            documento_id=str(doc.id),
            filename=doc.filename,
            domain=doc.domain,
            score=melhor_chunk.score,
            download_url=f"/api/rag/documents/{doc.id}/download",
            file_size_bytes=get_file_size(doc.storage_path)
        )
```

---

## 4. Interface Frontend (`DocumentDownloadCard.tsx`)

### 4.1. Componente de UI (`frontend/components/chat/DocumentDownloadCard.tsx`)

O widget de chat renderiza o card visualmente destacado abaixo da mensagem:

- **Ícone por extensão**: Ícone em destaque de PDF (vermelho), Arquivo de Texto (azul) ou Documento Genérico (cinza).
- **Metadados**: Exibição do nome do arquivo, tamanho formatado (ex.: `2.4 MB`) e badge de relevância (ex.: `Relevância 92%`).
- **Ação**: Botão estilizado **"📥 Baixar Documento"** com efeito hover que inicia o download diretamente no navegador.

---

## 5. Estratégia de Testes e Validação

1. **Testes do Backend (Pytest)**:
   - `test_rag_document_download_endpoint_success`: Valida download de PDF/TXT existente com retorno do `FileResponse`.
   - `test_rag_document_download_admin_auth_required`: Valida que documentos de `purpose="admin"` exigem token e recusam com 401/403 se ausente.
   - `test_orchestrator_emits_document_download_card`: Valida que a busca vetorial com score >= 0.65 gera o card `CardDocumentoDownload`.
2. **Testes do Frontend (Vitest)**:
   - `DocumentDownloadCard.test.tsx`: Valida renderização dos elementos do card, botão de download e acionamento da URL correta.
