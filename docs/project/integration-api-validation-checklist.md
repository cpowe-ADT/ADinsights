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
4) Keep the canonical source-to-warehouse mapping synced in `docs/project/integration-data-contract-matrix.md`.

## Phase 1 connectors (required)

## Phase 1 connector roadmap checklist

Use this as the connector execution list for Phase 1 closeout.

| ID | Connector | Scope | Owner(s) | Status | Exit criteria |
|----|-----------|-------|----------|--------|---------------|
| S1-D | Microsoft Ads, LinkedIn Ads, TikTok Ads | Complete API validation checklist entries (auth/scopes/limits/lookback/known gotchas). | Maya | Done (2026-02-06) | All checklist fields completed with validation date + owner. |
| S1-E | Microsoft Ads | Decide Airbyte vs custom path and define schedule metadata (`America/Jamaica`). | Maya + Priya + Sofia | Done (2026-02-06, planning) | Connector decision documented + data contract notes + tests scoped. |
| S1-F | LinkedIn Ads | Confirm partner approval path, API limits, and ingestion plan. | Maya + Priya + Sofia | Done (2026-02-06, planning) | Approval risk documented + connector plan + fallback path. |
| S1-G | TikTok Ads | Confirm refresh-token lifecycle and production token rotation plan. | Maya + Leo + Priya | Done (2026-02-06, planning) | Token lifecycle documented + schedule/telemetry requirements captured. |

### Additional connector closeout items (recommended)

1. Add per-connector “minimum KPI parity” table (campaign, creative, geo, conversion, spend, currency).
2. Add expected failure modes + retry strategy notes for each connector (quota, auth revocation, schema drift).
3. Record rollout gate for each connector:
   - Staging sync success
   - dbt model/tests green
   - `/api/metrics/combined/` payload parity check
4. Add a go/no-go owner signature block per connector before production enablement.

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
- Authenticated portal validation evidence (manual): `docs/project/evidence/phase1-closeout/external/meta-authenticated-validation-required-2026-02-06-est.md`
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
- Auth model: OAuth 2.0 authorization code with refresh tokens through Microsoft identity + Ads developer token.
- Scopes/permissions: `offline_access` and Microsoft Ads management scope (`msads.manage`) with advertiser account access.
- App approval required: Yes. Developer token approval tier and account access must be validated before production sync.
- Rate limits / quota units: Endpoint-specific throttles and async reporting job limits; enforce exponential backoff with jitter.
- Reporting endpoints + dimensions: Campaign/ad group/ad performance, geo, device, and conversion reporting via async report download workflow.
- Historical lookback + data latency: Plan 3-day conversion replay for hourly metrics and 28-day attribution monitoring.
- Currency + timezone behavior: Account currency and account timezone in source; orchestration timezone stays `America/Jamaica`.
- Airbyte connector availability/maturity: Re-validate Airbyte connector maturity at build start; default implementation path is custom connector if acceptance tests fail.
- Known gotchas (e.g., account hierarchy, reporting delays): Manager-account vs client-account context, async report polling delays, and occasional schema/version drift.
- Validation owner + date: Maya + Priya, 2026-02-06
- Rollout gate:
  - Staging sync successful for one tenant and one manager hierarchy.
  - dbt staging + marts run without schema exceptions.
  - `/api/metrics/combined/` KPI parity validated against existing campaign metrics.
- S1-E implementation plan:
  - Decision: custom connector-first, Airbyte as optional fast-follow if reliability gates pass.
  - Schema mapping: normalize to campaign/ad group/ad/day grains aligned to existing marts.
  - Orchestration: hourly 06:00-22:00 + 3-day lookback, daily dimension refresh 02:15 (`America/Jamaica`).
  - Retry/backoff: base-2 exponential, max 5 attempts, jitter.
  - Test matrix: connector unit tests, backend telemetry tests, dbt staging/marts checks, compose validation.

