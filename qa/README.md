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

#### Mock runs (default)

Use the mock backend when iterating on UI scenarios or authoring new tests.

```bash
cd qa
npm test                      # runs against the built frontend in mock mode
```

You can scope the run while still using mocks:

```bash
npm test -- --grep "health"   # run only tests whose titles include "health"
```

#### Live API smoke runs

Provide the real backend base URL and disable the mocks when validating full-stack flows.

```bash
cd qa
MOCK_MODE=false LIVE_API_BASE_URL="https://staging.adinsights.local" npm test
```

If the frontend is already hosted, append `QA_BASE_URL="https://staging-frontend.adinsights.local"` to reuse it instead of starting the preview server. The suite skips API-dependent specs unless `LIVE_API_BASE_URL` is defined, so set it explicitly when `MOCK_MODE=false`.

### Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `MOCK_MODE` | `true` | When `true`, tests stub API health and export endpoints to avoid requiring the Django backend. Set to `false` to exercise live APIs. |
| `QA_PORT` | `4173` | Port used for the ephemeral Vite dev server started by Playwright. |
| `QA_BASE_URL` | — | Override the computed base URL (useful when pointing to an already running frontend). Leave unset to use the preview server (e.g., `http://127.0.0.1:${QA_PORT}`). |
| `LIVE_API_BASE_URL` | — | Required for live runs (`MOCK_MODE=false`). Provide the fully qualified base (e.g., `https://staging.adinsights.local`). |

When `MOCK_MODE=false`, ensure the backend is running and reachable from the test environment. The suite expects `/api/health/`, `/api/health/airbyte/`, `/api/health/dbt/`, and `/api/metrics/export/?format=csv` to respond with production-formatted payloads.

### Mock data & snapshots

- Mock responses are fulfilled inline in each spec and rely on the static JSON fixtures that ship with the frontend (`frontend/public/*.json`). Update or add new fixtures there before recording alternative responses.
- Use the frontend TypeScript models (for example, `frontend/src/state/useDashboardStore.ts`) as the source of truth when shaping mock payloads. Running `npm run build` in `frontend/` will surface type drift before QA runs capture the data.
- Update Playwright snapshot baselines by passing `--update-snapshots` through to the runner: `npm test -- --update-snapshots`. Use this after intentional UI changes and confirm the visual diffs locally before committing.
- We do not currently persist HAR recordings. If you need to capture new network traffic, use Playwright's [`tracing.start({ screenshots: true, snapshots: true })`](https://playwright.dev/docs/trace-viewer) helpers inside a spec and commit the resulting trace zip alongside any updated mocks.

### Accessibility expectations

Accessibility coverage is currently manual. When introducing new flows, run `npm run test:headed` and use Playwright's [built-in accessibility inspector](https://playwright.dev/docs/accessibility-testing) (open via **More tools → Accessibility**) to verify landmark, contrast, and focus heuristics. Capture findings in the test PR and add follow-up issues for any violations you cannot resolve immediately.

CI publishes traces, videos, and screenshots for each spec to the pipeline artifacts:

- GitHub Actions: `Artifacts > playwright-traces` contains `*.zip` trace bundles, `*.webm` videos, and `*.png` screenshots grouped by test file. GitHub will display `binary not supported` for the zipped traces—download them locally and run `npx playwright show-trace <path-to-zip>` to review.
- Nightly builds upload to the `nightly-playwright` artifact with the same layout. Live (`MOCK_MODE=false`) jobs attach additional HAR captures for debugging backend regressions.

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
## CI & nightly strategy

- **PR checks:** Run only the mock-mode suite (`MOCK_MODE=true`) with deterministic seeds. Failures gate merges unless tagged as `@quarantine`.
- **Nightly matrix:** Expands coverage across Chromium, Firefox, and WebKit; runs both mock and live (`MOCK_MODE=false`) variants; and enables visual + accessibility snapshots in headed mode. Live branches also record HAR files for regression comparison.
- **Quarantined tests:** Tests tagged `@quarantine` are skipped in PR jobs but executed (and reported separately) in the nightly matrix. When fixing an issue, remove the tag and verify the spec passes locally and in a PR run before closing the tracking ticket. Nightly failures automatically reopen the quarantine issue.
