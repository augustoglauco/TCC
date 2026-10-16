import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";

/**
 * Contrato de `GET /api/admin/ferramentas` — estado das três ferramentas de
 * inteligência de código do projeto (Graphify, Repowise, GitNexus).
 *
 * `tipo` diz como a ferramenta é alcançada: `"artefato"` é um arquivo
 * gerado no repositório (Graphify) e `"servidor"` é um processo local que
 * precisa estar no ar. `url` vem `null` quando não há o que abrir — nesse
 * caso a tela mostra `comando`, que é o que gera/sobe o que falta.
 */
export interface FerramentaStatus {
  id: "graphify" | "repowise" | "gitnexus" | string;
  nome: string;
  descricao: string;
  tipo: "artefato" | "servidor" | string;
  url: string | null;
  online: boolean;
  detalhe: string | null;
  comando: string;
}

export interface FerramentasResposta {
  ferramentas: FerramentaStatus[];
}

export async function fetchFerramentas(token: string): Promise<FerramentasResposta> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/admin/ferramentas?_t=${Date.now()}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-cache",
      Pragma: "no-cache",
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Falha ao consultar as ferramentas (${response.status})`);
  }

  return (await response.json()) as FerramentasResposta;
}

/**
 * URL que o iframe usa para cada ferramenta.
 *
 * O artefato do Graphify é servido pelo backend e exige admin, mas um
 * iframe não manda cabeçalho `Authorization` — por isso o token vai na
 * query string, caminho que `require_admin` já aceita (mesmo padrão de
 * `GET /api/rag/documents/{id}/download`). Os servidores locais são
 * abertos direto na porta deles, sem token.
 */
export function urlDeVisualizacao(ferramenta: FerramentaStatus, token: string): string | null {
  if (!ferramenta.url) return null;
  if (ferramenta.url.startsWith("/")) {
    return `${getApiBaseUrl()}${ferramenta.url}?token=${encodeURIComponent(token)}`;
  }
  const url = urlPublicaDoServidor(ferramenta.url);
  return ferramenta.id === "gitnexus" ? comServerDoGitNexus(url) : url;
}

/**
 * A UI do GitNexus é uma SPA que chama o backend dela numa URL fixa de build
 * (`http://localhost:4747`, constante no bundle) — e esse `localhost` é o do
 * navegador. De fora da rede ele aponta para a máquina de quem acessa, a
 * sondagem falha e a tela fica parada em "Start your local server".
 *
 * O parâmetro `?server=` que a própria SPA lê sobrescreve essa URL. Apontá-lo
 * para a origem de onde a página foi servida resolve nos dois casos — e
 * também em `localhost`, onde a porta `4747` do padrão só respondia por
 * acidente, porque é a porta pública do Caddy.
 *
 * # MVP: casado com o parâmetro `server` do GitNexus 1.6.12; se uma versão
 * futura renomeá-lo, a tela volta ao "Start your local server".
 */
function comServerDoGitNexus(url: string): string {
  try {
    const u = new URL(url);
    u.searchParams.set("server", u.origin);
    return u.toString();
  } catch {
    return url;
  }
}

/**
 * Porta interna da UI -> porta pública do Caddy
 * (`infra/caddy/Caddyfile.ferramentas`), sem senha. O `localhost` de
 * uma URL de servidor é o do navegador, então quando o site é aberto de outra
 * máquina (DuckDNS) o host passa a ser o da própria página.
 */
const PORTA_PUBLICA: Record<string, string> = { "3012": "3002", "4757": "4747" };

function urlPublicaDoServidor(url: string): string {
  if (typeof window === "undefined") return url;
  const host = window.location.hostname;
  if (host === "localhost" || host === "127.0.0.1") return url;
  try {
    const u = new URL(url);
    if (u.hostname !== "localhost" && u.hostname !== "127.0.0.1") return url;
    u.hostname = host;
    u.port = PORTA_PUBLICA[u.port] ?? u.port;
    return u.toString();
  } catch {
    return url;
  }
}

export interface AtualizacaoResposta {
  sucesso: boolean;
  saida: string;
}

/**
 * `POST /api/admin/ferramentas/{id}/atualizar` — reindexa a ferramenta
 * (`graphify update .` ou `gitnexus analyze --index-only`).
 */
export async function atualizarFerramenta(
  id: "graphify" | "gitnexus",
  token: string,
): Promise<AtualizacaoResposta> {
  const response = await fetch(`${getApiBaseUrl()}/api/admin/ferramentas/${id}/atualizar`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    let detalhe = `Falha ao atualizar (${response.status})`;
    try {
      const corpo = (await response.json()) as { detail?: string };
      if (corpo.detail) detalhe = corpo.detail;
    } catch {
      // corpo sem JSON: mantém a mensagem genérica
    }
    throw new Error(detalhe);
  }

  return (await response.json()) as AtualizacaoResposta;
}
