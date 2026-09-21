import { expect, test } from "@playwright/test";

// Smoke test manual contra o backend e o modelo local (Ollama) reais — não
// mocka POST /api/chat/messages (ver tests/e2e/chat.spec.ts para os testes
// mockados/determinísticos que rodam via `npm run test:e2e`).
//
// Pré-requisitos: backend rodando em NEXT_PUBLIC_API_BASE_URL (padrão
// http://localhost:8000) com Ollama no ar e o modelo de LOCAL_MODEL_NAME
// carregado; frontend em http://localhost:3001 (`PORT=3001 npm run dev`).
//
// Rodar com: npm run test:e2e:smoke
test("mensagem de agendamento roda contra o backend/Ollama reais e responde localmente", async ({
  page,
}) => {
  await page.goto("/suporte");
  await page.getByRole("button", { name: "Abrir chat" }).click();

  await page.getByLabel("Mensagem").fill("Quero agendar uma visita para amanhã às 15h");
  await page.getByRole("button", { name: "Enviar" }).click();

  // MVP: sem asserção de texto exato — a resposta vem de um LLM real e não é
  // determinística. Só confirma que o domínio foi roteado corretamente e que
  // alguma resposta não-vazia chegou (prova a integração ponta a ponta).
  const domainLabel = page.getByTestId("message-domain-label").last();
  await expect(domainLabel).toHaveText("Agendamento", { timeout: 45_000 });

  const assistantText = domainLabel.locator("xpath=following-sibling::p");
  await expect(assistantText).not.toBeEmpty();

  await expect(page.getByTestId("chat-error")).not.toBeVisible();
});
