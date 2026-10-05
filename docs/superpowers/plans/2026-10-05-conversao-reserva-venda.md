# Conversão de Reserva para Venda com Comprovação Multimodal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o recurso de conversão de reservas de produtos em vendas efetivas com validação por documentos de comprovante de pagamento (Imagem, PDF e TXT) processados por LLM multimodal interno, cobrindo as 5 modalidades especificadas: Manual Simples (Admin), Manual Padrão (Admin com Assistência de IA), Automática por Upload (Admin), Automática via Chat (Cliente / Assistente Virtual) e Automática via Protocolo MCP (`converter_reserva_venda`).

**Architecture:** 
Novas colunas e tabelas estendem o modelo de `Pedido` em `app.db.models` (`status` expandido para `"venda_concluida"`, `"pagamento_divergente"`, adicionando `comprovante_url`, `tipo_conversao`, `convertido_em`, `convertido_por`, `llm_parecer`). 
Um novo serviço `ComprovanteEvaluator` (`app/services/comprovante_evaluator.py`) realiza OCR/extração de documentos (PDF via `pdf_extract`, Imagem via Vision/OCR, TXT via UTF-8) e submete o conteúdo ao LLM interno com um prompt de verificação financeira estruturada.
A API administrativa em `/api/admin/pedidos` provê endpoints para conversão manual e automática de comprovantes.
O Roteador de Chat (B2C/B2B) reconhece o envio de comprovantes de pagamento e executa a conversão automática diretamente no chat.
O servidor MCP B2B expõe a ferramenta `converter_reserva_venda` para automação por sistemas de parceiros.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (async), PostgreSQL, Alembic, Pydantic v2, PyPDF/PDFExtract, OCR/Vision LLM, MCP SDK, Next.js 14, Tailwind CSS, TypeScript, Pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-05-conversao-reserva-venda-design.md`

## Global Constraints

- Python 3.11+ assíncrono com SQLAlchemy 2.0 e asyncpg.
- Modificação estrutural de banco de dados versionada via Alembic migration (`0022_conversao_reserva_venda.py`).
- Manter o escopo alinhado às 5 modalidades especificadas.
- O serviço de avaliação por LLM deve retornar parecer padronizado em JSON (`valido`, `valor_comprovante`, `divergencia`, `justificativa`).
- Em caso de falha de leitura ou divergência nos valores, o pedido não pode ser convertido automaticamente em venda (deve ir para `pagamento_divergente` ou permanecer `reservado`).
- Commits cirúrgicos com referências claras aos requisitos (R12/Vendas).

---

### Task 1: Migration 0022 & Atualização do Modelo SQLAlchemy (`pedidos`)

**Files:**
- Create: `backend/migrations/versions/0022_conversao_reserva_venda.py`
- Modify: `backend/src/app/db/models.py`
- Test: `backend/tests/test_conversao_reserva_venda_models.py`

**Interfaces:**
- Consumes: Modelo `Pedido` de `app.db.models`.
- Produces: Novas colunas em `Pedido`: `comprovante_url`, `tipo_conversao`, `convertido_em`, `convertido_por`, `llm_parecer`.

- [ ] **Step 1: Escrever teste de unidade para validação do modelo com novos campos**

Criar `backend/tests/test_conversao_reserva_venda_models.py` verificando a inclusão das colunas de conversão de venda no modelo `Pedido`.

```python
import pytest
from datetime import datetime, UTC
from app.db.models import Pedido

@pytest.mark.asyncio
async def test_pedido_conversao_venda_fields(db_session):
    now = datetime.now(UTC)
    pedido = Pedido(
        status="venda_concluida",
        user_email="cliente@exemplo.com",
        comprovante_url="/uploads/comprovantes/pix_123.pdf",
        tipo_conversao="auto_chat",
        convertido_em=now,
        convertido_por="sistema_llm",
        llm_parecer='{"valido": true, "valor_comprovante": 1500.00, "divergencia": 0.0}',
    )
    db_session.add(pedido)
    await db_session.commit()

    saved_pedido = await db_session.get(Pedido, pedido.id)
    assert saved_pedido.status == "venda_concluida"
    assert saved_pedido.comprovante_url == "/uploads/comprovantes/pix_123.pdf"
    assert saved_pedido.tipo_conversao == "auto_chat"
    assert saved_pedido.convertido_em is not None
    assert saved_pedido.convertido_por == "sistema_llm"
    assert "valido" in saved_pedido.llm_parecer
