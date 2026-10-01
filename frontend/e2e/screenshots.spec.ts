import { expect, test } from "@playwright/test";

// Capturas de tela para revisão visual. Só roda com SCREENSHOTS_DIR definido.
const dir = process.env.SCREENSHOTS_DIR;
test.skip(!dir, "defina SCREENSHOTS_DIR para gerar as capturas");

function isoDay(days = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

test("capturas das telas", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 860 });
  await page.goto("/login");
  await page.screenshot({ path: `${dir}/01-login.png` });
  await page.getByLabel("E-mail").fill("admin@e2e.com");
  await page.getByLabel("Senha").fill("senha-e2e-segura");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Funcionários" })).toBeVisible();

  const token = await page.evaluate(async () => {
    const r = await fetch("/api/v1/auth/refresh", { method: "POST" });
    return ((await r.json()) as { access_token: string }).access_token;
  });
  const headers = { Authorization: `Bearer ${token}` };
  for (const [name, reg, start, end] of [
    ["João da Silva", "100", "08:00", "16:00"],
    ["Maria Souza", "101", "09:00", "18:00"],
    ["Carlos Lima", "102", "22:00", "06:00"],
  ]) {
    await page.request.post("/api/v1/employees", {
      headers,
      data: {
        name,
        registration_number: reg,
        hire_date: isoDay(-20),
        payday: 5,
        schedule: { start_time: start, end_time: end },
      },
    });
  }
  const add = (type: string, day: number, time: string, employee = 1) =>
    page.request.post("/api/v1/time-records/adjustments", {
      headers,
      data: {
        kind: "ADD",
        employee_id: employee,
        type,
        recorded_at: `${isoDay(day)}T${time}`,
        reason: "Dados de exemplo para captura de tela",
      },
    });
  for (const day of [-3, -2, -1]) {
    await add("ENTRY", day, day === -2 ? "08:20" : "07:58");
    await add("LUNCH_EXIT", day, "12:00");
    await add("LUNCH_RETURN", day, "13:00");
    await add("EXIT", day, day === -1 ? "17:30" : "16:02");
  }

  await page.reload();
  await expect(page.getByRole("link", { name: "João da Silva" })).toBeVisible();
  await page.screenshot({ path: `${dir}/02-funcionarios.png` });

  await page.getByRole("button", { name: "Novo funcionário" }).click();
  await page.getByLabel("Nome").fill("Ana Pereira");
  await page.screenshot({ path: `${dir}/03-cadastro.png` });
  await page.getByRole("button", { name: "Cancelar" }).click();

  await page.getByRole("link", { name: "João da Silva" }).click();
  await expect(page.getByRole("heading", { name: "João da Silva" })).toBeVisible();
  await page.screenshot({ path: `${dir}/04-funcionario.png`, fullPage: true });

  await page.getByRole("link", { name: "Histórico" }).click();
  await expect(page.locator("table tbody tr").first()).toBeVisible();
  await page.screenshot({ path: `${dir}/05-historico.png`, fullPage: true });

  await page.goto("/banco-de-horas/1");
  await page.getByRole("button", { name: "Período" }).click();
  await page.getByLabel("Data inicial").fill(isoDay(-6));
  await page.getByLabel("Data final").fill(isoDay(0));
  await expect(page.getByText("Saldo final")).toBeVisible();
  await page.screenshot({ path: `${dir}/06-banco-de-horas.png`, fullPage: true });

  await page.goto("/pagamento");
  await expect(page.locator("tr", { hasText: "João da Silva" })).toBeVisible();
  await page.screenshot({ path: `${dir}/08-pagamento.png`, fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/funcionarios");
  await expect(page.getByRole("link", { name: "João da Silva" })).toBeVisible();
  await page.screenshot({ path: `${dir}/07-celular.png`, fullPage: true });
});
