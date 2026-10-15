"""Configuração de execução dos agentes autônomos (R13).

Estado de processo único, atualizado pelo painel de configurações
(`PUT /api/admin/runtime-settings`, persistido em `app_settings`) e no boot
pelo `lifespan` de `app.main`. Fica num módulo porque o gancho que dispara
os agentes (`app.db.catalog.criar_pedido`) não tem acesso a `request.app`.
"""

from dataclasses import dataclass
from typing import Any, Literal

EstoqueAgentMode = Literal["desativado", "deterministico", "ia"]
EstoqueAgentLlm = Literal["local", "externo"]

DEFAULT_ESTOQUE_AGENT_MODE: EstoqueAgentMode = "deterministico"
DEFAULT_ESTOQUE_AGENT_LLM: EstoqueAgentLlm = "local"


@dataclass
class AgentRuntime:
    estoque_modo: EstoqueAgentMode = DEFAULT_ESTOQUE_AGENT_MODE
    estoque_llm: EstoqueAgentLlm = DEFAULT_ESTOQUE_AGENT_LLM
    local_client: Any = None
    external_client: Any = None

    def llm_client(self) -> Any:
        return self.external_client if self.estoque_llm == "externo" else self.local_client


runtime = AgentRuntime()