```

- [ ] **Step 2: Executar o teste e confirmar falha**

Run: `backend/.venv/bin/pytest backend/tests/test_conversao_reserva_venda_models.py -v`
Expected: FAIL (campos inexistentes em `Pedido`).

- [ ] **Step 3: Criar migração Alembic 0021 e modificar `models.py`**

Adicionar as colunas em `backend/src/app/db/models.py` no model `Pedido`:
- `comprovante_url: Mapped[str | None] = mapped_column(String(255), nullable=True)`
- `tipo_conversao: Mapped[str | None] = mapped_column(String(50), nullable=True)`
- `convertido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)`
- `convertido_por: Mapped[str | None] = mapped_column(String(100), nullable=True)`
- `llm_parecer: Mapped[str | None] = mapped_column(Text, nullable=True)`

Criar o arquivo de migração `backend/migrations/versions/0021_conversao_reserva_venda.py`.

- [ ] **Step 4: Executar os testes novamente**

Run: `backend/.venv/bin/pytest backend/tests/test_conversao_reserva_venda_models.py -v`
Expected: PASS.

---

### Task 2: Serviço `ComprovanteEvaluator` por LLM Multimodal

**Files:**
- Create: `backend/src/app/services/comprovante_evaluator.py`
- Create: `backend/tests/test_comprovante_evaluator.py`
- Modify: `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md`

**Interfaces:**
- Consumes: Arquivos em memória/disco (PDF, JPG, PNG, TXT), `pdf_extract.py`, LLM local/externo.
- Produces: Dataclass `ParecerComprovante` (`valido: bool`, `valor_pago: Decimal`, `divergencia: Decimal`, `justificativa: str`, `codigo_transacao: str | None`).

- [ ] **Step 1: Criar teste de unidade para o extrator e avaliador de comprovante**

Criar `backend/tests/test_comprovante_evaluator.py` testando a extração de um comprovante em formato TXT e PDF simulados.

```python
import pytest
from decimal import Decimal
from app.services.comprovante_evaluator import ComprovanteEvaluator, ParecerComprovante

@pytest.mark.asyncio
async def test_avaliar_comprovante_txt_valido():
    conteudo_txt = """
    COMPROVANTE DE PAGAMENTO PIX
    Valor: R$ 1.500,00
    Data: 05/10/2026
    ID Transação: E1234567890
    Favorecido: Minha Empresa B2B LTDA
    """
    evaluator = ComprovanteEvaluator()
    parecer = await evaluator.avaliar_texto(conteudo_txt, valor_devido=Decimal("1500.00"))
    
    assert parecer.valido is True
    assert parecer.valor_pago == Decimal("1500.00")
    assert parecer.divergencia == Decimal("0.00")
    assert parecer.codigo_transacao == "E1234567890"
