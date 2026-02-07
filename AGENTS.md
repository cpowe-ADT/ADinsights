# AGENTS Guidelines

## Scope

These instructions apply to the entire repository unless a more specific `AGENTS.md` overrides them.

## Purpose

This file serves as the operational prompt for any agent working on ADinsights. Read it before making changes so the guardrails, schedules, and workflow expectations stay consistent across parallel tracks. Stream-specific KPIs, owners, and Definition-of-Done checklists live in `docs/workstreams.md`—use it alongside this guide when executing a track.

## Quick Context References

- Feature catalog (built/in progress/planned): `docs/project/feature-catalog.md`
- Feature ownership + tests + runbooks: `docs/project/feature-ownership-map.md`
- API contract changelog: `docs/project/api-contract-changelog.md`
- Integration data contract matrix: `docs/project/integration-data-contract-matrix.md`
- Release checklist: `docs/runbooks/release-checklist.md`
- CSV upload runbook: `docs/runbooks/csv-uploads.md`
- Data quality checklist: `docs/ops/data-quality-checklist.md`
- Risk register: `docs/ops/risk-register.md`
- ADR log: `docs/ops/adr-log.md`
- User journey map: `docs/project/user-journey-map.md`
- Support playbook: `docs/runbooks/support-playbook.md`
- Ops dashboard links: `docs/ops/dashboard-links.md`
- Postmortem template: `docs/ops/postmortem-template.md`
- Data lineage map: `docs/project/data-lineage-map.md`
- AI onboarding checklist: `docs/ops/ai-onboarding-checklist.md`
- Testing cheat sheet: `docs/ops/testing-cheat-sheet.md`
- Feature flags reference: `docs/project/feature-flags-reference.md`
- Definition of Done: `docs/project/definition-of-done.md`
- AI escalation rules: `docs/ops/escalation-rules.md`
- AI session resume template: `docs/ops/ai-session-resume-template.md`
- Decision checklist: `docs/ops/decision-checklist.md`
- Test failure triage: `docs/ops/test-failure-triage.md`
- New engineer onboarding: `docs/ops/new-engineer-onboarding.md`
- Human onboarding guide: `docs/ops/human-onboarding-guide.md`
- Confused engineer walkthrough: `docs/ops/confused-engineer-walkthrough.md`
- Documentation snob review: `docs/ops/documentation-snob-review.md`
- Golden path onboarding: `docs/ops/golden-path-onboarding.md`

## When to Update AGENTS.md

Update `AGENTS.md` when:
- A new cross-cutting doc is added (catalogs, ownership, runbooks, escalation rules).
- Guardrails, schedules, or test matrix change.
- Recontextualization workflow changes.

## Personas & Ownership Map

Personas and stream ownership live in:
- `docs/workstreams.md` (owners, KPIs, tests, DoD)
- `docs/project/feature-ownership-map.md` (domain → owner → tests/runbooks)

When unsure, consult the ownership map before starting work.

## Recontextualization Workflow

If context is unclear, follow this order:
1) `AGENTS.md`
2) `docs/ops/doc-index.md`
3) `docs/workstreams.md`
4) `docs/project/feature-catalog.md`
5) `docs/project/phase1-execution-backlog.md`
6) `docs/task_breakdown.md`
7) `docs/project/vertical_slice_plan.md`

## Architecture Guardrails

- Preserve the existing stack: Django + DRF + Celery in `backend/`, React + Vite + TanStack Table + Leaflet in `frontend/`, Airbyte OSS artifacts in `infrastructure/airbyte/`, and dbt models/macros/tests in `dbt/`.
- Do not introduce alternative frameworks (e.g., FastAPI) or remove the health endpoints `/api/health/`, `/api/health/airbyte/`, `/api/health/dbt/`, or `/api/timezone/`.
- Maintain row-level security and tenant isolation. Backend code must continue to set `SET app.tenant_id` per request and may not weaken existing policies.

## Background Agents, Schedules & Guardrails

**Timezone:** America/Jamaica

**PII policy:** Only report aggregated advertising metrics; never expose user-level data.

