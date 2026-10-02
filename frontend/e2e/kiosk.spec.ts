import { expect, test, type Page } from "@playwright/test";

/**
 * Terminal de ponto de ponta a ponta, com câmera simulada do Chromium e o motor facial falso do backend
 * (a imagem da câmera simulada corresponde sempre à mesma "pessoa").
 */

async function loginAdmin(page: Page) {
  await page.goto("/login");
  await page.getByLabel("E-mail").fill("admin@e2e.com");
  await page.getByLabel("Senha").fill("senha-e2e-segura");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Funcionários" })).toBeVisible();
}

test("cadastro do rosto e batida no terminal", async ({ page, context }) => {
  page.on("dialog", (dialog) => void dialog.accept());
  await loginAdmin(page);

  // Funcionário que trabalha todos os dias, para o teste não depender do dia da semana.
  await page.getByRole("button", { name: "Novo funcionário" }).click();
  const form = page.getByRole("dialog", { name: "Novo funcionário" });
  await form.getByLabel("Nome").fill("Rosa Terminal");
  await form.getByLabel("Matrícula").fill("K1");
  await form.getByLabel("Data de admissão").fill("2020-01-01");
  await form.getByText("Sáb", { exact: true }).click();
  await form.getByText("Dom", { exact: true }).click();
  await form.getByLabel("Entrada").fill("06:00");
  await form.getByLabel("Saída").fill("22:00");
  await form.getByLabel("Tempo de almoço (min)").fill("60");
  await form.getByRole("button", { name: "Cadastrar" }).click();
  await expect(page.getByRole("heading", { name: "Rosa Terminal" })).toBeVisible();

  // Biometria: consentimento antes, depois as fotos pela câmera.
  await expect(page.getByText("Não cadastrado")).toBeVisible();
  await page.getByRole("button", { name: "Registrar consentimento" }).click();
  await page.getByRole("button", { name: "Cadastrar rosto" }).click();
  const capture = page.getByRole("dialog", { name: "Cadastrar rosto" });
  await capture.getByRole("button", { name: "Tirar foto" }).click();
  await expect(capture.getByText("Fotos cadastradas: 1 de 5")).toBeVisible();
  await capture.getByRole("button", { name: "Concluir" }).click();
  await expect(page.getByText("Pronto para bater ponto")).toBeVisible();

  // Terminal cadastrado na administração.
  await page.getByRole("link", { name: "Administração" }).click();
  await page.getByRole("tab", { name: "Terminais" }).click();
  await page.getByLabel("Nome do terminal").fill("Entrada principal");
  await page.getByRole("button", { name: "Cadastrar terminal" }).click();
  const token = (await page.locator("code").textContent())?.trim() ?? "";
  expect(token.length).toBeGreaterThan(30);

  // O terminal roda em outra aba, sem sessão de administrador.
  const kiosk = await context.newPage();
  const cspErrors: string[] = [];
  kiosk.on("console", (msg) => {
    if (msg.type() === "error" && /Content Security Policy|wasm/i.test(msg.text())) cspErrors.push(msg.text());
  });
  await kiosk.goto("/kiosk");
  await kiosk.getByLabel("Chave do terminal").fill("chave-errada");
  await kiosk.getByRole("button", { name: "Ativar terminal" }).click();
  await expect(kiosk.getByRole("alert")).toContainText("Chave inválida");
  await kiosk.getByLabel("Chave do terminal").fill(token);
  await kiosk.getByRole("button", { name: "Ativar terminal" }).click();
  await expect(kiosk.getByText("Ponto — Entrada principal")).toBeVisible();
  // O detector do navegador (MediaPipe, servido localmente) carregou: a câmera simulada não tem rosto.
  await expect(kiosk.getByText("Posicione o rosto na moldura")).toBeVisible({ timeout: 20_000 });
  expect(cspErrors).toEqual([]);

  // Identificação: só os botões permitidos ficam habilitados.
  await kiosk.getByRole("button", { name: "Identificar" }).click();
  await expect(kiosk.getByRole("heading", { name: "Rosa Terminal" })).toBeVisible();
  await expect(kiosk.getByRole("button", { name: "Entrada" })).toBeEnabled();
  await expect(kiosk.getByRole("button", { name: "Saída", exact: true })).toBeDisabled();
  await kiosk.getByRole("button", { name: "Entrada" }).click();
  await expect(kiosk.getByRole("status")).toContainText("Entrada registrada às");

  // Um toque na confirmação libera o terminal na hora para o próximo colega (sem ele, some em 2,5 s).
  await kiosk.getByRole("status").click();
  await expect(kiosk.getByRole("button", { name: "Identificar" })).toBeVisible({ timeout: 1_000 });

  // Consulta do próprio banco de horas.
  await kiosk.getByRole("button", { name: "Identificar" }).click();
  await expect(kiosk.getByRole("button", { name: "Entrada" })).toBeDisabled();
  await kiosk.getByRole("button", { name: "Ver meu banco de horas" }).click();
  await expect(kiosk.getByText("Saldo do banco")).toBeVisible();
  await expect(kiosk.getByRole("heading", { name: "Rosa Terminal" })).toBeVisible();
  await kiosk.getByRole("button", { name: "Sair" }).click();

  // A batida aparece no histórico do administrador, com origem Terminal.
  await page.getByRole("link", { name: "Histórico" }).click();
  await expect(page.locator("tr", { hasText: "Rosa Terminal" }).first()).toContainText("Terminal");
});
