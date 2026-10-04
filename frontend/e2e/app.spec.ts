import { expect, test, type Page } from "@playwright/test";

/** Data local no formato AAAA-MM-DD, deslocada em `days` dias a partir de hoje. */
function isoDay(days = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

async function login(page: Page) {
  await page.goto("/funcionarios");
  await expect(page).toHaveURL(/\/login/);
  await page.getByLabel("E-mail").fill("admin@e2e.com");
  await page.getByLabel("Senha").fill("senha-e2e-segura");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Funcionários" })).toBeVisible();
}

test("login errado mostra mensagem", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("E-mail").fill("admin@e2e.com");
  await page.getByLabel("Senha").fill("senha-errada-123");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("alert")).toContainText("Credenciais inválidas");
});

test("fluxo do administrador: cadastro, histórico, banco de horas e administração", async ({ page }) => {
  await login(page);

  // Cadastro: nome, dias, horário fixo e tempo de almoço.
  await page.getByRole("button", { name: "Novo funcionário" }).click();
  const dialog = page.getByRole("dialog", { name: "Novo funcionário" });
  await dialog.getByLabel("Nome").fill("João da Silva");
  await dialog.getByLabel("Matrícula").fill("100");
  await dialog.getByLabel("Data de admissão").fill(isoDay(-40));
  await dialog.getByLabel("Dia do pagamento").fill("5");
  await dialog.getByText("Sáb", { exact: true }).click(); // segunda a sábado
  await dialog.getByLabel("Entrada").fill("08:00");
  await dialog.getByLabel("Saída").fill("16:00");
  await dialog.getByLabel("Tempo de almoço (min)").fill("30");
  await dialog.getByRole("button", { name: "Cadastrar" }).click();

  await expect(page.getByRole("heading", { name: "João da Silva" })).toBeVisible();
  const scheduleRows = page.locator("table tbody tr");
  await expect(scheduleRows).toHaveCount(6);
  await expect(scheduleRows.first()).toContainText("08:00");
  await expect(scheduleRows.first()).toContainText("7h30"); // 8 h - 30 min de almoço, calculado pelo backend
  await expect(page.getByText("Dia do pagamento: 5")).toBeVisible();
  await expect(page.getByText("Ciclo atual:")).toBeVisible();

  // Validação vinda do backend: almoço maior que o turno.
  await page.getByRole("button", { name: "Alterar horário" }).click();
  const scheduleDialog = page.getByRole("dialog", { name: "Alterar horário" });
  await scheduleDialog.getByLabel("Tempo de almoço (min)").fill("600");
  await scheduleDialog.getByRole("button", { name: "Salvar horário" }).click();
  await expect(scheduleDialog.getByRole("alert")).toContainText("almoço");
  await scheduleDialog.getByRole("button", { name: "Cancelar" }).click();

  // Histórico: inclui entrada e saída esquecidas de ontem.
  await page.getByRole("link", { name: "Histórico" }).click();
  await expect(page.getByRole("heading", { name: "Histórico de batidas" })).toBeVisible();
  for (const [type, time] of [
    ["Entrada", "08:00"],
    ["Saída", "17:00"],
  ] as const) {
    await page.getByRole("button", { name: "Incluir batida esquecida" }).click();
    const add = page.getByRole("dialog", { name: "Incluir batida esquecida" });
    await add.getByLabel("Funcionário").selectOption({ label: "João da Silva (100)" });
    await add.getByLabel("Tipo").selectOption({ label: type });
    await add.getByLabel("Data", { exact: true }).fill(isoDay(-1));
    await add.getByLabel("Hora").fill(time);
    await add.getByLabel("Justificativa").fill("Funcionário esqueceu de bater o ponto");
    await add.getByRole("button", { name: "Incluir" }).click();
    await expect(add).toBeHidden();
  }
  await page.getByRole("button", { name: "Período" }).click();
  await page.getByLabel("Data inicial").fill(isoDay(-1));
  await page.getByLabel("Data final").fill(isoDay(-1));
  const rows = page.locator("table tbody tr");
  await expect(rows).toHaveCount(2);
  await expect(rows.first()).toContainText("17:00");
  await expect(rows.first()).toContainText("Ajuste");

  // Anular a saída: some da lista padrão.
  await rows.first().getByRole("button", { name: "Detalhes" }).click();
  const detail = page.getByRole("dialog", { name: "Detalhes da batida" });
  await expect(detail).toContainText("Funcionário esqueceu de bater o ponto");
  await detail.getByLabel("Justificativa").fill("Horário de saída informado errado");
  await detail.getByRole("button", { name: "Anular" }).click();
  await detail.getByRole("button", { name: "Fechar" }).click();
  await expect(rows).toHaveCount(1);

  // Banco de horas: resumo de todos e detalhe do funcionário.
  await page.getByRole("link", { name: "Banco de horas" }).click();
  await expect(page.getByRole("heading", { name: "Banco de horas", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "João da Silva" })).toBeVisible();
  await page.getByRole("link", { name: "João da Silva" }).click();
  await expect(page.getByRole("heading", { name: /Banco de horas — João da Silva/ })).toBeVisible();
  await expect(page.getByText("Saldo final")).toBeVisible();
  await page.getByRole("button", { name: "Período" }).click();
  await page.getByLabel("Data inicial").fill(isoDay(-1));
  await page.getByLabel("Data final").fill(isoDay(-1));
  await expect(page.getByText("Incompleto").first()).toBeVisible(); // ontem ficou só com a entrada

  // Pagamento: horas do ciclo, em decimal para multiplicar pelo valor da hora.
  await page.getByRole("link", { name: "Pagamento" }).click();
  await expect(page.getByRole("heading", { name: "Pagamento" })).toBeVisible();
  const payRow = page.locator("tr", { hasText: "João da Silva" });
  await expect(payRow.getByTestId("payable")).toContainText(/\d+,\d{2} h/);
  await payRow.getByRole("link", { name: "Detalhe" }).click();
  await expect(page.getByRole("heading", { name: /Banco de horas — João da Silva/ })).toBeVisible();
  await expect(page.getByLabel("Data inicial")).toBeVisible(); // período do ciclo já aplicado

  // Administração: feriado e terminal (chave exibida uma única vez).
  await page.getByRole("link", { name: "Administração" }).click();
  await expect(page.getByRole("heading", { name: "Administração" })).toBeVisible();
  await page.getByLabel("Data", { exact: true }).fill(`${new Date().getFullYear()}-12-25`);
  await page.getByLabel("Nome", { exact: true }).fill("Natal");
  await page.getByLabel("Repete todo ano").check();
  await page.getByRole("button", { name: "Adicionar" }).click();
  await expect(page.getByText("25/12 — Natal")).toBeVisible();

  await page.getByRole("tab", { name: "Terminais" }).click();
  await page.getByLabel("Nome do terminal").fill("Recepção");
  await page.getByRole("button", { name: "Cadastrar terminal" }).click();
  await expect(page.getByRole("status")).toContainText("copie agora");

  await page.getByRole("tab", { name: "Auditoria" }).click();
  await expect(page.getByText("device.create")).toBeVisible();

  // Consumo: item com preço e lançamento na ficha do funcionário, descontado no pagamento.
  await page.getByRole("tab", { name: "Consumo" }).click();
  await page.getByLabel("Nome", { exact: true }).fill("Refrigerante lata");
  await page.getByLabel("Preço (R$)").fill("6,00");
  await page.getByRole("button", { name: "Adicionar item" }).click();
  await expect(page.getByText(/Refrigerante lata — R\$\s6,00/)).toBeVisible();

  await page.getByRole("link", { name: "Funcionários" }).click();
  await page.getByRole("link", { name: "João da Silva" }).click();
  await page.getByLabel("Item").selectOption({ label: "Refrigerante lata — R$\u00a06,00" });
  await page.getByLabel("Qtd.").fill("2");
  await page.getByRole("button", { name: "Lançar consumo" }).click();
  await expect(page.getByText(/Total do ciclo: R\$\s12,00/)).toBeVisible();
  await expect(page.getByText(/Descontar consumo: R\$\s12,00/)).toBeVisible();
  await page.getByRole("link", { name: "Administração" }).click();

  // Sessão sobrevive a recarregar a página (cookie de refresh) e termina ao sair.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Administração" })).toBeVisible();
  await page.getByRole("button", { name: "Sair" }).click();
  await page.goto("/funcionarios");
  await expect(page).toHaveURL(/\/login/);
});
