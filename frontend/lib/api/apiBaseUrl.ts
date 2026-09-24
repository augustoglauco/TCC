// Achado (2026-09-24): as 6 chamadoras hardcodeavam
// `process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"` — ao
// acessar o frontend por um host que não é o da máquina de dev (IP da LAN,
// domínio DuckDNS), "localhost" no navegador aponta pro PRÓPRIO dispositivo
// do usuário, não pro backend. Mesma classe do bug já corrigido em
// next.config.ts (allowedDevOrigins), mas no nível de chamada de API em vez
// do dev server.
export function getApiBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    // Achado no code-review (2026-09-24): sem remover uma barra final, um
    // valor como "http://backend:8000/" virava "http://backend:8000//api/..."
    // (barra dupla) nas 5+ chamadoras que fazem `${API_BASE_URL}/api/...` —
    // o roteador do FastAPI não trata isso como equivalente à rota real, e
    // toda requisição vira 404 mesmo com a URL "parecendo" certa.
    return process.env.NEXT_PUBLIC_API_BASE_URL.replace(/\/+$/, "");
  }
  if (typeof window !== "undefined") {
    // Achado no code-review (2026-09-24): protocolo fixo em "http" quebrava
    // em mixed content assim que a página era aberta via https (ex.: atrás
    // de um proxy reverso com TLS) — o navegador bloqueia toda chamada
    // fetch para um recurso http a partir de uma página https. Usa o mesmo
    // protocolo da própria página em vez de fixar "http".
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
}
