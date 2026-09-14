import { defineConfig } from "@playwright/test";

import baseConfig from "./playwright.config";

// MVP: smoke test manual contra o backend e o modelo local (Ollama) reais —
// não roda no `npm run test:e2e` padrão (esse usa mocks, ver
// tests/e2e/chat.spec.ts) porque depende de infraestrutura externa (Ollama
// rodando com o modelo carregado) e tem latência de LLM real (dezenas de
// segundos). Ver docs/FRONTEND.md §6.
export default defineConfig(baseConfig, {
  testDir: "./tests/smoke",
  fullyParallel: false,
  timeout: 60_000,
  webServer: undefined,
});
