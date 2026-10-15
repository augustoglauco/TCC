import { expect, test } from "@playwright/test";

// Cobre as mudanças de interação do widget feitas em 2026-10-14 (ver
// docs/FRONTEND.md §3): fechar o modal ao clicar num card rico com link,
// devolver o foco à caixa de mensagem e abrir o chat já na última mensagem.
//
// Por que em Playwright e não só em Vitest: os testes de unidade rodam em
// jsdom, que não tem layout — `scrollIntoView` é um mock e não existe
// "estar visível na área rolável". As asserções abaixo (`toBeInViewport`,
// `toBeFocused` depois de um `requestAnimationFrame`, navegação real do
// `next/link`) só têm sentido num navegador de verdade.
//
// MVP: mesma abordagem do `chat.spec.ts` — a resposta de
// POST /api/chat/messages é mockada no contrato SSE real, sem depender do
// modelo local; o endpoint do produto também é mockado para a página de
// destino não depender do banco.

function sseBody(events: Array<{ event: string; data: unknown }>): string {
  return events
    .map(({ event, data }) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
    .join("");
}

const CARD_PRODUTO = {
  tipo: "produto",
  produto_id: 42,
  nome: "Gerador Diesel GD-15",
  preco: "24900.00",
  imagem_url: null,
  estoque_total: 8,
};

function respostaComCard(texto: string, card?: unknown) {
  return sseBody([
    { event: "conversation", data: { conversation_id: "e2e-interacao" } },
    { event: "token", data: { text: texto } },
    {
      event: "done",
      data: {
        domain: "vendas",
        backend_used: "local",
        escalation_reason: "nenhum",
        ...(card ? { card } : {}),
      },
    },
  ]);
}

test("clicar no card rico de produto navega e fecha o modal do chat", async ({ page }) => {
  await page.route("**/api/chat/messages", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: respostaComCard("Temos esse gerador em estoque.", CARD_PRODUTO),
    });
  });
  await page.route("**/api/products/42", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: 42,
        nome: "Gerador Diesel GD-15",
        descricao: "Gerador a diesel de 15 kVA.",
        categoria: "Geradores",
        preco: "24900.00",
        estoque_total: 8,
        imagens: [],
      }),
    });
  });

  await page.goto("/suporte");
  await page.getByRole("button", { name: "Abrir chat" }).click();

  await page.getByLabel("Mensagem").fill("Tem gerador de 15 kVA?");
  await page.getByRole("button", { name: "Enviar", exact: true }).click();

  const card = page.getByRole("link", { name: /Gerador Diesel GD-15/ });
  await expect(card).toBeVisible();
  await card.click();

  // O ChatWidget vive no layout raiz, então o modal sobrevive à navegação do
  // next/link se ninguém o fechar — era o bug.
  await expect(page).toHaveURL(/\/produtos\/42$/);
  await expect(page.getByLabel("Mensagem")).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Abrir chat" })).toBeVisible();
});

test("o foco volta à caixa de mensagem depois de enviar", async ({ page }) => {
  await page.route("**/api/chat/messages", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: respostaComCard("Posso ajudar com mais alguma coisa?"),
    });
  });

  await page.goto("/suporte");
  await page.getByRole("button", { name: "Abrir chat" }).click();

  const caixa = page.getByLabel("Mensagem");
  await caixa.fill("Bom dia");
  // Clicar no botão move o foco para o botão, e o <input> ainda fica disabled
  // enquanto a resposta chega: só pode voltar quando os controles reabrem.
  await page.getByRole("button", { name: "Enviar", exact: true }).click();

  await expect(page.getByText("Posso ajudar com mais alguma coisa?")).toBeVisible();
  await expect(caixa).toBeFocused();
});

test("abrir o chat mostra a última mensagem, não o topo da conversa", async ({ page }) => {
  let n = 0;
  await page.route("**/api/chat/messages", async (route) => {
    n += 1;
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: respostaComCard(
        `Resposta ${n}. ` + "Texto longo o suficiente para empurrar a conversa. ".repeat(4),
      ),
    });
  });

  await page.goto("/suporte");
  await page.getByRole("button", { name: "Abrir chat" }).click();

  const caixa = page.getByLabel("Mensagem");
  for (let i = 1; i <= 6; i += 1) {
    await caixa.fill(`Pergunta ${i} com texto suficiente para ocupar espaço na lista`);
    await page.getByRole("button", { name: "Enviar", exact: true }).click();
    await expect(page.getByText(`Resposta ${i}.`)).toBeVisible();
  }

  // Fecha e reabre: as mensagens continuam no store (zustand em memória), e é
  // na reabertura que o salto para o fim tem de acontecer. O botão flutuante
  // do `ChatWidget` ("Fechar chat") não serve aqui: com o modal aberto ele
  // fica fora da árvore de acessibilidade e `getByRole` não o encontra —
  // fecha-se pelo "Fechar" do próprio `components/ui/Modal.tsx`.
  await page.getByRole("button", { name: "Fechar", exact: true }).click();
  await expect(caixa).not.toBeVisible();
  await page.getByRole("button", { name: "Abrir chat" }).click();

  await expect(page.getByText("Resposta 6.")).toBeInViewport();
  await expect(page.getByText("Pergunta 1 com texto")).not.toBeInViewport();
});

test("abrir o chat foca a caixa de mensagem em ponteiro preciso", async ({ page }) => {
  // O projeto do Playwright é Desktop Chrome, logo `(pointer: fine)` casa e o
  // foco automático na abertura deve acontecer. O caso oposto (touch, em que
  // focar abriria o teclado virtual e esconderia a última mensagem) está
  // coberto só em Vitest com stub de `matchMedia`: exigiria um projeto com
  // `devices["Pixel 5"]` no playwright.config.ts, fora do escopo atual.
  await page.goto("/suporte");
  await page.getByRole("button", { name: "Abrir chat" }).click();

  await expect(page.getByLabel("Mensagem")).toBeFocused();
});