### LinkedIn Ads
- Auth model: OAuth 2.0 member authorization with refreshable tokens for Marketing APIs.
- Scopes/permissions: `r_ads`, `r_ads_reporting`, and write scopes only if mutation endpoints are required.
- App approval required: Yes. Marketing Developer Platform access and tenant ad-account authorization are mandatory.
- Rate limits / quota units: Strict per-application and per-member quotas; enforce conservative polling and backoff.
- Reporting endpoints + dimensions: Account/campaign/creative performance, spend, clicks, impressions, and conversion aggregates.
- Historical lookback + data latency: 3-day replay for late metrics; monitor platform reporting lag explicitly in telemetry.
- Currency + timezone behavior: Account currency from source; orchestration in `America/Jamaica`.
- Airbyte connector availability/maturity: Treat as custom connector path for Phase 1 unless a validated Airbyte connector meets reliability gates.
- Known gotchas (strict API limits, partner approval): partner access delays, URN identifier normalization, and campaign hierarchy edge cases.
- Validation owner + date: Maya + Sofia, 2026-02-06
- Rollout gate:
  - Partner approval confirmation and token issuance documented.
  - Staging sync completes within quota limits.
  - dbt + API parity checks confirm KPI alignment with existing dashboard contracts.
- S1-F implementation plan:
  - Decision: custom connector primary due approval and quota constraints.
  - Schema mapping: URN -> stable IDs, campaign/creative grain compatibility with marts.
  - Orchestration: hourly metrics window + daily dimensions schedule in `America/Jamaica`.
  - Retry/backoff: base-2 exponential, max 5 attempts, jitter, with quota-aware pacing.
  - Test matrix: auth/refresh tests, ingestion parser tests, backend telemetry tests, dbt contract tests.

### TikTok Ads
- Auth model: OAuth 2.0 advertiser authorization with short-lived access tokens and refresh-token rotation.
- Scopes/permissions: reporting and account-read scopes required for ad metrics extraction.
- App approval required: Yes. TikTok for Business app review and advertiser authorization required.
- Rate limits / quota units: Endpoint and app-level QPS constraints; enforce batched pulls + backoff/jitter.
- Reporting endpoints + dimensions: Campaign/ad group/ad performance with geo breakdowns where available.
- Historical lookback + data latency: 3-day replay for late conversion attribution and correction windows.
- Currency + timezone behavior: Source account currency retained; orchestration timezone `America/Jamaica`.
- Airbyte connector availability/maturity: Airbyte connector can be used if validation gates pass; fallback is custom connector.
- Known gotchas (refresh token lifecycle, sandbox vs prod): refresh-token expiry/revocation, advertiser binding changes, sandbox field mismatch.
- Validation owner + date: Maya + Leo, 2026-02-06
- Rollout gate:
  - Token lifecycle runbook validated (refresh, revoke, rotate paths).
  - Staging sync + telemetry freshness thresholds pass.
  - dbt and `/api/metrics/combined/` parity validated for spend/clicks/conversions.
- S1-G implementation plan:
  - Decision: Airbyte-first with mandatory fallback path to custom ingestion.
  - Schema mapping: normalize to existing campaign/creative/date grains with defensive null handling.
  - Orchestration: hourly metrics + daily dimensions in `America/Jamaica`.
  - Retry/backoff: base-2 exponential, max 5 attempts, jitter, token-refresh on auth failure path.
  - Test matrix: token-refresh unit tests, ingestion mapping tests, backend telemetry tests, dbt staging/marts validation.

## Deliverables

- Completed checklists above with dates and owners.
- Decision: Airbyte connector vs custom build for each source.
- Notes on data availability vs dashboard KPIs.
- Risk summary (approval lead times, rate limits, data latency).
- Canonical cross-source mapping in `docs/project/integration-data-contract-matrix.md`.
- Automated gate command: `python3 infrastructure/airbyte/scripts/check_data_contracts.py`.
