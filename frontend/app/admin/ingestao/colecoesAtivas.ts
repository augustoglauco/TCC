import type { RagCollection } from "@/lib/types/rag";

export interface ColecoesAtivas {
  chat: RagCollection | undefined;
  b2b: RagCollection | undefined;
  admin: RagCollection | undefined;
}

/** Collection ativa de cada finalidade (purpose); sem purpose conta como "chat". */
export function colecoesAtivasPorFinalidade(collections: RagCollection[]): ColecoesAtivas {
  return {
    chat: collections.find((c) => c.is_active && (c.purpose || "chat") === "chat"),
    b2b: collections.find((c) => c.is_active && c.purpose === "mcp_b2b"),
    admin: collections.find((c) => c.is_active && c.purpose === "admin"),
  };
}
