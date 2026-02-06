# Integration API Validation Checklist (Phase 1)

Purpose: prevent connector build surprises by validating API access, scopes, limits, and reporting
constraints before implementation. Use this for all new connectors, starting with Phase 1 paid
media sources.

Note: tenant credentials are supplied during onboarding/setup. This checklist does not require
credentials; it records API requirements and constraints so builds are not blocked later.

Owners: Maya (Integrations), Leo (Celery), Priya (dbt), Sofia (Metrics API). Coordinate with Raj if
execution spans backend + dbt + infrastructure.

## Usage

1) Complete the checklist for each connector before scheduling build work.
2) Record approvals, scopes, quotas, and known limitations.
3) Attach final notes to the connector backlog item in `docs/project/phase1-execution-backlog.md`.

## Phase 1 connectors (required)

### Meta Marketing API (production readiness gate)
- Auth model: Long-lived system access token for Marketing API (`ads_read`) with app credentials.
- Scopes/permissions: `ads_read`, app-level permissions for token refresh workflow.
- App approval required: Yes (Meta app + business verification per account policy).
- Rate limits / quota units: Platform-managed; monitor via Airbyte job telemetry + API cost fields.
- Reporting endpoints + dimensions: Ad/account insights with incremental lookback replay.
- Historical lookback + data latency: 3-day replay window for late conversions; 28-day attribution horizon.
- Currency + timezone behavior: Account-level currency; schedule timezone pinned to `America/Jamaica`.
- Airbyte connector availability/maturity: Supported via Airbyte Meta source template.
- Known gotchas: Token expiration/revocation and app permission drift can silently stale syncs.
- Validation owner + date: Maya + Leo, 2026-02-06
- Verification commands:
  - `python3 infrastructure/airbyte/scripts/validate_tenant_config.py`
  - `python3 infrastructure/airbyte/scripts/verify_production_readiness.py`
  - `python3 infrastructure/airbyte/scripts/airbyte_health_check.py`

### Google Ads (production readiness gate)
- Auth model: OAuth client credentials + refresh token + developer token.
- Scopes/permissions: Google Ads API access at manager/customer hierarchy.
- App approval required: Yes (developer token review + OAuth consent setup).
- Rate limits / quota units: API-unit based; watch Airbyte telemetry and API cost counters.
- Reporting endpoints + dimensions: GAQL daily metrics + geo slices from configured query.
- Historical lookback + data latency: Incremental with conversion lag replay (default 3-day lookback).
- Currency + timezone behavior: Cost in micros converted downstream; schedule timezone `America/Jamaica`.
- Airbyte connector availability/maturity: Supported via Airbyte Google Ads source template.
- Known gotchas: Developer token restrictions, MCC login-customer mismatch, refresh token expiry.
- Validation owner + date: Maya + Priya, 2026-02-06
- Verification commands:
  - `python3 infrastructure/airbyte/scripts/validate_tenant_config.py`
  - `python3 infrastructure/airbyte/scripts/verify_production_readiness.py`
  - `python3 infrastructure/airbyte/scripts/airbyte_health_check.py`

### Microsoft Advertising (Bing Ads)
- Auth model:
- Scopes/permissions:
- App approval required:
- Rate limits / quota units:
- Reporting endpoints + dimensions:
- Historical lookback + data latency:
- Currency + timezone behavior:
- Airbyte connector availability/maturity:
- Known gotchas (e.g., account hierarchy, reporting delays):
- Validation owner + date:

### LinkedIn Ads
- Auth model:
- Scopes/permissions:
- App approval required:
- Rate limits / quota units:
- Reporting endpoints + dimensions:
- Historical lookback + data latency:
- Currency + timezone behavior:
- Airbyte connector availability/maturity:
- Known gotchas (strict API limits, partner approval):
- Validation owner + date:

### TikTok Ads
- Auth model:
- Scopes/permissions:
- App approval required:
- Rate limits / quota units:
- Reporting endpoints + dimensions:
- Historical lookback + data latency:
- Currency + timezone behavior:
- Airbyte connector availability/maturity:
- Known gotchas (refresh token lifecycle, sandbox vs prod):
- Validation owner + date:

## Deliverables

- Completed checklists above with dates and owners.
- Decision: Airbyte connector vs custom build for each source.
- Notes on data availability vs dashboard KPIs.
- Risk summary (approval lead times, rate limits, data latency).
