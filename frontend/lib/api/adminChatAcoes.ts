import { extrairDetalheDeErro } from "@/lib/api/errors";
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";

const API_BASE_URL = getApiBaseUrl();

async function postarAcao(
  token: string,
  id: string,
  rota: "confirmar" | "cancelar",
): Promise<{ status: string; depois?: Record<string, unknown> }> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/admin/chat/acoes/${id}/${rota}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new Error("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }
  if (!response.ok) {
    throw new Error(
      (await extrairDetalheDeErro(response)) ?? "Não foi possível concluir a ação. Tente novamente.",
    );
  }
  return (await response.json()) as { status: string; depois?: Record<string, unknown> };
}

export const confirmarAcao = (token: string, id: string) => postarAcao(token, id, "confirmar");
export const cancelarAcao = (token: string, id: string) => postarAcao(token, id, "cancelar");