```

- [ ] **Step 2: Implementar o módulo `comprovante_evaluator.py`**

Criar a classe `ComprovanteEvaluator` em `backend/src/app/services/comprovante_evaluator.py`:
- Método `extrair_texto(conteudo_bytes, extensao)` (trata PDF via `pdf_extract`, TXT via UTF-8, imagem via OCR/Visão).
- Método `avaliar(conteudo_bytes, extensao, valor_devido)` que monta o prompt de extração estruturada (JSON) via LLM e calcula a divergência matemática (`valor_pago - valor_devido`).

- [ ] **Step 3: Testar o serviço**

Run: `backend/.venv/bin/pytest backend/tests/test_comprovante_evaluator.py -v`
Expected: PASS.

---

### Task 3: Endpoints Admin de Conversão Manual & Automática (`/api/admin/pedidos`)

**Files:**
- Create: `backend/src/app/api/admin_pedidos_conversao.py`
- Modify: `backend/src/app/main.py` (registrar router)
- Test: `backend/tests/test_admin_pedidos_conversao_api.py`

**Interfaces:**
- Consumes: Service `ComprovanteEvaluator`, `app.db.catalog`.
- Produces: 
  - `POST /api/admin/pedidos/{id}/converter-manual-simples` (Modo 1)
  - `POST /api/admin/pedidos/{id}/analisar-comprovante` (Modo 2)
  - `POST /api/admin/pedidos/{id}/confirmar-conversao` (Modo 2)
  - `POST /api/admin/pedidos/{id}/converter-auto-admin` (Modo 3)

- [ ] **Step 1: Criar testes de API dos endpoints administrativos de conversão**

Testar chamadas para as 3 rotas administrativas com dados simulados de upload de arquivo.

- [ ] **Step 2: Implementar os endpoints em `admin_pedidos_conversao.py`**

Implementar os handlers das rotas com validações de status prévio (`Pedido.status == "reservado"`), persistência de arquivo em `uploads/comprovantes/` e atualização do pedido no banco de dados.

- [ ] **Step 3: Executar a suíte de testes de API**

Run: `backend/.venv/bin/pytest backend/tests/test_admin_pedidos_conversao_api.py -v`
Expected: PASS.

---

### Task 4: Fluxo de Conversão Automática via Chat (B2C e B2B - Modos 4 e 5)

**Files:**
- Modify: `backend/src/app/router/orchestrator.py`
- Modify: `backend/src/app/router/sales_catalog.py`
- Test: `backend/tests/test_chat_conversao_reserva.py`

**Interfaces:**
- Consumes: `ComprovanteEvaluator`, `criar_pedido` / `obter_pedido_ativo_sessao`.
- Produces: Conversão automática do pedido vinculado à conversa ao receber um comprovante de pagamento no chat público ou B2B.

- [ ] **Step 1: Criar teste de integração para envio de comprovante no chat**

Simular o envio de uma mensagem de chat contendo anexo ou referência de pagamento para uma reserva aberta na sessão, verificando a conversão de `reservado` para `venda_concluida`.

- [ ] **Step 2: Implementar detecção de intenção em `orchestrator.py` e handler em `sales_catalog.py`**

Atualizar o orquestrador para identificar intenção `vendas_comprovante_pagamento` quando um anexo ou texto de comprovante é enviado. Executar o `ComprovanteEvaluator` com o valor devido do pedido da sessão. Se aprovado, atualizar status para `venda_concluida` (`tipo_conversao="auto_chat"`) e responder ao usuário confirmando o encerramento da venda.

- [ ] **Step 3: Executar testes de integração do chat**

Run: `backend/.venv/bin/pytest backend/tests/test_chat_conversao_reserva.py -v`
Expected: PASS.

---

### Task 5: Tool MCP B2B `converter_reserva_venda` (Modo 5)

**Files:**
- Modify: `backend/src/app/mcp_server/b2b.py`
- Modify: `cliente-b2b/src/client.py`
- Modify: `cliente-b2b/src/app.py`
- Test: `backend/tests/test_mcp_converter_reserva.py`

**Interfaces:**
- Consumes: Protocolo MCP (streamable HTTP), `ComprovanteEvaluator`.
- Produces: Ferramenta MCP `converter_reserva_venda(pedido_id: str, comprovante_base64_ou_texto: str, nome_arquivo: str) -> dict`.

- [ ] **Step 1: Criar teste para a ferramenta MCP `converter_reserva_venda`**

Testar a chamada da ferramenta via MCP client enviando um payload com pedido_id e o comprovante em texto/base64.

- [ ] **Step 2: Implementar a tool no Servidor MCP B2B (`b2b.py`) e Cliente B2B Streamlit**

Adicionar a ferramenta `@mcp.tool(name="converter_reserva_venda")` em `backend/src/app/mcp_server/b2b.py`. Ela obtém o pedido pelo ID, submete o comprovante ao `ComprovanteEvaluator` e, se validado, altera `status="venda_concluida"` (`tipo_conversao="auto_mcp_b2b"`). Atualizar a UI Streamlit em `cliente-b2b` com formulário para envio de comprovante.

- [ ] **Step 3: Executar os testes do MCP B2B**

Run: `backend/.venv/bin/pytest backend/tests/test_mcp_converter_reserva.py -v`
Expected: PASS.

---

### Task 6: Interface Administrativa no Frontend (`/admin/pedidos`)

**Files:**
- Create: `frontend/app/admin/pedidos/page.tsx`
- Create: `frontend/app/admin/pedidos/modal_conversao.tsx`
- Test: Testes de renderização frontend (Vitest / Playwright).

**Interfaces:**
- Consumes: Endpoints `/api/admin/pedidos/*`.
- Produces: Tela de gestão de pedidos com listagem de reservas, filtro de status (`reservado`, `venda_concluida`, `pagamento_divergente`) e modal interativo para execução dos Modos 1, 2 e 3 de conversão com upload de arquivo e exibição do parecer do LLM.

- [ ] **Step 1: Criar componentes do modal de conversão e página de pedidos**

Implementar componentes React/Next.js com suporte a drag-and-drop de arquivos de comprovante (PDF, JPG, PNG, TXT), seletor da modalidade de conversão (Manual Simples, Manual Padrão com Parecer IA, Automático) e exibição do resultado/status do pedido.

- [ ] **Step 2: Validar compilação do frontend**

Run: `npm --prefix frontend run build`
Expected: Compilação TypeScript / Next.js com 0 erros.

---

### Task 7: Atualização da Documentação Central

**Files:**
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md`

- [ ] **Step 1: Atualizar `docs/ARCHITECTURE.md`**
Registrar a funcionalidade de conversão de reserva em venda com as 5 modalidades, detalhando os estados estendidos do pedido (`venda_concluida`, `pagamento_divergente`) e a integração multimodal com LLM.

- [ ] **Step 2: Atualizar `docs/ROADMAP.md`**
Adicionar a nova seção no Roadmap referente à funcionalidade de Conversão de Reserva em Venda com as caixas de verificação marcadas.

- [ ] **Step 3: Atualizar `docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md`**
Documentar o prompt de extração estruturada e avaliação de comprovantes financeiros.
