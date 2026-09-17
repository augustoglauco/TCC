import { expect, test } from "@playwright/test";

// MVP: mocka a resposta de POST /api/chat/messages em vez de depender do
// backend/modelo local real (Ollama) estar rodando — cobre o fluxo da UI
// (abrir widget, enviar, exibir resposta/erro); a integração real com o
// backend fica para os testes de integração ponta a ponta da Fase 9 (ver
// docs/ROADMAP.md).
//
// O corpo mockado é o contrato real de streaming SSE (`text/event-stream`,
// blocos `event:`/`data:`), não mais o JSON síncrono antigo — ver
// `docs/FRONTEND.md` §4.

function sseBody(events: Array<{ event: string; data: unknown }>): string {
  return (
    events.map(({ event, data }) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join("")
  );
}

test("envia mensagem de texto e exibe a resposta do assistente", async ({ page }) => {
  await page.route("**/api/chat/messages", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: sseBody([
        { event: "conversation", data: { conversation_id: "e2e-conversation-id" } },
        { event: "token", data: { text: "Posso ajudar a agendar sua visita." } },
        {
          event: "done",
          data: { domain: "agendamento", backend_used: "local", escalation_reason: "nenhum" },
        },
      ]),
    });
  });

  await page.goto("/suporte");
  await page.getByRole("button", { name: "Abrir chat" }).click();

  await page.getByLabel("Mensagem").fill("Quero agendar uma visita");
  await page.getByRole("button", { name: "Enviar" }).click();

  await expect(page.getByText("Posso ajudar a agendar sua visita.")).toBeVisible();
  await expect(page.getByTestId("message-domain-label")).toHaveText("Agendamento");
});

test("mostra erro com opção de tentar novamente quando a API falha", async ({ page }) => {
  let attempts = 0;
  await page.route("**/api/chat/messages", async (route) => {
    attempts += 1;
    if (attempts === 1) {
      await route.fulfill({ status: 503, contentType: "application/json", body: "{}" });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: sseBody([
        { event: "conversation", data: { conversation_id: "e2e-conversation-id" } },
        { event: "token", data: { text: "Agora funcionou." } },
        {
          event: "done",
          data: { domain: "agendamento", backend_used: "local", escalation_reason: "nenhum" },
        },
      ]),
    });
  });

  await page.goto("/suporte");
  await page.getByRole("button", { name: "Abrir chat" }).click();

  await page.getByLabel("Mensagem").fill("Quero agendar uma visita");
  await page.getByRole("button", { name: "Enviar" }).click();

  await expect(page.getByTestId("chat-error")).toContainText("temporariamente indisponível");

  await page.getByRole("button", { name: "Tentar novamente" }).click();

  await expect(page.getByText("Agora funcionou.")).toBeVisible();
  await expect(page.getByTestId("chat-error")).not.toBeVisible();
});

test("grava um áudio (dispositivo fake) e exibe o texto transcrito na bolha do usuário", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["microphone"]);

  await page.route("**/api/chat/messages", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: sseBody([
        { event: "conversation", data: { conversation_id: "e2e-conversation-id" } },
        { event: "transcription", data: { transcribed_message: "Quero agendar uma visita" } },
        { event: "token", data: { text: "Posso ajudar a agendar sua visita." } },
        {
          event: "done",
          data: { domain: "agendamento", backend_used: "local", escalation_reason: "nenhum" },
        },
      ]),
    });
  });

  await page.goto("/suporte");
  await page.getByRole("button", { name: "Abrir chat" }).click();

  await page.getByRole("button", { name: "Gravar áudio" }).click();
  await expect(page.getByRole("button", { name: "Parar gravação" })).toBeVisible();

  await page.getByRole("button", { name: "Parar gravação" }).click();

  await expect(page.getByText("Quero agendar uma visita")).toBeVisible();
  await expect(page.getByText("Posso ajudar a agendar sua visita.")).toBeVisible();
});
