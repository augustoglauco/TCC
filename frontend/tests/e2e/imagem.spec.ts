import { expect, test } from "@playwright/test";

// MVP: mocka a resposta de POST /api/chat/messages em vez de depender do
// CLIP/visão externa reais — mesmo espírito de `chat.spec.ts` (ver
// docs/FRONTEND.md §6). O fluxo padrão de qualquer imagem enviada é
// identificação de produto (docs/ARCHITECTURE.md §4): a resposta sai como
// `token` (texto) + `identification` (telemetria, ainda não renderizada
// separadamente pelo widget) + `done`.

function sseBody(events: Array<{ event: string; data: unknown }>): string {
  return events
    .map(({ event, data }) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
    .join("");
}

// PNG 1x1 mínimo válido — só precisa passar pela validação de formato do
// `ImageUploader` (aceita PNG/JPG/WEBP); o conteúdo nunca chega a ser
// decodificado de verdade, a resposta de `POST /api/chat/messages` é mockada.
const PNG_1X1_BASE64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=";

test("envia uma imagem e exibe a identificação do produto", async ({ page }) => {
  await page.route("**/api/chat/messages", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: sseBody([
        { event: "conversation", data: { conversation_id: "e2e-imagem-1" } },
        {
          event: "token",
          data: {
            text: "Identifiquei: Gerador Diesel GD-15.\n\nPotência de 15 kVA, ideal para pequenos comércios.",
          },
        },
        {
          event: "identification",
          data: { status: "identificado", produto: "Gerador Diesel GD-15", confidence: 0.92 },
        },
        {
          event: "done",
          data: {
            domain: "vendas",
            backend_used: "identificacao_imagem",
            escalation_reason: "nenhum",
          },
        },
      ]),
    });
  });

  await page.goto("/suporte");
  await page.getByRole("button", { name: "Abrir chat" }).click();

  await page.locator('input[type="file"]').setInputFiles({
    name: "gerador.png",
    mimeType: "image/png",
    buffer: Buffer.from(PNG_1X1_BASE64, "base64"),
  });
  await expect(page.getByText("🖼️ gerador.png")).toBeVisible();

  await page.getByRole("button", { name: "Enviar", exact: true }).click();

  await expect(page.getByText("Identifiquei: Gerador Diesel GD-15.")).toBeVisible();
});

test("mostra mensagem de produto não identificado", async ({ page }) => {
  await page.route("**/api/chat/messages", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: sseBody([
        { event: "conversation", data: { conversation_id: "e2e-imagem-2" } },
        { event: "token", data: { text: "Não identifiquei o produto." } },
        { event: "identification", data: { status: "nao_identificado" } },
        {
          event: "done",
          data: {
            domain: "vendas",
            backend_used: "identificacao_imagem",
            escalation_reason: "nenhum",
          },
        },
      ]),
    });
  });

  await page.goto("/suporte");
  await page.getByRole("button", { name: "Abrir chat" }).click();

  await page.locator('input[type="file"]').setInputFiles({
    name: "desconhecido.png",
    mimeType: "image/png",
    buffer: Buffer.from(PNG_1X1_BASE64, "base64"),
  });
  await page.getByRole("button", { name: "Enviar", exact: true }).click();

  await expect(page.getByText("Não identifiquei o produto.")).toBeVisible();
});
