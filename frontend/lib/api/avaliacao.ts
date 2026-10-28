import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";

/** Proporção com intervalo de confiança de 95% (Wilson). */
export interface Proporcao {
  acertos: number;
  total: number;
  taxa: number;
  ic_inf: number;
  ic_sup: number;
}

export interface RoteadorProvedor {
  provider: string;
  acuracia: Proporcao;
  latencia_media_s: number | null;
  degradacoes: number;
  /** esperado -> previsto -> contagem */
  matriz_confusao: Record<string, Record<string, number>>;
}

export interface ResultadosAvaliacao {
  roteador: { dominios: string[]; provedores: RoteadorProvedor[] } | null;
  rag: {
    total: number;
    nota_media: number | null;
    fonte_correta: Proporcao;
    nota_media_fonte_certa: number | null;
    nota_media_fonte_errada: number | null;
    distribuicao_notas: Record<string, number>;
    por_dificuldade: { dificuldade: string; total: number; nota_media: number | null }[];
    /** Perguntas que o corpus não responde: o certo é recusar sem inventar. */
    sem_resposta: { total: number; recusou: number; alucinou: number };
  } | null;
  /** Baseline (MiniLM 800/100) x vencedora (bge-m3 768/115) da Etapa 7. */
  etapa7: {
    bracos: {
      braco: string;
      rotulo: string;
      respondiveis: number;
      nota_media: number;
      fonte_correta: number;
      fonte_correta_ic: Proporcao;
      recusas_indevidas: number;
      sem_resposta: number;
      negativas_recusou: number;
      negativas_alucinou: number;
      latencia_media_s: number;
      latencia_p95_s: number;
    }[];
  } | null;
  chunk_size: {
    pontos: {
      chunk_size: number;
      overlap_pct: number | null;
      ndcg_10: number | null;
      recall_5: number | null;
    }[];
    melhor_chunk_size: number | null;
  } | null;
  injecao: {
    clientes: {
      cliente: string;
      resistencia: Proporcao;
      por_categoria: { categoria: string; total: number; comprometidos: number }[];
    }[];
  } | null;
  modelos: {
    modelo: string;
    gerado_em: string | null;
    config: Record<string, unknown>;
    metricas: Record<string, number | null>;
  }[];
}

/** Página pública: sem token. Só agregados — ver docs/ARCHITECTURE.md §9. */
export async function fetchResultadosAvaliacao(): Promise<ResultadosAvaliacao> {
  const response = await fetch(`${getApiBaseUrl()}/api/avaliacao/resultados`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Falha ao carregar os resultados (HTTP ${response.status}).`);
  }
  return (await response.json()) as ResultadosAvaliacao;
}
