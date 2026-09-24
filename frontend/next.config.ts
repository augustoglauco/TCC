import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next.js 16 bloqueia por padrão requisições de dev cross-origin
  // (inclusive o WebSocket de HMR) vindas de qualquer origem que não seja
  // `localhost` — acessar o dev server pelo IP da rede local (ex.: testar
  // no celular na mesma rede) faz o handshake do HMR falhar
  // (`net::ERR_INVALID_HTTP_RESPONSE`), o que impede o React de terminar a
  // hidratação: a página SSR aparece normal, mas nenhum botão interativo
  // responde a toque (menu hambúrguer, modal do chat). Só o hostname é
  // comparado (sem porta/esquema) — ver
  // node_modules/next/dist/docs/.../allowedDevOrigins.md.
  allowedDevOrigins: ["192.168.1.200"],
};

export default nextConfig;
