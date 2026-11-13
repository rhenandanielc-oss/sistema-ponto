import { expect, test, type Page } from "@playwright/test";

/** Link de ativação de uso único e trava por localização (BUSINESS-RULES.md §4.7). */

async function loginAdmin(page: Page) {
  await page.goto("/login");
  await page.getByLabel("E-mail").fill("admin@e2e.com");
  await page.getByLabel("Senha").fill("senha-e2e-segura");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Funcionários" })).toBeVisible();
}

test("link de ativação permanente e terminal com localização exigida", async ({ page, context }) => {
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
  await page.locator("tr", { hasText: "Celular da Jesi" }).getByRole("button", { name: "Ver link" }).click();
  const url = (await page.locator("code").textContent())?.trim() ?? "";
  expect(url).toContain("/kiosk#ativar=");

  // Celular do funcionário: abre o link e já entra no terminal, sem digitar chave.
  await context.grantPermissions(["camera", "geolocation"]);
  await context.setGeolocation({ latitude: -23.5506, longitude: -46.6334, accuracy: 20 });
  const phone = await context.newPage();
  await phone.goto(url);
  await expect(phone.getByText("Ponto — Celular da Jesi")).toBeVisible();
  expect(phone.url()).toContain("ativar="); // o código fica no endereço: favorito e atalho entram direto

  // O link é permanente: abre de novo (e em outro navegador) e entra no terminal do mesmo jeito.
  const other = await (await context.browser()!.newContext()).newPage();
  await other.context().grantPermissions(["camera", "geolocation"], { origin: new URL(url).origin });
  await other.goto(url);
  await expect(other.getByText("Ponto — Celular da Jesi")).toBeVisible();
  await other.context().close();

  // Sem permissão de localização, o terminal avisa já ao abrir (e diz como liberar).
  const noGps = await (await context.browser()!.newContext()).newPage();
  await noGps.context().grantPermissions(["camera"], { origin: new URL(url).origin });
  await noGps.goto(url);
  await expect(noGps.getByRole("alert").filter({ hasText: /localiza/i })).toBeVisible({ timeout: 15_000 });
  await noGps.context().close();

  // "Novo link" invalida o anterior.
  await page.locator("tr", { hasText: "Celular da Jesi" }).getByRole("button", { name: "Novo link" }).click();
  await expect(page.locator("code")).not.toHaveText(url);
  const stale = await (await context.browser()!.newContext()).newPage();
  await stale.goto(url);
  await expect(stale.getByRole("alert")).toContainText(/inválido ou desativado/);
  await stale.context().close();
});
