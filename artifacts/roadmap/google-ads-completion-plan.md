# Google Ads — Completion Plan

**Status at writing:** unified workspace UI shipped (Sprint 3, April 2026), SDK wired for ~70% of endpoints, several action/action-polling gaps remain.

**Completion estimate:** ~70–75% of "production-ready" done. Remaining work: ~15–25 days focused effort for one senior engineer.

**Commit baseline:** `7a0e701b` (viz-kit + Sprint 3) is the last known-good state of the Google Ads surface.

---

## ⚠️ CORRECTION NOTE (added during adversarial audit)

An adversarial audit surfaced material inaccuracies in the GA-A\* task definitions below. Verified against source:

1. **`GoogleAdsBudgetPacingView` EXISTS** at `backend/analytics/google_ads_views.py:1308` and is routed at `backend/analytics/urls.py:95`. It returns a **tenant-level rollup**, not per-campaign rows. GA-A1 is therefore an **extension** of an existing view, not a new endpoint.
2. **`GoogleAdsRecommendationsView` EXISTS** at `google_ads_views.py:1413` / routed at `urls.py:105`. The `GoogleAdsSdkRecommendation` model at `backend/integrations/models.py:1228` **already has a `dismissed` boolean field** (indexed at line 1241). GA-A2 is adding a **dismiss action endpoint + UI button**, NOT a new dismissals table.
3. **`GoogleAdsExportCreateView` / `ExportStatusView` / `ExportDownloadView` ALL EXIST** at lines 1599/1673/1690 of `google_ads_views.py` (routed at `urls.py:109-118`). `frontend/src/lib/googleAdsDashboard.ts:109-121` already calls them. The actual gap is that `ReportsTabSection.tsx:89-92` fires `fetchGoogleAdsExportStatus` **once** — there's no polling loop. GA-A3 is a **frontend polling wire-up**, not a backend build.

The GA-A*/B*/C\* text below is left as the original aspiration. **Use the verified scope in `prompts/finish-google-ads.v2.md` Pre-Flight section as the authoritative task definition.** Do not build duplicate endpoints. Always `grep` the view names above before writing a single line of backend code.

## How to read this file

- Each task has an **ID**, **effort** (S ≤1d, M 1–3d, L 3–5d), **dependencies**, and enough detail to start.
- Phases are **sequential** for Google Ads. Within a phase tasks can run parallel where marked.
- When you pick up a task, grep the file paths cited to get current line numbers (they drift).
- `[NEW-ENDPOINT]` = backend work needed. `[UI-ONLY]` = frontend only.

## Current gap inventory (verified)

| #   | Gap                                                                            | File cite                                                                                                  | Phase |
| --- | ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------- | ----- |
| 1   | Pacing tab: per-campaign budget variance endpoint                              | `frontend/src/components/google-ads/workspace/tab-sections/PacingTabSection.tsx` (search `[NEW-ENDPOINT]`) | A     |
| 2   | Recommendations: dismiss action wired in UI but backend integration incomplete | `frontend/src/components/google-ads/workspace/tab-sections/RecommendationsTabSection.tsx`                  | A     |
| 3   | Reports: list-saved-reports endpoint missing entirely                          | `frontend/src/components/google-ads/workspace/tab-sections/ReportsTabSection.tsx`                          | A     |
| 4   | Reports: export-job status polling unwired (jobs queued but no UI updates)     | same as #3                                                                                                 | A     |
| 5   | Change log pagination — only recent events visible                             | `frontend/src/components/google-ads/workspace/tab-sections/ChangesTabSection.tsx`                          | B     |
| 6   | Saved-view reconciliation check (client-state drift)                           | `frontend/src/routes/google-ads/GoogleAdsReportsPage.tsx`                                                  | B     |
| 7   | Integration tests for tab→endpoint wiring                                      | `frontend/src/components/google-ads/workspace/__tests__/` + `backend/tests/test_google_ads_*.py`           | C     |
| 8   | IS% (Impression Share) — permanent deferral, not a gap                         | `frontend/src/components/google-ads/workspace/WorkspaceKpiStrip.tsx:19-22`                                 | —     |
| 9   | Per-campaign/per-asset daily series — permanent API limitation                 | `artifacts/sprint/S3-architect-design.md §6.2`                                                             | —     |

---

## Phase A — Unblock the 3 incomplete tabs (8–11 days)

Goal: Pacing, Recommendations, Reports tabs move from ⚠️ partial to ✅ shipped.

### GA-A1 — Per-campaign budget variance endpoint `[NEW-ENDPOINT]` (L, 3–5d)

- **Backend**: new endpoint `GET /api/google-ads/budgets/pacing/` returning per-campaign rows `{campaign_id, campaign_name, budget_amount, spend_mtd, pace_pct, projected_eom, variance}`
- Data source: `google_ads_campaigns` table joined with daily metrics mart for MTD spend
- Tenant + client_id scoping per existing patterns in `backend/integrations/google_ads_views.py`
- **Frontend**: in `PacingTabSection.tsx`, replace `[NEW-ENDPOINT]` stub with `DistributionBar` driven by new endpoint; KPI tiles show total budget, total spend, avg pace, over-pace count
- **Tests**: backend pytest (tenant isolation + date math), frontend vitest (renders, empty state, error state)
- **DoD**: Pacing tab no longer shows "[NEW-ENDPOINT]" marker; `grep -r "\[NEW-ENDPOINT\]" frontend/src/components/google-ads/workspace/tab-sections/PacingTabSection.tsx` returns nothing

