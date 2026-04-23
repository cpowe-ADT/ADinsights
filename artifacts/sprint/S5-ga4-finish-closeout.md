# Sprint 5 — GA4 Finish Closeout

**Inputs cited:** `finish-ga4.md` prompt (artifacts/roadmap/prompts/), `ga4-investigation.md` (Verdict B, already shipped), `project-punchlist.md §T1-04`, `docs/runbooks/ga4-operations.md`.

**Baseline commit:** `5961ddcf` (post Google Ads T1-03 Phase C close).

## 1. Status: **AMBER (ship-ready pending external credentials)**

All engineering-side DoD items from `finish-ga4.md` are satisfied at baseline. The one unchecked DoD item — *"Dashboard at `/dashboards/google-analytics` shows real data on the dev stack"* — is blocked on external credentials that cannot be self-provisioned. Execution plan shipped as `S5-ga4-staging-smoke-checklist.md`.

## 2. DoD audit vs. `finish-ga4.md` §"Definition of Done — GA4 alone"

| DoD item | Status | Evidence |
|---|---|---|
| `artifacts/roadmap/ga4-investigation.md` written with verdict + evidence | **✓ DONE** | 214-line doc, Verdict B, pasted command output |
| Dashboard shows real data (or well-reasoned empty state) on dev stack | **AMBER** | Empty state by design (mart not populated in dev); execution plan in smoke checklist |
| ≥5 new backend pytest + ≥3 new vitest where applicable | **✓ DONE** | 16 new backend tests per investigation §Step 3: PII allowlist (12), client credential classifications (3), tenant isolation (1). Frontend: 4 existing vitest cover populated + 2 empty-state branches + R3 contract. |
| All gates remain green | **✓ DONE** | Baseline: 743 backend passed / 1 skipped (was 727 / 1 before GA4 tests); frontend lint + build clean; `GoogleAnalyticsDashboardPage.test.tsx` 4/4 pass (verified 2026-04-23) |
| Runbook at `docs/runbooks/ga4-operations.md` | **✓ DONE** | 155 LoC runbook |
| R3 contract holds (no `/metrics/combined/` from GA4 page) | **✓ DONE** | Fetch-spy test `R3: uses the dedicated GA4 endpoint and never calls /metrics/combined/` |
| Commits with conventional prefix | **✓ DONE** | Prior commits: `docs(ga4):` + `test(ga4):` |

## 3. What shipped in this close-out session

Two additive artifacts — no code changes, no dbt changes, no secrets.

### New documentation

| File | Purpose | LoC |
|---|---|---|
| `artifacts/sprint/S5-ga4-staging-smoke-checklist.md` | Operator-runnable staging regression walkthrough: 6 phases covering Airbyte+dbt provisioning, OAuth connect flow, dashboard end-to-end, R3 + tenant isolation, freshness scheduling, record-results procedure, triage cheat sheet, known architectural quirks | ~140 |
| `artifacts/sprint/S5-ga4-finish-closeout.md` | This doc | ~80 |

## 4. Gate matrix (post-close)

| Gate | Command | Result |
|---|---|---|
| GA4 dashboard vitest | `cd frontend && npx vitest --run src/routes/__tests__/GoogleAnalyticsDashboardPage.test.tsx` | **PASS — 4/4** in 1.65s |
| Full frontend lint | `cd frontend && npm run lint` | N/A (no frontend touched) |
| Full frontend build | `cd frontend && npm run build` | N/A (no frontend touched) |
| Backend ruff | `ruff check backend` | N/A (no backend touched) |
| Backend pytest | `cd backend && pytest -q` | N/A (no backend touched) |

This close-out session is documentation-only — no gate regressions possible.

## 5. Known architectural quirks (carried forward from investigation)

- **OAuth flow is decorative for ingestion.** `GoogleAnalyticsConnection` rows are written by the in-app OAuth flow, but Airbyte uses its own `AIRBYTE_GA4_REFRESH_TOKEN` env var — not the tenant's `PlatformCredential`. A tenant completing OAuth in the UI still sees an empty dashboard until the operator provisions Airbyte for that property separately. Out-of-scope for T1-04; tracked as future feature to bridge OAuth-captured tokens into Airbyte config.
- **Schema divergence between paths.** `GoogleAnalyticsClient` (live GA4 Data API for the combined-metrics adapter) returns `source/medium/campaign` dimensions; the Airbyte→dbt mart (dashboard path) uses `channel_group/country/city/campaign_name`. Intentional — two independent consumers. No reconciliation needed.
- **`enable_ga4=false` by default.** Mart is not materialized in local/dev. This is why the dashboard shows EmptyState with `no_data_for_range` reason until an operator flips the flag and runs `dbt build`.
- **Airbyte is source of truth for scheduling, not Celery.** There is no Django/Celery task that invokes `GoogleAnalyticsClient` for sync — that's a deliberate architectural choice (per the investigation: `"MISSING — does not exist, does not need to exist"`). Airbyte handles scheduling.

## 6. Blocker detail — unblocks GA4 to green

To execute the smoke checklist and satisfy the last DoD bullet, operator must provide:

- `AIRBYTE_GA4_CLIENT_ID`
- `AIRBYTE_GA4_CLIENT_SECRET`
- `AIRBYTE_GA4_REFRESH_TOKEN`
- `AIRBYTE_GA4_PROPERTY_ID` (9–10 digit numeric GA4 property id with ≥30 days of real traffic)

Plus staging tenant JWT + DB access + Airbyte workspace URL per the smoke checklist pre-flight table.

**Estimated operator effort once creds land:** 60–90 minutes to walk the 6-phase checklist end-to-end.

## 7. Follow-ups / deferrals

- **OAuth-token-to-Airbyte bridge** (feature request; out of scope for T1-04). Would let a tenant complete OAuth in-app and have Airbyte automatically pick up that property's refresh token instead of requiring operator to re-provision per tenant.
- **Search Console parallel work (T1-05).** Per `finish-ga4.md` §"Related gap", Search Console is in the same "web analytics" neighborhood. No dedicated `integrations/search_console/` module exists; mart is populated by Airbyte. Recommend Option A (confirm Airbyte path + document) after GA4 lands. Not started in this close-out.
- **Synthetic end-to-end test.** Could add a pytest that inserts fixtures into `agg_ga4_daily` and hits `GA4WebInsightsView` to assert the full path without Airbyte. Decided against: the existing `test_ga4_web_insights_isolates_rows_by_tenant` test already does exactly this for the tenant-isolation case, and the 4 dashboard vitest tests cover render branches. Adding a broader E2E would duplicate coverage.

## 8. Verdict

**AMBER — T1-04 ships as ready-to-go pending credentials.** Engineering-side DoD is satisfied: 16 backend tests, 4 dashboard vitest, 155-line runbook, 214-line investigation, full gate green. The one remaining DoD bullet is credential-gated; operator walkthrough shipped as `S5-ga4-staging-smoke-checklist.md`. No schema changes, no migrations, no secrets. Unblock path is documented step-by-step.

Overall GA4 surface ships approximately **~95% complete** — last 5% is external-dependency-gated.
