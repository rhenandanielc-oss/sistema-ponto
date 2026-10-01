import { defineConfig } from "@playwright/test";

// Navegador: usa o Chromium já instalado no ambiente quando PLAYWRIGHT_CHROMIUM_PATH estiver definido.
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_PATH;
// E2E_BASE_URL permite testar o build servido pelo nginx (ex.: http://localhost:8080) em vez do Vite.
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:5173";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL,
    locale: "pt-BR",
    timezoneId: "America/Sao_Paulo",
    trace: "retain-on-failure",
    launchOptions: executablePath ? { executablePath } : {},
  },
  webServer: [
    {
      command: "./e2e/start-backend.sh",
      url: "http://127.0.0.1:8000/api/v1/health/ready",
      timeout: 120_000,
      reuseExistingServer: false,
    },
    ...(process.env.E2E_BASE_URL
      ? []
      : [
          {
            command: "npx vite --port 5173 --strictPort",
            url: "http://localhost:5173",
            timeout: 60_000,
            reuseExistingServer: false,
          },
        ]),
  ],
});
