import { expect, test } from "@playwright/test";

// MVP: mocka POST /api/auth/login e GET /api/orders (chamado pela página de
// perfil ao montar, para o histórico de pedidos) em vez de depender do
// backend real — mesmo espírito de `chat.spec.ts` (ver docs/FRONTEND.md §6).

const LOGIN_RESPONSE = {
  token: "mock-token-1",
  user: {
    id: 1,
    email: "ana.recorrente@example.com",
    nome: "Ana Recorrente",
    perfil: "Cliente",
    perfil_motivo: "3 compras recentes",
  },
};

test.beforeEach(async ({ page }) => {
  await page.route("**/api/orders**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [], total: 0, limit: 10, offset: 0 }),
    });
  });
});

test("faz login manual e é redirecionado para o perfil", async ({ page }) => {
  await page.route("**/api/auth/login", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(LOGIN_RESPONSE),
    });
  });

  await page.goto("/conta/login");
  await page.getByLabel("Endereço de E-mail").fill(LOGIN_RESPONSE.user.email);
  await page.getByLabel("Senha de Acesso").fill("12345");
  await page.getByRole("button", { name: "Entrar" }).click();

  await expect(page).toHaveURL(/\/conta\/perfil/);
  await expect(page.getByRole("heading", { name: "Ana Recorrente" })).toBeVisible();
  await expect(page.getByText(LOGIN_RESPONSE.user.email)).toBeVisible();
});

test("login rápido com conta de demonstração", async ({ page }) => {
  await page.route("**/api/auth/login", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(LOGIN_RESPONSE),
    });
  });

  await page.goto("/conta/login");
  await page.getByRole("button", { name: /Ana Recorrente/ }).click();

  await expect(page).toHaveURL(/\/conta\/perfil/);
  await expect(page.getByRole("heading", { name: "Ana Recorrente" })).toBeVisible();
});

test("mostra erro quando a senha está incorreta e permanece na página", async ({ page }) => {
  await page.route("**/api/auth/login", async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({
        detail: "Senha de demonstração incorreta. Utilize a senha padrão: 12345.",
      }),
    });
  });

  await page.goto("/conta/login");
  await page.getByLabel("Endereço de E-mail").fill(LOGIN_RESPONSE.user.email);
  await page.getByLabel("Senha de Acesso").fill("errada");
  await page.getByRole("button", { name: "Entrar" }).click();

  await expect(page.getByText("Senha de demonstração incorreta")).toBeVisible();
  await expect(page).toHaveURL(/\/conta\/login/);
});
