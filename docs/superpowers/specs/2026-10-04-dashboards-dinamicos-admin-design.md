# Dashboards e Gráficos Dinâmicos Gerados via Chat com Persistência Permanente no PostgreSQL

## 1. Visão Geral e Objetivos

Este documento especifica a arquitetura e implementação do subsistema de **Dashboards e Gráficos Dinâmicos solicitados pelo Administrador via Chat**.

### 1.1. Motivação
Atualmente, o Administrador pode consultar informações sobre catálogo, estoque, métricas de tokens e relatórios através do chat ou de telas fixas do sistema. No entanto, não há um meio de:
- Pedir uma visualização gráfica personalizada diretamente em linguagem natural no chat (ex.: *"Crie um gráfico de barras das vendas por categoria no último mês"*).
- Manter os gráficos gerados salvos em um painel permanente (**"/admin/dashboards"**) que resista a reinicializações da aplicação ou trocas de sessão.

### 1.2. Principais Funcionalidades
1. **Geração Inteligente via Chat**:
   - O Administrador (logado) solicita um gráfico no chat público ou no modo admin.
   - O Orquestrador identifica a solicitação, extrai/calcula os dados no banco relacional ou nas métricas do sistema, e emite um card de mensagem rico (`CardGrafico`).
2. **Persistência Permanente no PostgreSQL (`admin_charts`)**:
   - Os gráficos gerados são salvos automaticamente no banco de dados na tabela `admin_charts`.
   - A reinicialização do servidor ou deploy da aplicação preserva 100% dos dashboards criados pelo Admin.
3. **Painel de Dashboards (`/admin/dashboards`)**:
   - Área acessível via menu ⚙️ no frontend para visualizar a galeria completa dos gráficos salvos.
   - Suporte a atualização em tempo real (*refresh*), reordenação na grade (grid layout), edição de títulos e exclusão.

---

## 2. Modelo de Dados (PostgreSQL & Alembic Migration `0019`)

### 2.1. Tabela `admin_charts`

Criada pela migração Alembic `0019_admin_charts.py`:

```python
class AdminChart(Base):
    """Gráficos dinâmicos gerados via chat pelo Administrador e persistidos
    para exibição no painel permanente /admin/dashboards.
    """

    __tablename__ = "admin_charts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    tipo_grafico: Mapped[str] = mapped_column(String(50), nullable=False)  # "bar", "line", "pie", "area", "donut"
    config_json: Mapped[dict] = mapped_column(_JsonVariant, nullable=False, default=dict)
    dados_json: Mapped[list] = mapped_column(_JsonVariant, nullable=False, default=list)
    sql_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    fixado: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    ordem: Mapped[int] = mapped_column(default=0)
    criado_por: Mapped[str] = mapped_column(String(255), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

### 2.2. Estrutura do `config_json`
Especificação declarativa para o componente visual do frontend (Recharts):

```json
{
  "x_key": "categoria",
  "y_keys": ["total_vendas_brl"],
  "labels": {
    "total_vendas_brl": "Total de Vendas (R$)"
  },
  "format": "currency",
  "palette": ["#3b82f6", "#10b981", "#f59e0b", "#ef4444"]
}
```

---

## 3. Fluxo de Geração de Gráficos no Chat

### 3.1. Orquestrador e Resposta em SSE

1. **Detecção de Intenção**:
   - Quando a mensagem do visitante (validado como Admin via `auth_token`) contém pedidos explícitos de visualização gráfica (ex.: "gerar gráfico", "mostre num gráfico"), o roteador ativa o módulo de síntese visual `app.router.chart_generator`.
2. **Execução de Agregação de Dados**:
   - O gerador consulta os dados relevantes (vendas por categoria, histórico de pedidos, métricas de tokens/custos, estoques por CD).
3. **Persistência Imputada e Retorno**:
   - Cria o registro na tabela `admin_charts`.
   - Retorna no evento SSE `done` o card rico do tipo `CardGrafico`:

```python
class CardGrafico(BaseModel):
    tipo: Literal["grafico"] = "grafico"
    chart_id: str
    titulo: str
    tipo_grafico: Literal["bar", "line", "pie", "area", "donut"]
    config: dict
    dados: list[dict]
    fixado: bool = True
```

---

## 4. Endpoints REST Administrativos (`/api/admin/charts`)

### 4.1. Contrato da API (`app/api/admin_charts.py`)

- `GET /api/admin/charts`: Retorna a lista de gráficos salvos no dashboard ordenados por `ordem` e `criado_em`.
- `POST /api/admin/charts`: Permite criar manualmente ou via endpoint um novo gráfico no painel.
- `POST /api/admin/charts/{id}/refresh`: Re-executa a agregação de dados e atualiza o `dados_json` do gráfico no banco.
- `PUT /api/admin/charts/{id}`: Permite atualizar o título, descrição, ordem ou alternar a flag `fixado`.
- `DELETE /api/admin/charts/{id}`: Remove permanentemente um gráfico do dashboard.

---

## 5. Interface Frontend (`/admin/dashboards` & Renderizador Recharts)

### 5.1. Componentes Frontend
1. **`ChartRenderer.tsx`**:
   - Renderiza dinamicamente tipos de gráfico (`bar`, `line`, `pie`, `area`, `donut`) consumindo a biblioteca `recharts`.
   - Aplica temas responsivos, tooltips formatados (moeda, inteiros, porcentagens) e suporte a modo escuro/claro.
2. **`DynamicChartCard.tsx`**:
   - Card container do gráfico no painel `/admin/dashboards`.
   - Botões de ação rápida no topo do card: 🔄 Atualizar Dados, ✏️ Editar Título, 📌 Fixar/Desafixar, 🗑️ Excluir.
3. **Página `/admin/dashboards/page.tsx`**:
   - Grade responsiva de 1, 2 ou 3 colunas (CSS Grid) apresentando todos os gráficos fixados do Administrador.

---

## 6. Segurança & Proteção

- **Autenticação Obrigatória**: Apenas requisições com `auth_token` de administrador válido (`verificar_admin_por_token`) podem gerar gráficos via chat ou interagir com a API `/api/admin/charts`.
- **Sanitização de Agregações**: O gerador de gráficos executa apenas queries pré-compiladas do SQLAlchemy (como agregações de `produtos`, `pedidos` ou `metricas`), sem executar SQL arbitrário enviado na requisição HTTP.

---

## 7. Estratégia de Testes e Validação

1. **Testes do Backend (Pytest)**:
   - `test_admin_charts_model_and_crud`: Valida criação, atualização e exclusão na tabela `admin_charts`.
   - `test_chart_generator_router_integration`: Valida a sintaxe da ferramenta de geração de gráficos a partir do Orquestrador.
   - `test_admin_charts_api`: Valida os endpoints REST sob autenticação de token admin.
2. **Testes do Frontend (Vitest)**:
   - `ChartRenderer.test.tsx`: Valida renderização dos componentes do Recharts para cada tipo de gráfico (`bar`, `line`, `pie`, `area`).
   - `AdminDashboardsPage.test.tsx`: Valida listagem, exclusão e refresh na tela `/admin/dashboards`.
