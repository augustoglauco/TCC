import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";

/**
 * Contrato de `/api/admin/datasets` — Painel de Preparação da Avaliação
 * (Fase 10, `backend/src/app/api/admin_datasets.py`).
 *
 * São duas metades independentes: o progresso/fila de revisão dos cinco
 * conjuntos da Estratégia A, e o executor das tarefas longas (ingestão e
 * benchmark), que roda solto e é lido por polling incremental do log.
 */
export type StatusRevisao = "pendente" | "aprovado" | "corrigido" | "descartado";

export interface ConjuntoStatus {
  id: string;
  nome: string;
  meta: number;
  total: number;
  pendentes: number;
  aprovados: number;
  corrigidos: number;
  descartados: number;
  /** Gabarito exato por construção (imagem e banco): entra na tela pronto,
   *  sem fila — é o que derruba a revisão humana de 12h para ~4,5h. */
  revisao_automatica: boolean;
  /** `false` quando o `dataset.json` ainda não foi gerado. */
  existe: boolean;
}

export interface DatasetsResposta {
  conjuntos: ConjuntoStatus[];
}

export interface ItemRevisao {
  indice: number;
  id: string;
  status: string;
  /** Campos crus do caso, sem `revisao`: cada conjunto tem o seu formato
   *  (a pergunta e o trecho de origem do RAG não são a mensagem do
   *  roteador), então a tela monta o layout a partir das chaves. */
  campos: Record<string, unknown>;
}

export interface ItensResposta {
  conjunto: string;
  total: number;
  itens: ItemRevisao[];
}

export interface TarefaResumo {
  id: string;
  tipo: string;
  rotulo: string;
  estado: "rodando" | "concluida" | "falhou" | "cancelada" | string;
  iniciada_em: number;
  terminada_em: number | null;
  codigo: number | null;
  total_linhas: number;
}

export interface TarefaDetalhe extends TarefaResumo {
  linhas: string[];
  proximo_offset: number;
}

/**
 * Tarefas que o backend aceita em `POST /tarefas`.
 *
 * # MVP: espelha `TAREFAS_DISPONIVEIS` de `admin_datasets.py` à mão — o
 * backend não expõe rota que liste os tipos, e um tipo desconhecido volta
 * 404. Ao acrescentar tarefa lá, acrescente aqui.
 */
export const TAREFAS: { tipo: string; rotulo: string; descricao: string }[] = [
  {
    tipo: "gerar_rascunho_rag_docs",
    rotulo: "Gerar rascunho: 180 perguntas de RAG",
    descricao:
      "160 respondíveis sobre os PDFs + 20 sem resposta. Retomável, e no tier :free o rate limit manda no relógio.",
  },
  {
    tipo: "ingerir_corpus",
    rotulo: "Ingerir o corpus no RAG",
    descricao: "Os PDFs de docs/Manuais_fornecedor/ControlId na collection ativa. Minutos.",
  },
  {
    tipo: "triagem",
    rotulo: "Triagem: roteador + imagem",
    descricao: "Os 10 candidatos, sem chamada de juiz. ~8 min de GPU cada.",
  },
  {
    tipo: "rodada_completa",
    rotulo: "Rodada completa do benchmark",
    descricao: "As quatro etapas nos sobreviventes da triagem. Horas, e gasta juiz.",
  },
];

async function pedir<T>(caminho: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}/api/admin/datasets${caminho}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-cache",
      Authorization: `Bearer ${token}`,
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let detalhe = `Falha na requisição (${response.status})`;
    try {
      const corpo = (await response.json()) as { detail?: string };
      if (corpo.detail) detalhe = corpo.detail;
    } catch {
      // corpo sem JSON: mantém a mensagem genérica
    }
    throw new Error(detalhe);
  }

  return (await response.json()) as T;
}

export function fetchConjuntos(token: string): Promise<DatasetsResposta> {
  return pedir<DatasetsResposta>(`?_t=${Date.now()}`, token);
}

export function fetchItens(
  conjuntoId: string,
  token: string,
  opcoes: { apenasPendentes?: boolean; offset?: number; limite?: number } = {},
): Promise<ItensResposta> {
  const query = new URLSearchParams({
    apenas_pendentes: String(opcoes.apenasPendentes ?? true),
    offset: String(opcoes.offset ?? 0),
    limite: String(opcoes.limite ?? 20),
  });
  return pedir<ItensResposta>(`/${conjuntoId}/itens?${query}`, token);
}

/**
 * Grava a decisão de revisão no próprio `dataset.json`. `campos` só vai
 * quando o revisor corrigiu algo — o backend faz `update`, não substituição,
 * então mandar o item inteiro não é necessário.
 */
export function revisarItem(
  conjuntoId: string,
  indice: number,
  status: StatusRevisao,
  token: string,
  campos?: Record<string, unknown>,
): Promise<ItemRevisao> {
  return pedir<ItemRevisao>(`/${conjuntoId}/itens/${indice}`, token, {
    method: "PATCH",
    body: JSON.stringify(campos ? { status, campos } : { status }),
  });
}

export function iniciarTarefa(tipo: string, token: string): Promise<TarefaResumo> {
  return pedir<TarefaResumo>("/tarefas", token, {
    method: "POST",
    body: JSON.stringify({ tipo }),
  });
}

export function fetchTarefas(token: string): Promise<TarefaResumo[]> {
  return pedir<TarefaResumo[]>(`/tarefas?_t=${Date.now()}`, token);
}

/** `desde` é o offset do log já exibido: a tela pede só o que falta. */
export function fetchTarefa(id: string, desde: number, token: string): Promise<TarefaDetalhe> {
  return pedir<TarefaDetalhe>(`/tarefas/${id}?desde=${desde}`, token);
}

export function cancelarTarefa(id: string, token: string): Promise<TarefaResumo> {
  return pedir<TarefaResumo>(`/tarefas/${id}/cancelar`, token, { method: "POST" });
}