**Secrets policy:** Reversible OAuth tokens are AES-GCM encrypted with per-tenant DEKs wrapped by KMS. Never log or commit secrets.

| Agent                   | Purpose                                    | Cadence                 | Window     | SLA      | Notes                                                                           |
| ----------------------- | ------------------------------------------ | ----------------------- | ---------- | -------- | ------------------------------------------------------------------------------- |
| sync_meta_metrics       | Meta Insights (yesterday + 3-day lookback) | Hourly 06:00–22:00      | ~5m        | <30m     | Use incremental sync with Insights Window Lookback to capture late conversions. |
| sync_google_metrics     | Google Ads GAQL daily metrics              | Hourly 06:00–22:00      | ~5m        | <30m     | Convert cost micros to currency; rely on the Airbyte Google Ads source.         |
| sync_dimensions_daily   | Campaigns/adsets/ads plus geo constants    | Daily 02:15             | ~10m       | by 03:00 | Dimensions change slowly; daily refresh keeps dbt models stable.                |
| dbt_staging_incremental | Build `stg_*` models                       | After each metrics sync | ~4m        | <15m     | Incremental on `date` to keep ingestion lightweight.                            |
| dbt_aggregates          | Build marts/aggregates                     | 05:00 daily             | ~8m        | by 06:00 | Powers dashboards and map visuals.                                              |
| ai_daily_summary        | Email-ready summary                        | 06:10 daily             | ~1m/tenant | by 06:30 | Uses only aggregated metrics.                                                   |
| rotate_deks             | Rewrap DEKs via KMS                        | Weekly Sun 01:30        | —          | —        | Envelope encryption pattern; rewrap only.                                       |

**Backoff/Retry:** Use exponential backoff (base 2), maximum five attempts, with jitter.

**Observability:** Track task latency, success rate, rows processed, and upstream API cost units. Emit structured JSON logs including `tenant_id`, `task_id`, and `correlation_id`; do not log secrets. Alert on consecutive failures, secret expiration, or unexpectedly empty syncs.

## Workflow Expectations

- Keep each change isolated to a single top-level folder to allow independent PRs per sprint track.
- Use short-lived feature branches and prefer squash merges.
- Follow conventional commit messages such as `feat(backend): …` or `docs(airbyte): …`.
- When a change must touch multiple folders, loop in the Cross-Stream Integration Lead (Raj) so each stream owner co-reviews, and involve the Architecture/Refactor engineer (Mira) whenever the work is a codebase-wide refactor. Both roles keep cross-stream PRs aligned with the guardrails in `docs/workstreams.md`.

## Testing Matrix

Run the canonical checks for the folder you touch:

- **Backend:** `ruff check backend && pytest -q backend`
- **Frontend:** `cd frontend && npm ci && npm test -- --run && npm run build`
- **dbt:** `make dbt-deps && dbt --project-dir dbt run --select staging && dbt snapshot && dbt --project-dir dbt run --select marts`
- **Airbyte:** `cd infrastructure/airbyte && docker compose config`

## Secrets & Data Handling

- Never commit real credentials. Only update `.env.sample`, `.example`, or redacted documentation placeholders.
- Keep all analytics aggregated; avoid exposing per-user or other identifiable data.

## Implementation Notes

- **DRF optional fields:** Use `required=False` to allow omission during deserialization and `allow_null=True` only when explicit `null` should be accepted.
- **Celery + Django:** Continue using the existing integrated setup; do not re-home task discovery or settings.
- **dbt snapshots:** Use SCD Type 2 semantics with `dbt_valid_from`/`dbt_valid_to` for mutable dimensions.
- **TanStack Table:** Prefer `getSortedRowModel()` with controlled `state.sorting` and `onSortingChange`; avoid duplicate local sort state.
- **Leaflet choropleths:** Load GeoJSON safely, bucket values defensively, and guard tooltip rendering against missing data.

## Timezone Reminder

Reference schedules, cron examples, and documentation in the `America/Jamaica` timezone unless an upstream tool forces UTC.
