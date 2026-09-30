import { expect, test } from "@playwright/test";

// MVP: mocka login, catálogo de produtos e pedidos em vez de depender do
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

const PRODUTO = {
  id: 1,
  nome: "Gerador Diesel GD-15",
  descricao: "Gerador a diesel de 15 kVA, ideal para pequenos comércios e obras.",
  preco: 24900,
  categoria: "geradores",
  imagem_url: null,
  estoques: [
    {
      id: "e1",
      centro_distribuicao: "CD-SP",
      quantidade: 10,
      atualizado_em: new Date().toISOString(),
    },
  ],
  imagens: [],
};

const ORDER_RESPONSE = {
  id: "pedido-e2e-1",
  status: "reservado",
  criado_em: new Date().toISOString(),
  user_email: LOGIN_RESPONSE.user.email,
  itens: [
    {
      produto_id: 1,
      nome_produto: "Gerador Diesel GD-15",
      quantidade: 1,
      centro_distribuicao: "CD-SP",
      preco_unitario: 24900,
      subtotal: 24900,
    },
  ],
  valor_total: 24900,
};

async function fazerLogin(page: import("@playwright/test").Page) {
  await page.route("**/api/auth/login", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(LOGIN_RESPONSE),
    });
  });
  await page.route("**/api/orders**", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(ORDER_RESPONSE),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [], total: 0, limit: 10, offset: 0 }),
    });
  });

  await page.goto("/conta/login");
  await page.getByLabel("Endereço de E-mail").fill(LOGIN_RESPONSE.user.email);
  await page.getByLabel("Senha de Acesso").fill("12345");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page).toHaveURL(/\/conta\/perfil/);
}

test("finaliza um pedido a partir do carrinho pré-preenchido por link de produto", async ({
  page,
}) => {
  await fazerLogin(page);

  await page.route("**/api/products/1", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(PRODUTO),
    });
  });
  await page.route("**/api/products?*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [PRODUTO], total: 1, limit: 50, offset: 0 }),
    });
  });

  // `?produto=1` reproduz o link "Comprar" da ficha do produto: adiciona o
  // item ao carrinho automaticamente ao carregar a página (ver
  // `app/pedidos/page.tsx`).
  await page.goto("/pedidos?produto=1");

  await expect(page.getByText("Gerador Diesel GD-15")).toBeVisible();

  await page.getByRole("button", { name: "Finalizar Pedido & Reservar" }).click();

  await expect(page.getByText("Pedido Reservado com Sucesso!")).toBeVisible();
  await expect(page.getByText(ORDER_RESPONSE.id)).toBeVisible();
});

test("exige login antes de acessar o carrinho e pedidos", async ({ page }) => {
  await page.goto("/pedidos");

  await expect(page.getByText("Autenticação Necessária")).toBeVisible();
  await expect(page.getByRole("link", { name: /Entrar na Conta/ })).toBeVisible();
});
