import { defineConfig, devices } from "@playwright/test";

// MVP: só Chromium, sem matriz de browsers/dispositivos — suficiente para o
// protótipo de TCC (ver docs/FRONTEND.md §6, Fase 9 do docs/ROADMAP.md).
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    // Permite testar o `AudioRecorder` (getUserMedia/MediaRecorder) sem um
    // microfone real: o Chromium gera um dispositivo de áudio fake (tom de
    // teste) e aceita automaticamente o prompt de permissão.
    launchOptions: {
      args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"],
    },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: true,
  },
});
