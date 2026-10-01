import { expect, test } from "@playwright/test";

// Capturas do terminal e da biometria para revisão visual. Só roda com SCREENSHOTS_DIR definido.
const dir = process.env.SCREENSHOTS_DIR;
test.skip(!dir, "defina SCREENSHOTS_DIR para gerar as capturas");

test("capturas do terminal", async ({ page, context }) => {
  page.on("dialog", (d) => void d.accept());
  await page.setViewportSize({ width: 1280, height: 860 });
  await page.goto("/login");
  await page.getByLabel("E-mail").fill("admin@e2e.com");
  await page.getByLabel("Senha").fill("senha-e2e-segura");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Funcionários" })).toBeVisible();
  const token = await page.evaluate(async () => {
    const r = await fetch("/api/v1/auth/refresh", { method: "POST" });
    return ((await r.json()) as { access_token: string }).access_token;
  });
  const headers = { Authorization: `Bearer ${token}` };
  const created = await page.request.post("/api/v1/employees", {
    headers,
    data: {
      name: "João da Silva",
      registration_number: "100",
      hire_date: "2026-01-01",
      payday: 5,
      schedule: { weekdays: [0, 1, 2, 3, 4, 5, 6], start_time: "06:00", end_time: "22:00" },
    },
  });
  const employee = ((await created.json()) as { id: number }).id;
  await page.goto(`/funcionarios/${employee}`);
  await page.getByRole("button", { name: "Registrar consentimento" }).click();
  await page.getByRole("button", { name: "Cadastrar rosto" }).click();
  await page.screenshot({ path: `${dir}/09-cadastro-rosto.png` });
  await page.getByRole("button", { name: "Tirar foto" }).click();
  await expect(page.getByText("Fotos cadastradas: 1 de 5")).toBeVisible();
  await page.getByRole("button", { name: "Concluir" }).click();
  await expect(page.getByText("Pronto para bater ponto")).toBeVisible();
  await page.getByText("Pronto para bater ponto").scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${dir}/10-ficha-com-rosto.png`, fullPage: true });

  const device = await page.request.post("/api/v1/devices", { headers, data: { name: "Recepção" } });
  const deviceToken = ((await device.json()) as { token: string }).token;

  const kiosk = await context.newPage();
  await kiosk.setViewportSize({ width: 1024, height: 768 });
  await kiosk.goto("/kiosk");
  await kiosk.screenshot({ path: `${dir}/11-terminal-configurar.png` });
  await kiosk.getByLabel("Chave do terminal").fill(deviceToken);
  await kiosk.getByRole("button", { name: "Ativar terminal" }).click();
  await expect(kiosk.getByText("Posicione o rosto na moldura")).toBeVisible({ timeout: 20_000 });
  await kiosk.screenshot({ path: `${dir}/12-terminal-camera.png` });
  await kiosk.getByRole("button", { name: "Identificar" }).click();
  await expect(kiosk.getByRole("heading", { name: "João da Silva" })).toBeVisible();
  await kiosk.screenshot({ path: `${dir}/13-terminal-botoes.png` });
  await kiosk.getByRole("button", { name: "Entrada" }).click();
  await expect(kiosk.getByRole("status")).toBeVisible();
  await kiosk.screenshot({ path: `${dir}/14-terminal-confirmacao.png` });
  await expect(kiosk.getByRole("button", { name: "Identificar" })).toBeVisible({ timeout: 10_000 });
  await kiosk.getByRole("button", { name: "Identificar" }).click();
  await kiosk.getByRole("button", { name: "Ver meu banco de horas" }).click();
  await expect(kiosk.getByText("Saldo do banco")).toBeVisible();
  await kiosk.screenshot({ path: `${dir}/15-terminal-banco.png` });
});
