# Frontend — Sistema de Ponto

React + TypeScript + Vite + Tailwind CSS + React Router + TanStack Query. Interface em português.
Arquitetura em `../ARCHITECTURE.md`.

## Desenvolvimento

Com o backend rodando em `http://localhost:8000` (ver `../backend/README.md`):

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173 — /api é encaminhado ao backend
```

## Qualidade e testes

```bash
npm run lint
npm run typecheck
npm test               # Vitest (unitários e componentes)
npm run build

# E2E (Playwright) com backend e frontend reais. O banco indicado é APAGADO a cada execução.
E2E_DATABASE_URL=postgresql+psycopg://ponto:SENHA@localhost:5432/ponto_e2e npm run e2e
# Testar o build servido pelo nginx em vez do Vite:
E2E_BASE_URL=http://localhost:8080 E2E_DATABASE_URL=... npm run e2e
# Capturas de tela para revisão visual:
SCREENSHOTS_DIR=/tmp/telas E2E_DATABASE_URL=... npx playwright test e2e/screenshots.spec.ts
```

## Tipos da API

Os tipos em `src/api/schema.d.ts` são gerados do OpenAPI do backend. Depois de mudar a API:

```bash
npm run gen:api
```

## Regras

* Nenhum cálculo de jornada no frontend: saldos, cargas e status vêm prontos do backend.
* O token de acesso fica só em memória; a sessão é recuperada pelo cookie `HttpOnly` de refresh.
* Datas e horas são exibidas como a API devolve (fuso da empresa), sem conversão pelo fuso do navegador.
