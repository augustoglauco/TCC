import { getApiBaseUrl } from "./apiBaseUrl";

/** Chave ativa de um parceiro B2B (só o prefixo; o texto nunca é devolvido de novo). */
export interface ChaveParceiroAtiva {
  cliente_id: number;
  email: string;
  nome: string;
  prefixo: string;
  criada_em: string;
}

/** Resposta da geração: `chave` só existe nesta resposta. */
export interface ChaveParceiroGerada {
  cliente_id: number;
  email: string;
  prefixo: string;
  chave: string;
}

function headers(token: string | null): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function erroDaResposta(res: Response, padrao: string): Promise<Error> {
  const corpo = await res.json().catch(() => null);
  return new Error(corpo?.detail || `${padrao} (${res.status}).`);
}

export async function fetchChavesParceiros(token: string | null): Promise<ChaveParceiroAtiva[]> {
  const res = await fetch(`${getApiBaseUrl()}/api/admin/parceiros-b2b`, {
    headers: headers(token),
    cache: "no-store",
  });
  if (!res.ok) throw await erroDaResposta(res, "Erro ao carregar as chaves B2B");
  return res.json();
}

export async function gerarChaveParceiro(
  token: string | null,
  clienteId: number,
): Promise<ChaveParceiroGerada> {
  const res = await fetch(`${getApiBaseUrl()}/api/admin/parceiros-b2b/${clienteId}/chave`, {
    method: "POST",
    headers: headers(token),
  });
  if (!res.ok) throw await erroDaResposta(res, "Erro ao gerar a chave B2B");
  return res.json();
}

export async function revogarChaveParceiro(token: string | null, clienteId: number): Promise<void> {
  const res = await fetch(`${getApiBaseUrl()}/api/admin/parceiros-b2b/${clienteId}/chave`, {
    method: "DELETE",
    headers: headers(token),
  });
  if (!res.ok) throw await erroDaResposta(res, "Erro ao revogar a chave B2B");
}
