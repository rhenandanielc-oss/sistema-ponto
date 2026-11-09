import { expect, test, type Page } from "@playwright/test";

/** Link de ativação de uso único e trava por localização (BUSINESS-RULES.md §4.7). */

async function loginAdmin(page: Page) {
  await page.goto("/login");
  await page.getByLabel("E-mail").fill("admin@e2e.com");
  await page.getByLabel("Senha").fill("senha-e2e-segura");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Funcionários" })).toBeVisible();
}

test("link de ativação de uso único e terminal com localização exigida", async ({ page, context }) => {
  page.on("dialog", (dialog) => void dialog.accept());
  await loginAdmin(page);

  // Local do restaurante nas configurações.
  await page.getByRole("link", { name: "Administração" }).click();
  await page.getByRole("tab", { name: "Configurações" }).click();
  await page.getByLabel("Local do restaurante: latitude").fill("-23.55052");
  await page.getByLabel("Local do restaurante: longitude").fill("-46.63331");
  await page.getByLabel("Raio permitido (m)").fill("150");
  await page.getByRole("button", { name: "Salvar configurações" }).click();
  await expect(page.getByText("Configurações salvas.")).toBeVisible();

  // Terminal que exige localização, ativado só pelo link.
  await page.getByRole("tab", { name: "Terminais" }).click();
  await page.getByLabel("Nome do terminal").fill("Celular da Jesi");
  await page.getByLabel("Exigir localização (celular do funcionário)").check();
  await page.getByRole("button", { name: "Cadastrar terminal" }).click();
  await expect(page.locator("tr", { hasText: "Celular da Jesi" })).toContainText("Exigida");
  await page.getByRole("button", { name: "Já copiei" }).click();
  await page.locator("tr", { hasText: "Celular da Jesi" }).getByRole("button", { name: "Link de ativação" }).click();
  const url = (await page.locator("code").textContent())?.trim() ?? "";
  expect(url).toContain("/kiosk#ativar=");

  // Celular do funcionário: abre o link e já entra no terminal, sem digitar chave.
  await context.grantPermissions(["camera", "geolocation"]);
  await context.setGeolocation({ latitude: -23.5506, longitude: -46.6334, accuracy: 20 });
  const phone = await context.newPage();
  await phone.goto(url);
  await expect(phone.getByText("Ponto — Celular da Jesi")).toBeVisible();
  expect(phone.url()).not.toContain("ativar=");

  // O mesmo link não serve de novo (nem em outro navegador/aba sem o token).
  const other = await (await context.browser()!.newContext({ baseURL: undefined })).newPage();
  await other.goto(url);
  await expect(other.getByRole("alert")).toContainText(/inválido ou vencido/);
  await other.context().close();
});
