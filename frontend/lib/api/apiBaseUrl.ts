// Achado (2026-09-24): as 6 chamadoras hardcodeavam
// `process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"` — ao
// acessar o frontend por um host que não é o da máquina de dev (IP da LAN,
// domínio DuckDNS), "localhost" no navegador aponta pro PRÓPRIO dispositivo
// do usuário, não pro backend. Mesma classe do bug já corrigido em
// next.config.ts (allowedDevOrigins), mas no nível de chamada de API em vez
// do dev server.
export function getApiBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL;
  }
  if (typeof window !== "undefined") {
    return `http://${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
}
