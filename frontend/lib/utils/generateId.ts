/**
 * Gera um id único no cliente. `crypto.randomUUID()` só existe em contexto
 * seguro (HTTPS ou `localhost`) — acessar o dev server pelo IP local via
 * HTTP (ex.: testar no celular na mesma rede) deixa `crypto.randomUUID`
 * `undefined`, o que derrubava o app inteiro sem tratamento (o erro
 * acontecia num `useEffect` montado na raiz do layout, e sem Error Boundary
 * o React desmonta toda a árvore — por isso nem o menu hambúrguer nem o
 * modal do chat apareciam). Fallback: UUID v4 via `Math.random`, suficiente
 * para um id de UI local, não para uso criptográfico.
 */
export function generateId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}
