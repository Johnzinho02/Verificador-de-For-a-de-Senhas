const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ page }) => { await page.goto("/"); });

test("analisa pelo Flask e atualiza a interface", async ({ page }) => {
  await expect(page).toHaveTitle(/FirePassJW/);
  const request = page.waitForResponse((response) => response.url().endsWith("/api/analisar"));
  await page.getByLabel("Senha para analisar").fill("rT7!vK9@pL2#xN5$");
  expect((await request).status()).toBe(200);
  await expect(page.locator("#strength-label")).toHaveText("Muito forte");
  await expect(page.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "5");
  await expect(page.locator("#criteria-count")).toHaveText("5 de 5 critérios");
});

test("reconhece senha comum e mostra recomendação", async ({ page }) => {
  await page.getByLabel("Senha para analisar").fill("P@ssw0rd2026!");
  await expect(page.locator("#strength-label")).toHaveText("Muito fraca");
  await expect(page.locator("#recommendations")).toContainText("conhecidas");
});

test("mostrar, ocultar e limpar funcionam por teclado", async ({ page }) => {
  const input = page.getByLabel("Senha para analisar");
  await input.fill("rT7!vK9@pL2#xN5$");
  await input.press("Tab");
  await expect(page.getByRole("button", { name: "Mostrar senha" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(input).toHaveAttribute("type", "text");
  await input.press("Tab");
  await page.keyboard.press("Enter");
  await expect(input).toHaveAttribute("type", "password");
  await page.getByRole("button", { name: /Limpar análise/ }).click();
  await expect(input).toHaveValue("");
  await expect(page.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");
});

test("layout não exige rolagem horizontal", async ({ page }) => {
  const fits = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
  expect(fits).toBe(true);
  await expect(page.getByRole("button", { name: "Mostrar senha" })).toBeVisible();
});

test("indisponibilidade da API não mantém uma nota antiga", async ({ page }) => {
  await page.route("**/api/analisar", (route) => route.abort());
  await page.getByLabel("Senha para analisar").fill("ExemploFicticio1!");
  await expect(page.locator("#strength-label")).toHaveText("Análise indisponível");
  await expect(page.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");
});

test("corpo inválido de resposta não produz classificação", async ({ page }) => {
  await page.route("**/api/analisar", (route) => route.fulfill({
    status: 200, contentType: "application/json", body: '{"nivel":99}',
  }));
  await page.getByLabel("Senha para analisar").fill("ExemploFicticio1!");
  await expect(page.locator("#strength-label")).toHaveText("Análise indisponível");
});

test("textos principais têm contraste suficiente com o fundo", async ({ page }) => {
  const resultados = await page.evaluate(() => {
    const rgb = (cor) => cor.match(/[\d.]+/g).slice(0, 3).map(Number);
    const luminancia = (cor) => rgb(cor).map((canal) => {
      const valor = canal / 255;
      return valor <= 0.04045 ? valor / 12.92 : ((valor + 0.055) / 1.055) ** 2.4;
    }).reduce((soma, valor, i) => soma + valor * [0.2126, 0.7152, 0.0722][i], 0);
    return [...document.querySelectorAll(
      ".input-label, .tips-intro, .recommendations li, .privacy-card p, .bottom-note p, .step-label"
    )].map((elemento) => {
      let ancestral = elemento;
      while (getComputedStyle(ancestral).backgroundColor === "rgba(0, 0, 0, 0)") {
        ancestral = ancestral.parentElement;
      }
      const texto = luminancia(getComputedStyle(elemento).color);
      const fundo = luminancia(getComputedStyle(ancestral).backgroundColor);
      return (Math.max(texto, fundo) + 0.05) / (Math.min(texto, fundo) + 0.05);
    });
  });
  for (const contraste of resultados) expect(contraste).toBeGreaterThanOrEqual(4.5);
});
