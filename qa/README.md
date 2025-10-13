# ADinsights QA Playwright Suite

This package houses end-to-end smoke tests for the ADinsights dashboard shell. The suite assumes the React frontend runs in mock mode by default while still allowing real API calls when a backend is available.

## Prerequisites
- Node.js 18+
- npm 9+

## Installation & Local Usage

```bash
cd qa
npm ci
npm run setup          # installs Playwright browsers
npm run setup:deps     # optional: installs Chromium system deps on Linux
npx playwright install-deps  # optional on fresh Linux machines
npm test
```

### Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `MOCK_MODE` | `true` | When `true`, tests stub API health and export endpoints to avoid requiring the Django backend. Set to `false` to exercise live APIs. |
| `QA_PORT` | `4173` | Port used for the ephemeral Vite dev server started by Playwright. |
| `QA_BASE_URL` | — | Override the computed base URL (useful when pointing to an already running frontend). |

When `MOCK_MODE=false`, ensure the backend is running and reachable from the test environment. The suite expects `/api/health/`, `/api/health/airbyte/`, `/api/health/dbt/`, and `/api/metrics/export/?format=csv` to respond with production-formatted payloads.

## Running Specific Tests

```bash
npm test -- --grep "health"
```

Refer to the [Playwright CLI docs](https://playwright.dev/docs/test-cli) for additional options such as headed mode (`npm run test:headed`) or tracing (`npx playwright show-trace <trace.zip>`). If you see errors about missing Chromium libraries on Linux, run `npm run setup:deps` (or `npx playwright install-deps chromium`) once—this pulls the required packages without checking them into source control.
