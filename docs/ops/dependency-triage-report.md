# Dependency Triage Report

Generated: 2026-02-17

## Scope

- Backend Python dependencies
- Root workspace npm dependencies
- Frontend npm dependencies
- QA npm dependencies
- Integrations exporter npm dependencies

## Decision Policy

Update dependencies only when one of the following is true:

- Security vulnerability with a fix available
- Build/test/runtime breakage caused by dependency versions
- Compatibility issue blocking local or CI workflows

## Findings

### Python (`backend/requirements.txt`, `backend/pyproject.toml`)

- `django==5.1.14` had known CVEs (`CVE-2025-13372`, `CVE-2025-64460`) with fix available in `5.1.15`.
- `sentry-sdk==1.45.0` had known CVE (`CVE-2024-40647`) with fix available in `1.45.1`.
- `cryptography==44.0.1` had known CVE (`CVE-2026-26007`) with fix available in `46.0.5`.

### npm (root/frontend)

- `npm audit` flagged high severity advisory on transitive `axios` (`GHSA-43fc-jf86-j433`) with fix available.
- The vulnerable chain came through Storybook test-runner dependencies.

### npm (qa/exporter)

- No vulnerabilities found by `npm audit`.

## Changes Applied

### Security-driven updates

- `backend/requirements.txt`
  - `django==5.1.14` -> `django==5.1.15`
  - `sentry-sdk==1.45.0` -> `sentry-sdk==1.45.1`
  - `cryptography==44.0.1` -> `cryptography==46.0.5`
- `backend/pyproject.toml`
  - `cryptography>=42.0,<45.0` -> `cryptography>=46.0.5,<47.0`
- `package.json`
  - Added npm `overrides` for `axios` to force a non-vulnerable release
- `frontend/package.json`
  - Added npm `overrides` for `axios` to force a non-vulnerable release

### Dependency automation hygiene

- `.github/dependabot.yml`
  - Replaced invalid placeholder config with valid weekly update jobs for:
    - pip (`/backend`)
    - npm (`/`)
    - npm (`/frontend`)
    - npm (`/qa`)
    - npm (`/integrations/exporter`)

## No-Change Decisions

- Outdated packages without security/break-fix/compatibility impact were not upgraded.
- No semver-minor/major refresh was performed beyond security-required changes.

## Residual Risks / Follow-up

- Keep weekly Dependabot PRs reviewed with the same policy (security + break/fix first).
- Re-run `pip-audit` and `npm audit` in CI on a regular cadence to detect future issues.

## Validation Evidence (2026-02-17)

### Launcher / Healthcheck

- `bash -n scripts/dev-launch.sh scripts/dev-healthcheck.sh` passed.
- `scripts/dev-launch.sh --list-profiles` printed the 4 expected profiles.
- Profile selection behavior verified with a mocked Docker CLI (daemon unavailable in this environment):
  - strict mode fails for busy selected profile.
  - non-strict mode falls to next free profile in cyclic order.
  - when all profiles conflict, incremental per-port fallback is applied.
- `.dev-launch.active.env` writes resolved profile, ports, and URLs.
- `scripts/dev-healthcheck.sh` precedence verified:
  - explicit env URLs > `.dev-launch.active.env` > defaults (`http://localhost:8000`, `http://localhost:5173`).

### Regression Suite

- Passed:
  - `ruff check backend`
  - `pytest -q backend`
  - `cd frontend && npm ci && npm run lint && npm test -- --run && npm run build`
  - `cd integrations/exporter && npm ci && npm test && npm run build`
- Not green in this run:
  - `cd qa && npm ci && npm test -- --project=chromium-desktop`
  - Failure mode: timeout waiting for Playwright `networkidle` in `qa/page-objects/BasePage.ts:16`.
  - Assessment: this appears to be a QA harness/runtime behavior issue, not a dependency vulnerability issue.
