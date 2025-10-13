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
npm run update-snapshots  # refreshes stored visual baselines
```

Playwright starts the built frontend using `npm run preview`, so ensure `frontend` has been built (`cd ../frontend && npm run build`) before launching the suite locally.

### Local workflows

- **Mock mode (default):** No backend required. Run `npm test` to exercise the UI with mocked API calls.
- **Live API smoke tests:** Set `MOCK_MODE=false` and provide a reachable base via `LIVE_API_BASE_URL` (for example, `LIVE_API_BASE_URL=https://staging.adinsights.local`). Optionally set `QA_BASE_URL` if the frontend is already hosted elsewhere.

### Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `MOCK_MODE` | `true` | When `true`, tests stub API health and export endpoints to avoid requiring the Django backend. Set to `false` to exercise live APIs. |
| `QA_PORT` | `4173` | Port used for the ephemeral Vite dev server started by Playwright. |
| `QA_BASE_URL` | — | Override the computed base URL (useful when pointing to an already running frontend). |
| `LIVE_API_BASE_URL` | — | Required for live runs (`MOCK_MODE=false`). Tests that rely on real APIs will skip unless this is defined. |

When `MOCK_MODE=false`, ensure the backend is running and reachable from the test environment. The suite expects `/api/health/`, `/api/health/airbyte/`, `/api/health/dbt/`, and `/api/metrics/export/?format=csv` to respond with production-formatted payloads.

## Running Specific Tests

```bash
npm test -- --grep "health"
```

Refer to the [Playwright CLI docs](https://playwright.dev/docs/test-cli) for additional options such as headed mode (`npm run test:headed`) or tracing (`npx playwright show-trace <trace.zip>`). If you see errors about missing Chromium libraries on Linux, run `npm run setup:deps` (or `npx playwright install-deps chromium`) once—this pulls the required packages without checking them into source control.

### Visual regression approvals

Dashboard and map flows capture Chromium desktop screenshots backed by mock data. Baselines are stored as base64 text files so
they remain friendly to tooling that rejects binary assets. When intentional UI changes occur:

1. Update the frontend fixture data if needed so the mock state reflects the new layout.
2. Run `npm run update-snapshots` from `qa/` to regenerate the base64-encoded snapshots inside `qa/__screenshots__/`.
3. Inspect the diff locally (Playwright surfaces pixel changes in the terminal output) before committing the refreshed assets.

All snapshot updates should accompany a quick accessibility review; the specs fail automatically on any new `serious`/`critical` axe-core violations.
