# Integration Completion Plan — Marketing Sources → Reporting

> Status: **DRAFT for engineering review** · Owner: Integration (Raj) + Architecture (Mira) ·
> Created: 2026-06-04 · Timezone: `America/Jamaica`
>
> Purpose: turn the deferred marketing connectors (TikTok, LinkedIn, Microsoft Ads — and the
> GA4 / Search Console pilots) into **live, reporting-grade** sources that flow all the way to
> `/api/metrics/combined/` and the dashboards, **one source at a time**, in safe chunks that
> respect the `AGENTS.md` scope freeze. Each chunk ships with evals and a defined Definition of
> Done so engineers (human or agent) can pick up any ticket cold.

---

## 0. How to use this document

1. Read §1 (where we are) and §2 (the spine every source must join). These are the invariants.
2. Read §3 — the one **design decision** that must be settled before any source build starts.
3. §4 picks the **pathfinder source** and the order. Do not parallelize sources.
4. §5 is the **reusable epic** (E0–E6). Every source instantiates the same epic.
5. §6 lists the **per-source deltas** (what's already scaffolded vs. net-new) so we don't redo work.
6. §7 is the **eval strategy** — the gates each ticket must pass.
7. §8 is the **chain-of-prompt playbook** — the literal step sequence to drive each ticket.
8. §9 governance / §10 risks / Appendix A the ticket index for your tracker.

Every ticket below is written so it can be lifted verbatim into ClickUp/Linear/GitHub.

---

## 1. Current state (audit, 2026-06-04)

| Source | Airbyte connector | Backend sync + models | Adapter | dbt → fact | Combined reporting |
|---|---|---|---|---|---|
| **Meta Ads** | ✅ | ✅ | ✅ `meta_direct` + `warehouse` | ✅ `stg_meta_*` → `all_ad_performance` → `fact_performance` | ✅ live |
| **Google Ads** | ✅ (SDK primary, Airbyte fallback) | ✅ `GoogleAdsSyncState` + SDK tasks | ✅ `warehouse` | ✅ `stg_google_ads*` → fact | ✅ live |
| **CSV Upload** | — | ✅ `TenantMetricsSnapshot` | ✅ `upload` | n/a (Phase 1) | ✅ live |
| **GA4** | ✅ | cred-only (`GoogleAnalyticsConnection`) | ✅ `google_analytics` (direct API) | `raw.ga4_reports`→`stg_ga4_reports`→`agg_ga4_daily` | ⚠️ pilot endpoint `/api/analytics/web/ga4/` only |
| **Search Console** | ✅ | — (Airbyte→warehouse) | `warehouse` | `raw.search_console_performance`→`stg_search_console`→`agg_search_console_daily` | ⚠️ pilot endpoint only |
| **TikTok Ads** | ✅ **green (fixed 2026-06-04)** | ❌ none | ❌ none for performance | ⚠️ union block exists but reads **transparency** seed, not connector output | ❌ |
| **LinkedIn Ads** | ✅ **green (fixed 2026-06-04)** | ❌ none | ❌ none for performance | ⚠️ same — transparency lineage only | ❌ |
| **Microsoft Ads** | ✅ **green (foundation)** | ❌ none | ❌ none | ❌ no dbt block at all | ❌ |

**Already true (do not rebuild):**
- All three custom connectors instantiate, `spec`/`discover`/`check`, and emit the canonical
  14-field schema under the installed CDK. Guarded by
  `infrastructure/airbyte/sources/tests/test_connector_smoke.py` and per-source tests.
- Platform enums `ClientPlatformAccount.PLATFORM_LINKEDIN` / `PLATFORM_TIKTOK`
  (`backend/integrations/models.py:1764-1765`) and credential providers
  `PlatformCredential.LINKEDIN` / `TIKTOK` (`:25-26`) **already exist**.
- dbt `dbt/models/reference/all_ad_performance.sql` already has `enable_linkedin` /
  `enable_tiktok` conditional union blocks (lines 93-172) emitting `source_platform`.

**Net-new gaps (the work this plan covers):**
- No backend **sync model / Celery task / repository** that lands connector *performance* rows
  in the warehouse for any of the three.
- `COMBINED_SUPPORTED` (`backend/analytics/platform_registry.py:49`) is still only
  `{meta_ads, google_ads}` — nothing else can pass combined metrics.
- The existing dbt union blocks read **transparency** seeds (`stg_tiktok_transparency`,
  `stg_linkedin_transparency`), **not** the new connectors' performance output — see §3.
- **Microsoft Ads** has no platform enum, no credential provider, no dbt block — it needs the
  enum/credential groundwork the other two already have.
- No `client_scoped_<platform>_ids` plumbing in `combined_metrics_service.py`.
- No frontend platform color token / dataset-store wiring for the new platforms.

---

## 2. The reporting spine (invariants every source must join)

A source becomes "reporting-grade" only when its rows traverse this spine. File anchors are the
contract; treat them as the integration test surface.

```
Airbyte connector (canonical 14-field rows)
   └─► raw warehouse table  (raw.<platform>_ads_performance)
        └─► dbt staging      stg_<platform>_ads_performance.sql      [normalize, parish-map]
             └─► union        all_ad_performance.sql  (source_platform='<platform>')
                  └─► fact     fact_performance.sql   (canonical column contract)
                       └─► snapshot  TenantMetricsSnapshot(source='warehouse')
                            └─► adapter  WarehouseAdapter.fetch_metrics()  backend/adapters/warehouse.py:69
                                 └─► service  combined_metrics_service.py  (platform filter + client scope)
                                      └─► view  CombinedMetricsView  backend/analytics/views.py:257
                                           └─► registry gate  platform_registry.COMBINED_SUPPORTED
                                                └─► frontend  useDashboardStore / platform toggles
```

**Canonical performance contract** (connector output → must survive to `fact_performance`):
`platform, date, account_id, campaign_id, ad_group_id, ad_id, region, device, spend,
impressions, clicks, conversions, conversion_value, currency`.

`fact_performance` column contract (the union target,
`dbt/models/reference/facts/fact_performance.sql`):
`tenant_id, date_day, source_platform, ad_account_id, campaign_id, campaign_name, status,
objective, adset_id, ad_id, ad_name, parish_code, parish_name, region_name, spend, impressions,
reach, clicks, conversions, effective_from`.

> Mapping note: the connector emits `ad_group_id`; the fact uses `adset_id`. The staging model
> is where `ad_group_id → adset_id`, `region → region_name/parish_*`, and `conversion_value`
> handling are reconciled. Parish mapping must reuse the existing Meta/Google parish seed logic.

**The nine seams a new source touches** (each maps to a ticket family in §5):

| # | Seam | File anchor | Combined-metrics required? |
|---|---|---|---|
| 1 | Credential provider | `backend/integrations/models.py` `PlatformCredential.PROVIDER_CHOICES:27` | yes |
| 2 | Sync state + daily model | `backend/integrations/models.py` (`GoogleAdsSyncState:1314` pattern) | yes |
| 3 | Celery sync task + Beat | `backend/integrations/tasks.py` (`sync_google_ads_sdk_incremental:280`), `backend/core/settings.py` Beat | yes |
| 4 | Raw→staging dbt model | `dbt/models/staging/stg_<platform>_ads_performance.sql` (new) | yes |
| 5 | Union into fact | `dbt/models/reference/all_ad_performance.sql` + `enable_<platform>` var | yes |
| 6 | Platform enum + label | `platform_registry.py` `COMBINED_SUPPORTED:49`, `_LABELS`, `COMBINED_ORDER` | yes |
| 7 | Client scoping | `combined_metrics_service.py::resolve_client_scoping` + warehouse filter | only if client-grouped |
| 8 | Settings flags | `backend/core/settings.py` `ENABLE_*` + per-source feature flag | yes |
| 9 | Frontend surface | `frontend/src/lib/platformLabels.ts`, `styles/chartTheme.ts`, `routes/DataSources.tsx`, `state/useDatasetStore.ts` | yes |

---

## 3. Design decision to settle FIRST (blocks all source builds)

**DD-1: Performance lineage vs. existing transparency lineage.**

The existing `all_ad_performance.sql` tiktok/linkedin blocks read `stg_tiktok_transparency` /
`stg_linkedin_transparency`, which are fed by *transparency* seed CSVs
(`dbt/seeds/raw/tiktok_transparency.csv`, `linkedin_transparency.csv`) — ad-library style data,
**not** the spend/impressions/clicks/conversions performance rows the new connectors emit.

We cannot have two different `source_platform='tiktok'` definitions feeding one fact. Choose:

- **Option A (recommended): separate performance staging models.** Add
  `stg_tiktok_ads_performance.sql` reading the connector's raw output, and switch the
  `enable_tiktok` union block to read the performance model. Retire/relabel the transparency
  block (e.g. `source_platform='tiktok_transparency'` kept out of `COMBINED_SUPPORTED`, or move
  transparency to its own mart). Cleanest separation; transparency and performance never collide.
- **Option B: merge in staging.** One `stg_tiktok` that coalesces transparency + performance.
  Rejected unless product needs a single blended grain — high risk of double-counting spend.

**Action:** Mira + Raj ratify DD-1 (default: Option A) in `docs/project/api-contract-changelog.md`
before ticket `*-E2-01` starts. Every source inherits the ratified choice.

**DD-2: Sync transport per source.** Google Ads uses an SDK with Airbyte fallback; Meta uses
direct + Airbyte. For TikTok/LinkedIn/Microsoft the connectors are **Airbyte-only** today. Decide
per source whether backend sync = "trigger Airbyte connection + read warehouse" (lower lift, reuse
`trigger_scheduled_airbyte_syncs`/`AirbyteConnection`) or a direct SDK client (higher lift, parity
harness). **Recommended default: Airbyte-orchestrated** for all three; revisit only if a
provider's Airbyte reliability fails the eval in §7.

---

## 4. Sequencing — one source at a time

**Principle:** prove the full spine on ONE pathfinder source, harden the template, then replicate.
No two sources in flight simultaneously (per user direction and scope-freeze hygiene).

**Readiness comparison:**

| Factor | TikTok | LinkedIn | Microsoft Ads |
|---|---|---|---|
| Connector green | ✅ | ✅ | ✅ |
| Platform enum exists | ✅ | ✅ | ❌ (add) |
| Credential provider exists | ✅ | ✅ | ❌ (add) |
| dbt union block stub | ✅ (transparency) | ✅ (transparency) | ❌ (add) |
| Frontend `PROVIDER_LABELS` entry | ✅ | ✅ | ❌ (add) |
| Connector contract-checked in `check_data_contracts.py` | ❌ | ❌ | ✅ |
| Net new groundwork | least | least | most (enum+cred+dbt) |

**Recommended order:**
1. **TikTok = pathfinder.** Most pre-scaffolded; build E0–E6 fully, treat its PRs as the template.
2. **LinkedIn = replication.** Same shape; should be mostly "copy + source-specific delta" once
   TikTok's template exists. Validates the template generalizes.
3. **Microsoft Ads = generalization test.** Forces the enum/credential/dbt groundwork the others
   skipped, proving the template works for a from-scratch platform. Its connector is the most
   contract-checked, de-risking the top of the spine.
4. **GA4 + Search Console = pilot promotion (separate track).** Different shape (already have
   `/api/analytics/web/*` endpoints + `agg_*` marts); see §6.4. Can run after or parallel to the
   ads track since it touches different files — but still gate on Raj/Mira for the combined-metrics
   promotion decision.

---

## 5. Reusable epic (instantiated once per source)

Replace `<P>` with the platform slug (`tiktok` / `linkedin` / `microsoft`). Each ticket lists
**Scope** (the single top-level folder it touches — keep PRs within one folder per `AGENTS.md`),
**Deps**, **Acceptance criteria (AC)**, and **Eval** (the §7 gate it must pass).

### E0 — Design & contract (Scope: `docs/`)
- **`<P>`-E0-01 — Source design note + DD-1/DD-2 application.**
  Deps: DD-1/DD-2 ratified. AC: a 1-page note in `docs/project/` covering raw table name, staging
  grain, fact mapping (`ad_group_id→adset_id`, parish derivation, currency normalization to a
  reporting currency or per-row passthrough), sync transport, and the credential shape. Update
  `docs/project/integration-data-contract-matrix.md` with the `<P>` row.
  Eval: design-review sign-off (Raj+Mira).

### E1 — Credentials + sync (Scope: `backend/`)
- **`<P>`-E1-01 — Credential provider** (Microsoft only; TikTok/LinkedIn already present).
  AC: `PlatformCredential.MICROSOFT` added to `PROVIDER_CHOICES`; migration; admin + connector
  setup endpoint accepts it. Eval: `test_integration_connector_api` extended, green.
- **`<P>`-E1-02 — Sync state + daily model.**
  AC: `<P>AdsSyncState` (mirror `GoogleAdsSyncState:1314` fields: engine, attempt/success
  timestamps, window bounds, rows_synced, last_error, metadata) + a raw daily table model (or
  documented reliance on the Airbyte-landed `raw.<P>_ads_performance`). Migration. Eval:
  `test_schema_regressions` updated; model unit test for upsert idempotency.
- **`<P>`-E1-03 — Celery sync task + Beat schedule.**
  AC: `sync_<P>_incremental` task following `sync_google_ads_sdk_incremental` structure
  (enumerate credentials → resolve sync state → trigger Airbyte connection / fetch → upsert →
  update state → `_trigger_warehouse_snapshot_refresh`). Beat entry in `settings.py`
  (`crontab(minute=0, hour="6-22")`, queue `CELERY_QUEUE_SYNC`). Eval: task test with mocked
  Airbyte/HTTP asserting state transitions + idempotent re-run (§7 L2).

### E2 — Warehouse / dbt (Scope: `dbt/`)
- **`<P>`-E2-01 — Staging performance model.**
  AC: `stg_<P>_ads_performance.sql` reads raw connector output, normalizes to the fact column
  contract, applies parish mapping (reuse Meta/Google seed). Per DD-1 Option A, distinct from any
  transparency model. Eval: dbt build + dbt tests (not_null/unique on grain) green; row-count and
  spend-sum sanity vs. a seeded fixture.
- **`<P>`-E2-02 — Union into fact + enable var.**
  AC: `all_ad_performance.sql` `enable_<P>` block points at the performance staging model and
  emits `source_platform='<P>'`; `enable_<P>` var defaults False, documented in `dbt_project.yml`.
  Eval: with `enable_<P>=true`, `fact_performance` contains `<P>` rows with the full column set and
  zero nulls in required columns; with the var false, fact is byte-identical to today (regression).
- **`<P>`-E2-03 — Snapshot builder includes `<P>`.**
  AC: the warehouse snapshot job that populates `TenantMetricsSnapshot.payload` includes `<P>`
  campaign/geo/parish/metrics slices. Eval: snapshot fixture test shows `<P>` keys present.

### E3 — Combined metrics (Scope: `backend/`)
- **`<P>`-E3-01 — Registry enablement.**
  AC: add `PLATFORM_<P>` to `COMBINED_SUPPORTED`, `_LABELS`, `COMBINED_ORDER` in
  `platform_registry.py`. Eval: `test_combined_platforms_only` extended — `?platforms=<P>` returns
  `<P>` data; omitting it excludes `<P>`.
- **`<P>`-E3-02 — Client scoping.**
  AC: `combined_metrics_service.resolve_client_scoping` resolves `<P>` account ids into the bundle
  and passes `client_scoped_<P>_ids` to the warehouse adapter; `WarehouseAdapter._apply_filters`
  honors it. Eval: `test_combined_client_id_scoping` extended — tenant A cannot see tenant B `<P>`
  accounts (RLS + scope). **Tenant-isolation eval is mandatory (§7 L4).**
- **`<P>`-E3-03 — Dataset status.**
  AC: `dataset_status` reflects `<P>` freshness where product requires per-source readiness
  (otherwise documented as warehouse-wide). Eval: `dataset_status` payload test.

### E4 — Frontend (Scope: `frontend/`)
- **`<P>`-E4-01 — Platform surface.**
  AC: color token in `styles/chartTheme.ts` (`PLATFORM_CHART_TOKENS.<P>`), `platformColor` case,
  `PROVIDER_LABELS` entry (Microsoft only), dataset-store key if a dedicated adapter is exposed,
  platform toggle shows `<P>` when `combined_supported` includes it. Eval: vitest for label/color;
  Storybook entry; `npm run build` + `npm run lint` clean.
- **`<P>`-E4-02 — Dashboard verification.**
  AC: with seeded `<P>` data, combined dashboard renders `<P>` in grids/charts/parish map and the
  platform filter toggles it. Eval: Playwright e2e (§7 L5) + preview screenshot.

### E5 — Evals & QA (Scope: `qa/` + `backend/tests` + `infrastructure/airbyte/sources/tests`)
- **`<P>`-E5-01 — Vertical-slice integration test.**
  AC: extend `backend/tests/integration/test_vertical_slice.py` to cover `<P>`: seeded raw →
  snapshot → `/api/metrics/combined/?platforms=<P>` returns expected aggregates. Eval: green in CI.
- **`<P>`-E5-02 — Contract check + CI wiring.**
  AC: add a `<P>` performance contract assertion to
  `infrastructure/airbyte/scripts/check_data_contracts.py` (fields, stream name, env keys), and
  wire `test_connector_smoke.py` into `.github/workflows/integration-smoke.yml`. Eval: contract
  script exit 0; CI job runs connector smoke.
- **`<P>`-E5-03 — Staging smoke checklist.**
  AC: an operator runbook `artifacts/sprint/<P>-staging-smoke-checklist.md` mirroring the GA4 /
  Google Ads Phase C checklists (provision → OAuth/creds → dashboard E2E → tenant isolation →
  freshness). Eval: doc review.

### E6 — Rollout (Scope: `backend/` + `docs/`)
- **`<P>`-E6-01 — Flags default-off + runbook.**
  AC: `ENABLE_<P>_*` and `enable_<P>` default False in all envs; `docs/runbooks/<P>-operations.md`
  written (triage order, re-sync, failure categories). Eval: release preflight green with flags off
  (must be a no-op when disabled).
- **`<P>`-E6-02 — Staged enablement.**
  AC: enable in staging behind flag, run E5-03 checklist with one real test account, archive
  evidence. Eval: go/no-go sign-off.

---

## 6. Per-source instantiation deltas

### 6.1 TikTok (pathfinder)
- Enum/credential/`PROVIDER_LABELS`: **already present** — skip E1-01.
- dbt: repoint existing `enable_tiktok` block from `stg_tiktok_transparency` to new
  `stg_tiktok_ads_performance` per DD-1; decide transparency block's fate.
- Connector source of truth: `infrastructure/airbyte/sources/tiktok_ads/` (raw fields: `country`→
  region, `placement_type`→device, `total_complete_payment`→conversion_value).
- Deliverable: this source's PRs are the **template** referenced by LinkedIn/Microsoft.

### 6.2 LinkedIn (replication)
- Enum/credential/labels: already present — skip E1-01.
- Connector deltas: URN extraction already normalizes ids (`urn:li:sponsoredCampaign:456`→`456`);
  `costInLocalCurrency`→spend, `DEVICE_TYPE` pivot→device.
- Expect E2/E3/E4 to be largely template copies; budget time mainly for LinkedIn's account/URN
  scoping in E3-02.

### 6.3 Microsoft Ads (generalization test)
- **Adds the groundwork the others had:** E1-01 credential provider `MICROSOFT`; platform enum
  `ClientPlatformAccount.PLATFORM_MICROSOFT` + `platform_registry` constants; **new** dbt
  `enable_microsoft` union block (none exists today).
- Connector source of truth: `infrastructure/airbyte/sources/microsoft_ads/` (already in
  `check_data_contracts.py`). Raw fields: `Country`→region, `DeviceType`→device,
  `Revenue`→conversion_value, `CurrencyCode`→currency.
- Treat completion as the signal that the template is platform-agnostic.

### 6.4 GA4 + Search Console (pilot promotion — separate track)
- Different lineage: `agg_ga4_daily` / `agg_search_console_daily` + existing
  `/api/analytics/web/{ga4,search-console}/` endpoints + `google_analytics` adapter.
- Work is **promotion + onboarding**, not net-new spine: (a) decide if/how web metrics join
  `/api/metrics/combined/` (likely stays a separate web surface, not blended with ad spend), (b)
  complete tenant onboarding, (c) credentials-gated staging smoke (`S5-ga4-staging-smoke-checklist`
  already exists). Keep `COMBINED_SUPPORTED` ad-only unless product explicitly wants blended web+ad.
- Gate the "join combined metrics?" question on Raj/Mira before any registry change.

---

## 7. Eval strategy (the gates)

Evals are **layered**; a ticket merges only when its layer's eval is green. Thresholds are the
contract — encode them as assertions, not vibes.

- **L0 Connector contract** (`infrastructure/airbyte/sources/tests/`): spec/discover/check + the
  canonical 14 fields + slice/lookback determinism. *Already green for all three.* Extend
  `check_data_contracts.py` per source (E5-02).
- **L1 Schema/regression** (`backend/tests/test_schema_regressions.py`): new models add required
  columns; existing facts unchanged when `enable_<P>=false` (byte-identical regression).
- **L2 Sync idempotency** (task tests): running the sync twice over the same window yields one row
  per grain key (no dupes), updates `last_success_at`, and classifies a forced error correctly.
- **L3 dbt data quality** (dbt tests): `not_null` on required fact columns, `unique` on
  `(tenant_id, source_platform, account_id, campaign_id, ad_group_id, ad_id, date_day)`,
  `accepted_values` on `source_platform`, spend-sum equals seeded fixture within 0 tolerance.
- **L4 Tenant isolation + scoping** (`test_combined_client_id_scoping`, `test_warehouse_client_scoping`):
  **mandatory, non-waivable.** Tenant A never sees tenant B `<P>` rows; RLS `app.tenant_id`
  preserved; empty scope → zeros (mirror `test_adapter_scope_parity`).
- **L5 End-to-end** (`test_vertical_slice` + Playwright in `qa/`): seeded raw → combined endpoint →
  dashboard renders `<P>`; parish map populated.
- **L6 Release preflight** (`manage.py backend_release_smoke` + gates): green with flags off
  (no-op) AND green with `<P>` enabled in staging.

**Eval harness convention:** each source gets one fixture pack under
`backend/tests/fixtures/<P>_performance/` (raw rows + expected snapshot + expected combined
aggregates) reused across L2–L5 so the same numbers are asserted end-to-end.

---

## 8. Chain-of-prompt playbook (drive one ticket at a time)

For each ticket, an engineer/agent runs this loop. Keep each PR inside one top-level folder.

1. **Contextualize** — "Read `AGENTS.md` §scope, this plan §2/§5/§6.x for `<P>`, and the file
   anchors for seam N. Restate the seam's input/output contract and the exact files you will
   touch. Do not touch other folders."
2. **Write the eval first** — "Add the L<k> eval/test for `<P>`-E<x>-<n> using the
   `<P>_performance` fixture pack. It must fail now (red) for the right reason. Show me the failure."
3. **Implement to green** — "Implement the minimal change in `<scope>` to pass the eval. Mirror the
   referenced template (`<template file:line>`). Keep diffs within `<scope>`."
4. **Regression sweep** — "Run L1 + the suite for this folder
   (`cd backend && pytest -q` / `dbt build` / `npm test -- --run`). Confirm `enable_<P>=false`
   leaves existing facts/tests unchanged."
5. **Isolation gate (if E3)** — "Run L4. Prove tenant A cannot read tenant B `<P>` data. Paste the
   assertion."
6. **Document + matrix** — "Update `integration-data-contract-matrix.md` and the source runbook for
   what changed. Note any contract change in `api-contract-changelog.md`."
7. **Commit** — conventional commit scoped to the folder
   (`feat(backend):` / `feat(dbt):` / `feat(frontend):`), Co-Authored-By trailer. One ticket → one
   focused PR.
8. **Handoff** — "Summarize: eval added, files touched, evals green, residual risk, next ticket
   unblocked."

> Rule of thumb: if a prompt would make you edit two top-level folders, it's two tickets.

---

## 9. Governance & guardrails

- **Scope freeze:** one top-level folder per PR unless Raj (integration) **and** Mira
  (architecture) approve a cross-cutting change (`AGENTS.md`). Most tickets here are single-folder
  by construction.
- **Flags default-off:** every source ships dark. `ENABLE_<P>_*` and `enable_<P>` default False;
  release preflight must pass as a no-op when disabled before any staging enablement.
- **Tenant isolation is non-negotiable:** L4 eval gates every E3 ticket; never weaken RLS or
  `SET app.tenant_id`.
- **Secrets:** only `.env.sample`/`.example` placeholders; real creds live in operator envs.
- **Timezone:** `America/Jamaica` for all schedules and windows.
- **No new frameworks:** stay on Django/DRF/Celery + React/Vite; no FastAPI/Next.js.
- **Definition of Done (per source):** L0–L6 green · flags off by default · runbook +
  matrix updated · staging smoke evidence archived · Raj/Mira sign-off.

---

## 10. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Transparency vs performance lineage collision (DD-1 unresolved) | High if skipped | Double-counted spend | Ratify DD-1 Option A before E2; L3 spend-sum eval |
| Airbyte connector reliability in prod (alpha connectors) | Med | Stale/empty data | DD-2 default Airbyte + freshness eval; SDK fallback only if eval fails |
| Currency mixing across platforms in one fact | Med | Wrong totals | Decide reporting-currency normalization in E0; assert in L3 |
| `ad_group_id`↔`adset_id` / parish mapping drift | Med | Misattributed rows | Reuse Meta/Google parish seed; L3 unique-grain test |
| Scope creep across folders | Med | Breaks scope freeze | One-folder-per-ticket rule (§8); template replication |
| Enabling a source flips existing dashboards | Low | Regression | `enable_<P>=false` byte-identical regression eval (L1/E2-02) |
| GA4/SC blended into ad combined metrics by accident | Low | Confused metrics | Keep web surface separate unless product+Mira approve |

---

## Appendix A — Ticket index (lift into tracker)

Order: do all TikTok tickets to DoD, then LinkedIn, then Microsoft. GA4/SC is a parallel-eligible
separate track. `E1-01` applies to Microsoft only.

| Ticket | Title | Scope | Eval gate |
|---|---|---|---|
| DD-1 | Ratify performance-vs-transparency lineage | docs | review |
| DD-2 | Ratify sync transport (Airbyte default) | docs | review |
| tiktok-E0-01 | TikTok design note + matrix row | docs | review |
| tiktok-E1-02 | TikTokAdsSyncState + daily model | backend | L1 |
| tiktok-E1-03 | sync_tiktok_incremental + Beat | backend | L2 |
| tiktok-E2-01 | stg_tiktok_ads_performance | dbt | L3 |
| tiktok-E2-02 | union + enable_tiktok repoint | dbt | L1/L3 |
| tiktok-E2-03 | snapshot includes tiktok | dbt/backend | L3 |
| tiktok-E3-01 | COMBINED_SUPPORTED += tiktok | backend | L0-combined |
| tiktok-E3-02 | client scoping + isolation | backend | **L4** |
| tiktok-E3-03 | dataset status | backend | L1 |
| tiktok-E4-01 | frontend platform surface | frontend | vitest/build |
| tiktok-E4-02 | dashboard verification | frontend | L5 |
| tiktok-E5-01 | vertical-slice test | backend | L5 |
| tiktok-E5-02 | contract check + CI wiring | infra/ci | L0 |
| tiktok-E5-03 | staging smoke checklist | docs | review |
| tiktok-E6-01 | flags off + runbook | backend/docs | L6 |
| tiktok-E6-02 | staged enablement | ops | go/no-go |
| linkedin-E0-01 … E6-02 | replicate template (skip E1-01) | per-folder | L0–L6 |
| microsoft-E0-01 … E6-02 | replicate + **E1-01 credential/enum** + new dbt block | per-folder | L0–L6 |
| ga4sc-PROMO-01 | decide web→combined join (Raj/Mira) | docs | review |
| ga4sc-PROMO-02 | GA4/SC tenant onboarding + smoke | backend/infra | credentials-gated |

---

_This plan is intentionally eval-first and single-folder-per-ticket so the work proceeds in large
but safe chunks. Start by ratifying DD-1/DD-2, then run the TikTok column to DoD as the template._
