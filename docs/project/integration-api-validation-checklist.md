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