### GA-A2 — Recommendations dismiss action (M, 2–3d)

- **Backend**: wire `POST /api/google-ads/recommendations/<id>/dismiss/` — calls `GoogleAdsService.RecommendationService.DismissRecommendation` through the SDK; persists dismissal in `google_ads_recommendation_dismissals` table so repeat views don't re-show
- Add `dismissed_at` + `dismissed_by_user_id` + `dismiss_reason` (optional) columns
- **Frontend**: `RecommendationsTabSection.tsx` — wire the existing dismiss button to POST, optimistic remove from list, rollback on failure with toast
- Accept-recommendation action is a follow-up — **out of scope for A2** (different API risk profile, needs product review)
- **Tests**: backend pytest (SDK error paths, idempotency), vitest (optimistic update + rollback)
- **DoD**: clicking dismiss on a recommendation removes it and a refresh confirms it's gone

### GA-A3 — Report list + export polling (M, 2–3d)

Two sub-tasks, do together:

- **GA-A3a Report list endpoint** — `GET /api/google-ads/reports/` returns user's saved reports `{id, name, type, schedule, last_run_at, last_status}`. Likely already has a model; just needs the read endpoint + serializer + viewset wiring.
- **GA-A3b Export job polling** — frontend `ReportsTabSection.tsx`: when user kicks off an export, poll `GET /api/google-ads/export-jobs/<id>/` every 3s for up to 60s; show status pill (queued/running/complete/failed); surface download link on complete. Uses existing `ReportExportJob` model.
- **DoD**: Reports tab renders saved reports list; kicking an export shows progression; download link appears on completion

---

## Phase B — Polish (3–4 days)

Goal: tabs go from "works" to "feels finished."

### GA-B1 — Change log pagination (S, 1–2d)

- Cursor-based or page-based pagination on `GET /api/google-ads/changes/` (backend likely already supports limit/offset; verify)
- **Frontend**: `ChangesTabSection.tsx` — add "Load more" button or infinite scroll; add date-range filter
- **DoD**: user can navigate past the first page of changes

### GA-B2 — Saved-view reconciliation check (S, 1–2d)

- Backend: add `GET /api/google-ads/saved-views/<id>/verify/` that re-runs the view's query shape against the current API schema; flags drift if Google added/removed fields
- **Frontend**: `GoogleAdsReportsPage.tsx` — small warning banner if any saved view reports drift
- Low priority — nice-to-have

---

## Phase C — Harden + document (5–7 days)

Goal: CI green on full Google Ads surface with real data shapes, and the SDK-hybrid architecture is documented.

### GA-C1 — Integration test suite for tab↔endpoint wiring (L, 3–4d)

For each of the 10 tab sections, write one integration test that:

1. Mocks the expected response shape from the backend
2. Asserts the tab renders KPIs + chart + table without error
3. Exercises the empty/loading/error branches

Put them in `frontend/src/components/google-ads/workspace/__tests__/*.integration.test.tsx`. Use MSW or vitest fetch-mock.

Backend side: ensure every new endpoint above (A1, A2, A3) has tenant-isolation + client-id-scoping + error-path tests in `backend/tests/test_google_ads_*.py`.

### GA-C2 — Document SDK + Airbyte hybrid as permanent (S, 1d)

The CLAUDE.md line "Google Ads SDK migration in progress (SDK with Airbyte fallback)" implies "in progress → SDK only eventually." Reality is simpler: **some metrics are only available via Airbyte** (per-campaign/per-asset daily series), so the hybrid is permanent.

- Update `docs/runbooks/google-ads-*.md` (create if missing) with:
  - Which endpoints use SDK directly (campaigns, keywords, assets, conversions, budgets, changes, saved-views, recommendations, reports)
  - Which endpoints use Airbyte (per-campaign daily, per-asset daily)
  - How to add a new endpoint (which side, why, test pattern)
- Update `docs/project/integration-data-contract-matrix.md` Google Ads row to reflect hybrid model
- Update `CLAUDE.md` line 119 — remove "migration in progress", replace with "hybrid SDK + Airbyte architecture"

### GA-C3 — Regression test against Google Ads staging (M, 2–3d)

Manual or scripted — point the local dev stack at a real Google Ads test account, click through all 10 tabs, capture any unexpected empty states or errors. Mostly a confidence-building exercise; documents that the real API shapes match what the code expects.

---

## What's out of scope forever

- **IS% (Impression Share)**: Google Ads API does not expose this metric. The KPI strip ships 4 tiles. Don't revisit unless the API changes.
- **Per-campaign/per-asset daily performance**: API doesn't expose intraday granularity. Stays on Airbyte mart. Frontend fallback to top-10 DistributionBar is the right answer.
- **Accept-recommendation action**: different API risk profile from dismiss. Requires product + legal review. Track separately.

## Phase summary

| Phase                 | Effort | Blocker?               | When                       |
| --------------------- | ------ | ---------------------- | -------------------------- |
| A — 3 incomplete tabs | 8–11d  | Yes (blocks "GA ship") | Now                        |
| B — Polish            | 3–4d   | No                     | After A                    |
| C — Hardening + docs  | 5–7d   | No                     | After A, ideally before GA |

**Total Google Ads to done: ~16–22 working days.** Add 2–3 days slack for PR review + staging smoke.
