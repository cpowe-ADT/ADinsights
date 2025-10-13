# AGENTS Guidelines

## Scope

These instructions apply to the entire repository unless a more specific `AGENTS.md` overrides them.

## Purpose

This file serves as the operational prompt for any agent working on ADinsights. Read it before making changes so the guardrails, schedules, and workflow expectations stay consistent across parallel tracks.

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
