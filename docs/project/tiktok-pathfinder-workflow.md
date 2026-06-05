# TikTok Reporting Pathfinder — Build Workflow (resumable)

> Branch: `feat/tiktok-reporting-pathfinder` (off `main`) · Plan: [integration-completion-plan.md](integration-completion-plan.md)
>
> This is the **resumable runbook** for wiring TikTok end-to-end into `/api/metrics/combined/`.
> Each step lists its **scope**, the **change**, and the **verify command** that must pass before
> moving on. Check the box when a step is green and committed. Anyone can resume by finding the
> first unchecked box and running its verify command to confirm the prior state.

## Decisions adopted (defaults from the plan; pending Raj/Mira ratification)

- **DD-1 = Option A** — performance and transparency are *separate* lineages. A new
  `stg_tiktok_ads_performance` model (fed by a `raw.tiktok_ads_performance` seed in the canonical
  14-field connector schema) feeds the combined fact under `source_platform='tiktok'`. The existing
  `stg_tiktok_transparency` model is **not** unioned into the combined fact (avoids double-counting
  spend). Both can coexist; only performance reaches reporting.
- **DD-2 = Airbyte-orchestrated sync** — backend triggers the Airbyte connection and reads warehouse
  rows; no direct SDK client for now.

## How to run things locally

- **dbt** (DuckDB, no server): `cd dbt && dbt build --select <model> --vars 'enable_tiktok: true'`
  then `dbt test --select <model> --vars 'enable_tiktok: true'`.
- **backend**: `cd backend && .venv/bin/python -m pytest tests/<file> -q` (SQLite test settings).
- **frontend**: `cd frontend && npx vitest run <file>` / `npm run build`.

## Build steps

### Stage A — dbt vertical (scope: `dbt/`)  ← DONE & verified (2026-06-05)
- [x] **A1** Seed `dbt/seeds/raw/tiktok_ads_performance.csv` (canonical 14-field rows; a couple of
  Jamaica parishes for the geo join). Register column types in `dbt_project.yml` (both `seeds:` and
  the `raw__tiktok_ads_performance` block) and add the `raw.tiktok_ads_performance` source table to
  `models/staging/schema.yml` (gated `enabled: "{{ var('enable_tiktok', False) }}"`).
- [x] **A2** `dbt/models/staging/stg_tiktok_ads_performance.sql` — mirror `stg_tiktok_transparency`:
  map canonical fields → fact columns (`account_id→ad_account_id`, `ad_group_id→adset_id`,
  `region→region_name`), join `geo_parish_lookup` for `parish_name/parish_code`, carry `conversions`
  + `conversion_value`. `config(materialized='view', enabled=var('enable_tiktok', False))`.
- [x] **A3** Repoint the `enable_tiktok` block in `models/reference/all_ad_performance.sql` from
  `stg_tiktok_transparency` → `stg_tiktok_ads_performance`; change `null as conversions` →
  `conversions` (performance has it).
- [x] **A4** Added dbt tests in `models/staging/schema.yml`: `not_null` on
  `tenant_id/ad_account_id/ad_id/date_day` + grain `unique_combination_of_columns`. Also fixed a
  latent parish-join fan-out (region→multiple parishes) by deduping the geo lookup.
  - **Verified (from repo root):**
    `CI_SKIP_FIXTURE_VIEWS=true dbt seed --project-dir dbt --profiles-dir dbt --full-refresh --vars 'enable_tiktok: true'`
    → `dbt run --project-dir dbt --profiles-dir dbt --selector staging_ci --vars 'enable_tiktok: true'`
    → `dbt test --project-dir dbt --profiles-dir dbt --select stg_tiktok_ads_performance --vars 'enable_tiktok: true'` (6/6 PASS).
    Data: tiktok in `fact_performance` = 4 rows, spend 431.50, conversions 19, 4 parishes.
    Regression: with `enable_tiktok` default false, fact has only meta+google; stg model not materialized.

### Stage B — combined-metrics registry (scope: `backend/`)
- [ ] **B1** Add `PLATFORM_TIKTOK` to `COMBINED_SUPPORTED` in `backend/analytics/platform_registry.py`
  (label/order already present).
  - **Verify:** extend `backend/tests/test_combined_platforms_only.py` — `?platforms=tiktok` includes
    tiktok; omitting excludes it. `cd backend && .venv/bin/python -m pytest tests/test_combined_platforms_only.py -q`.

### Stage C — warehouse snapshot includes TikTok (scope: `backend/`)
- [ ] **C1** Ensure the warehouse snapshot builder (the job that fills
  `TenantMetricsSnapshot.payload`) surfaces `tiktok` slices from `fact_performance`. Confirm whether
  it already generalizes over `source_platform` or hard-codes meta/google; extend if needed.
  - **Verify:** snapshot fixture/unit test shows `tiktok` keys; `test_warehouse_client_scoping` green.

### Stage D — client scoping + isolation (scope: `backend/`)  ← **mandatory L4 eval**
- [ ] **D1** Resolve `client_scoped_tiktok_ids` in `combined_metrics_service.resolve_client_scoping`
  and honor it in `WarehouseAdapter._apply_filters`.
  - **Verify:** extend `test_combined_client_id_scoping.py` — tenant A cannot see tenant B tiktok rows.

### Stage E — frontend surface (scope: `frontend/`)
- [ ] **E1** Add a `tiktok` color token in `styles/chartTheme.ts` + `platformColor` case; confirm the
  platform toggle shows TikTok when `combined_supported` includes it.
  - **Verify:** `cd frontend && npx vitest run` + `npm run build`.

### Stage F — end-to-end eval + rollout (scope: `backend/` + `docs/`)
- [ ] **F1** Vertical-slice test: seeded fact → `/api/metrics/combined/?platforms=tiktok` returns
  expected aggregates (extend `tests/integration/test_vertical_slice.py`).
- [ ] **F2** Flags default-off confirmed (`enable_tiktok=false` is a no-op); runbook stub
  `docs/runbooks/tiktok-operations.md`.

## Status log
- _(append dated one-liners as steps land, newest last)_
- 2026-06-05 — workflow created; decisions DD-1=A, DD-2=Airbyte adopted; starting Stage A.
