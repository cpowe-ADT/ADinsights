# Sprint Program Design — Meta + Google Ads + Combined Bulletproof Pass

**Input artifacts cited:**

- `/Users/thristannewman/ADinsights/artifacts/plan.md`
- `/Users/thristannewman/ADinsights/artifacts/audit/audit-report.json`
- `/Users/thristannewman/ADinsights/artifacts/synthesis/synthesis-report.md`
- `/Users/thristannewman/ADinsights/artifacts/triage/B0-triage.md`
- `/Users/thristannewman/ADinsights/artifacts/fixes/B1-fix-report.md`
- `/Users/thristannewman/ADinsights/artifacts/viz/sprints-plan.md`
- `/Users/thristannewman/ADinsights/artifacts/verify/meta-verification.json`
- `/Users/thristannewman/ADinsights/artifacts/verify/google-verification.json`
- `/Users/thristannewman/ADinsights/artifacts/verify/combined-verification.json`

---

## 1. Current State Assessment

### GREEN (confirmed landed)

| Item                                                                       | Evidence                               |
| -------------------------------------------------------------------------- | -------------------------------------- |
| Backend 727 tests pass, lint clean, build clean                            | synthesis-report.md §Test Results      |
| Frontend build clean, lint clean                                           | synthesis-report.md + B1-fix-report.md |
| High-severity Meta adapter scoping (M1, M4, M6 — R7 reconciliation effect) | synthesis-report.md APPLIED            |
| Meta account row click sets useMetaStore.filters.accountId (M2)            | APPLIED                                |
| Meta empty-state loading guard (M3, M5, M7)                                | APPLIED                                |
| Meta M16 loadPostTimeseries overrides param                                | APPLIED                                |
| resolveRoutePlatformScope extracted + 27 unit tests (R6)                   | APPLIED                                |
| Google Ads B1 platforms=google_ads in buildCommonParams                    | APPLIED                                |
| Google Ads B6/B7/B8 exec + table + budget + campaign detail scope params   | APPLIED                                |
| Google Ads FilterBar unhidden on /dashboards/google-ads (B1 hot-fix)       | B1-fix-report.md GREEN                 |
| Google Ads empty-state guard when no customer selected                     | B1-fix-report.md                       |
| Combined B-PLAT-01 scoped→unscoped transition in DashboardLayout           | APPLIED                                |
| Combined B-PLAT-02 empty byPlatform EmptyState                             | APPLIED                                |
| Combined B-SAVED-01/02 SavedDashboardPage platforms restore + dep array    | APPLIED                                |
| EmptyState reasonCode prop + data-reason-code attribute                    | APPLIED                                |

### YELLOW / suspect (landed but unverified IRL on a fresh session)

| Item                                                                                                                           | Risk                                    | From                                         |
| ------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------- | -------------------------------------------- |
| R7 reconciliation: does it fire correctly before first combined-dashboard fetch?                                               | Timing race if effect deps stale        | synthesis-report.md §DashboardLayout summary |
| Google Ads workspace global FilterBar: does it actually populate dropdown options in demo mode?                                | clientOptions=[] in demo; no affordance | B0-triage.md Q2                              |
| B2 seed effect removal: workspace customer_id now sourced exclusively from useDashboardStore — is this correct on a cold load? | Mount order                             | B1-fix-report.md                             |
| /dashboards/platforms stale row flash (B-PLAT-01): one render cycle window remains                                             | Effect fires after child mount          | combined-verification.json                   |

### RED / explicitly broken (user-stated or deferred in synthesis)

| Item                                                                                                                              | Severity         | Deferred reason                 |
| --------------------------------------------------------------------------------------------------------------------------------- | ---------------- | ------------------------------- |
| B-CAMP-01: CampaignDashboard row-level platform filter in useDashboardStore selectors — campaign rows from wrong platform survive | medium           | "store surgery out of time-box" |
| B-CREA-01: CreativeDashboard same problem for creatives selector                                                                  | medium           | deferred                        |
| B-AUD-01: AudienceDashboard EmptyState on loaded+empty (silent blank chart)                                                       | medium           | time-boxed out                  |
| B-CAMP-02: Duplicate CampaignDashboard empty-state branches                                                                       | low              | cosmetic                        |
| B-PLAT-03: Hardcoded Facebook/Instagram KPI labels on combined platforms page                                                     | low              | cosmetic                        |
| DataSources.test.tsx: 10 pre-existing failures (scrollIntoView mock missing)                                                      | low/pre-existing | unrelated to dashboards         |
| analytics/fx.py:189: pre-existing ruff F841                                                                                       | low/pre-existing |                                 |
| Google Ads B4: colon encoding in customer_id (theoretical)                                                                        | low              | "no fix needed"                 |

---

## 2. Sprint Goals & Non-Goals

### Goals

1. **Phase 1A** — Every `/dashboards/meta/*` route renders correctly with FilterBar + account picker, fetches meta-scoped data, handles empty/loading/error states, produces no console errors, passes unit and smoke tests on a fresh session.
2. **Phase 1B** — Every `/dashboards/google-ads` route (workspace unified mode) renders correctly with FilterBar + customer picker, fetches google-scoped data, handles empty/loading/error states, passes unit and smoke tests on a fresh session.
3. **Phase 2** — Every combined-view route (`/dashboards/platforms`, `campaigns`, `creatives`, `budget`, `audience`, `map`) renders correctly with cross-platform data, correct account scoping, no stale rows, correct empty states.
4. **Phase 3** — Full backend pytest, full frontend vitest (including fixing the pre-existing DataSources scrollIntoView failure), lint, build pass; written manual smoke checklist for user.

### Non-Goals

- Visualization upgrade (sprints-plan.md Sprint 1–4). Do not add new charts.
- New backend endpoints (no new API routes).
- Auth or RLS changes.
- GA4 / Search Console pages (these are already clean — no combined call).
- CsvUpload / CsvUploadDetail routes (in-progress feature, out of scope).
- /me ProfilePage (in-progress feature, out of scope).
- SavedDashboardPage builder serialization format changes.
- SDK migration completion for Google Ads (out of scope).

---

## 3. Phase Structure with Chain Handoffs

```
Phase 1A (Meta)         Phase 1B (Google Ads)
     |                        |
  C1A-audit               C1B-audit      <-- run in PARALLEL
     |                        |
  C2A-fix                 C2B-fix        <-- each gated on its own audit
     |                        |
  C3A-test               C3B-test        <-- each gated on its own fix
     |                        |
     +----------+-------------+
                |
           Phase 2 (Combined) -- gated on 1A GREEN AND 1B GREEN
                |
           C1C-audit
                |
           C2C-fix
                |
           C3C-test
                |
           Phase 3 (E2E) -- gated on Phase 2 GREEN
                |
            C4-e2e
```

---

### Phase 1A — Meta Dashboards Bulletproof

**Agent C1A-audit**

- Role: Deep read-only IRL audit of all `/dashboards/meta/*` routes
- Inputs:
  - `artifacts/verify/meta-verification.json` (all 16 bugs; focus on M1–M7, M12, M16)
  - `artifacts/synthesis/synthesis-report.md` (what was APPLIED vs DEFERRED)
  - `frontend/src/routes/MetaAccountsPage.tsx`
  - `frontend/src/routes/MetaInsightsDashboardPage.tsx`
  - `frontend/src/routes/MetaCampaignOverviewPage.tsx`
  - `frontend/src/routes/MetaConnectionStatusPage.tsx`
  - `frontend/src/routes/MetaPagesListPage.tsx`
  - `frontend/src/routes/MetaPageOverviewPage.tsx`
  - `frontend/src/routes/MetaPagePostsPage.tsx`
  - `frontend/src/routes/MetaPostDetailPage.tsx`
  - `frontend/src/routes/DashboardLayout.tsx` (R7 reconciliation effect — read-only)
  - `frontend/src/state/useMetaStore.ts`
  - `frontend/src/lib/dashboardFilters.ts`
  - `frontend/src/components/FilterBar.tsx`
- Scope: Files under `frontend/src/routes/Meta*.tsx`, `frontend/src/state/useMetaStore*`, `frontend/src/routes/DashboardLayout.tsx` (read-only)
- Must NOT touch: backend, combined routes, Google Ads routes
- Output artifact: `artifacts/sprint/phase1a-meta-audit.json`
  - Schema: `{ schema_version, agent_id: "C1A", timestamp, routes: [ { route, file, status: "green"|"yellow"|"red", bugs_confirmed: [ { id, severity, description, file, line, evidence } ], new_bugs: [...], fix_required: bool } ], cross_cutting: [ { concern, files_affected, severity } ], summary_verdict: "green"|"yellow"|"red" }`
- Definition of Done: Every route in the Meta cluster audited. For each route: network params checked (platforms=meta_ads or none for status), account propagation traced, empty/loading/error state confirmed. Known deferred bugs (M8–M11 "clean") re-verified. Any new bugs discovered documented.
- Tools allowed: Read-only (Glob, Grep, Read). No edits. No dev server.
- Time-box: 20 minutes

**Agent C2A-fix**

- Role: Apply fixes to Meta dashboard cluster
- Inputs:
  - `artifacts/sprint/phase1a-meta-audit.json` (primary — all red/yellow items)
  - `artifacts/verify/meta-verification.json` (fix_patches sections for each bug)
  - `artifacts/synthesis/synthesis-report.md` (deferred items: none remaining for Meta; check context)
  - All source files listed above for C1A-audit
- Scope: May edit `frontend/src/routes/Meta*.tsx`, `frontend/src/state/useMetaStore*.ts`, `frontend/src/routes/DashboardLayout.tsx` (reconciliation effect only — must not change platform-scope effect), `frontend/src/routes/__tests__/Meta*.test.tsx`
- Must NOT touch: backend, combined routes, Google Ads routes, `frontend/src/lib/dashboardFilters.ts` (already has 27 tests — preserve), FilterBar.tsx
- Output artifact: `artifacts/sprint/phase1a-meta-fix.md`
  - Schema: `# Phase 1A Meta Fix Report\n## Files Modified (table: file | change summary | lines +/-)\n## Tests Added (table: file | kind | cases)\n## Test Results (targeted suite output)\n## Build Output\n## Deferred (with reasons)\n## Status: GREEN|YELLOW|RED`
- Definition of Done: Targeted vitest suite for Meta files passes. Build clean. No new TypeScript errors introduced.
- Tools allowed: Read + Edit. Run `cd frontend && npx vitest run` on targeted files. Run `npm run build`. No full stack.
- Time-box: 35 minutes

**Agent C3A-test**

- Role: Validate Meta cluster against Phase 1A DoD checklist
- Inputs:
  - `artifacts/sprint/phase1a-meta-fix.md`
  - `artifacts/sprint/phase1a-meta-audit.json`
  - Phase 1A DoD checklist (Section 5 of this document)
- Scope: Run test suites; write missing test cases if DoD criteria lack coverage; read source to verify
- Must NOT touch: application source code (test files only, if strictly necessary to add coverage)
- Output artifact: `artifacts/sprint/phase1a-meta-test.md`
  - Schema: `# Phase 1A Meta Test Report\n## DoD Checklist Results (table: criterion | pass/fail | evidence)\n## Test Suite Summary (file counts, pass/fail)\n## Console Error Check (list any)\n## Unresolved Issues\n## VERDICT: GREEN|YELLOW|RED`
- Definition of Done: All Phase 1A DoD criteria pass (Section 5). Targeted vitest GREEN. Build clean.
- Tools allowed: Read + Edit (test files only). Run vitest targeted suite. Run lint + build.
- Time-box: 20 minutes

---

### Phase 1B — Google Ads Dashboards Bulletproof

**Agent C1B-audit**

- Role: Deep read-only IRL audit of `/dashboards/google-ads` (workspace unified mode)
- Inputs:
  - `artifacts/verify/google-verification.json` (B1–B8; focus on B2, B3, B5 deferred E2E, B4)
  - `artifacts/fixes/B1-fix-report.md` (what was changed in hot-fix)
  - `artifacts/triage/B0-triage.md` (Q1, Q2, Q3 landmines)
  - `artifacts/synthesis/synthesis-report.md` (APPLIED items for google)
  - `frontend/src/routes/google-ads/GoogleAdsWorkspacePage.tsx`
  - `frontend/src/hooks/useGoogleAdsWorkspaceData.ts`
  - `frontend/src/components/google-ads/workspace/WorkspaceHeader.tsx`
  - `frontend/src/components/google-ads/workspace/types.ts`
  - `frontend/src/components/google-ads/GoogleAdsDataTablePage.tsx`
  - `frontend/src/routes/google-ads/GoogleAdsExecutivePage.tsx`
  - `frontend/src/routes/google-ads/GoogleAdsBudgetPage.tsx`
  - `frontend/src/routes/google-ads/GoogleAdsCampaignDetailPage.tsx`
  - `frontend/src/routes/DashboardLayout.tsx` (hideGlobalFilters predicate — read only)
  - `frontend/src/routes/google-ads/GoogleAdsLegacyRedirects.tsx`
  - `frontend/src/router.tsx` (GOOGLE_ADS_WORKSPACE_UNIFIED flag wiring)
- Scope: Files under `frontend/src/routes/google-ads/**`, `frontend/src/hooks/useGoogleAdsWorkspaceData.ts`, `frontend/src/components/google-ads/**`
- Must NOT touch: backend, Meta routes, combined routes
- Output artifact: `artifacts/sprint/phase1b-google-audit.json`
  - Schema: `{ schema_version, agent_id: "C1B", timestamp, workspace_tabs_audited: [...], routes: [ { route, component, flag_mode, status, bugs_confirmed: [...], new_bugs: [...] } ], cross_cutting: [...], sdk_migration_risk: { severity, description, mitigation }, summary_verdict }`
- Definition of Done: Every workspace tab audited (overview, campaigns, search, pmax, assets, conversions, pacing, changes, recommendations, reports). FilterBar account propagation to workspace customer_id traced end-to-end. Empty state on no customer verified. SDK migration risk documented.
- Tools allowed: Read-only (Glob, Grep, Read). No edits. No dev server.
- Time-box: 20 minutes

**Agent C2B-fix**

- Role: Apply fixes to Google Ads workspace cluster
- Inputs:
  - `artifacts/sprint/phase1b-google-audit.json` (primary)
  - `artifacts/verify/google-verification.json` (fix_patches for B2, B3, B5)
  - `artifacts/triage/B0-triage.md` (Q3 landmine: invisible empty state, workspace SDK risk)
  - All source files listed for C1B-audit
- Scope: May edit `frontend/src/routes/google-ads/*.tsx`, `frontend/src/hooks/useGoogleAdsWorkspaceData.ts`, `frontend/src/components/google-ads/**`, test files under `frontend/src/routes/google-ads/__tests__/`
- Must NOT touch: DashboardLayout.tsx (do not re-hide FilterBar), Meta routes, combined routes, backend
- Output artifact: `artifacts/sprint/phase1b-google-fix.md`
  - Schema: same shape as phase1a-meta-fix.md but agent_id=C2B
- Definition of Done: Targeted vitest suite for Google Ads files passes. Build clean. No TypeScript errors.
- Tools allowed: Read + Edit. Run `cd frontend && npx vitest run` on targeted files. Run build. No full stack.
- Time-box: 35 minutes

**Agent C3B-test**

- Role: Validate Google Ads cluster against Phase 1B DoD checklist
- Inputs:
  - `artifacts/sprint/phase1b-google-fix.md`
  - `artifacts/sprint/phase1b-google-audit.json`
  - Phase 1B DoD checklist (Section 5)
- Scope: Run test suites; write missing test cases if DoD lacks coverage
- Must NOT touch: application source (test files only)
- Output artifact: `artifacts/sprint/phase1b-google-test.md`
  - Schema: same shape as phase1a-meta-test.md, agent_id=C3B
- Definition of Done: All Phase 1B DoD criteria pass. Targeted vitest GREEN. Build clean.
- Tools allowed: Read + Edit (test files only). Run vitest targeted suite. Run lint + build.
- Time-box: 20 minutes

---

### Phase 2 — Combined View Dashboard

**Gating condition:** `phase1a-meta-test.md` VERDICT=GREEN AND `phase1b-google-test.md` VERDICT=GREEN. If either is YELLOW, proceed only if no blocking bugs remain; document risk.

**Agent C1C-audit**

- Role: Deep read-only IRL audit of all combined-view routes
- Inputs:
  - `artifacts/verify/combined-verification.json` (B-PLAT-01 through B-SAVED-02; focus on deferred: B-CAMP-01, B-CREA-01, B-AUD-01, B-PLAT-03)
  - `artifacts/synthesis/synthesis-report.md` (APPLIED + DEFERRED combined items)
  - `artifacts/sprint/phase1a-meta-test.md` (confirms R7 reconciliation working)
  - `artifacts/sprint/phase1b-google-test.md` (confirms Google Ads FilterBar working)
  - `frontend/src/routes/PlatformDashboard.tsx`
  - `frontend/src/routes/CampaignDashboard.tsx`
  - `frontend/src/routes/CampaignDetail.tsx`
  - `frontend/src/routes/CreativeDashboard.tsx`
  - `frontend/src/routes/CreativeDetail.tsx`
  - `frontend/src/routes/BudgetDashboard.tsx`
  - `frontend/src/routes/AudienceDashboard.tsx`
  - `frontend/src/routes/ParishMapDetail.tsx`
  - `frontend/src/routes/SavedDashboardPage.tsx`
  - `frontend/src/routes/DashboardLayout.tsx` (scoped→unscoped transition, read-only)
  - `frontend/src/state/useDashboardStore.ts`
  - `frontend/src/lib/dashboardFilters.ts`
- Scope: Files under `frontend/src/routes/` for combined routes, `frontend/src/state/useDashboardStore*`
- Must NOT touch: Meta routes, Google Ads routes, backend
- Output artifact: `artifacts/sprint/phase1c-combined-audit.json`
  - Schema: `{ schema_version, agent_id: "C1C", timestamp, routes: [ { route, component, status, bugs_confirmed: [...], new_bugs: [...] } ], deferred_items_status: [ { bug_id, still_open: bool, evidence } ], cross_cutting: [...], summary_verdict }`
- Definition of Done: All 6 combined routes audited. Deferred bugs (B-CAMP-01, B-CREA-01, B-AUD-01, B-PLAT-03, B-CAMP-02) re-assessed — determine if still open or if prior patches closed them. R7 round-trip (Meta account → navigate to /dashboards/platforms → same account in FilterBar) verified via code trace.
- Tools allowed: Read-only. No edits. No dev server.
- Time-box: 20 minutes

**Agent C2C-fix**

- Role: Apply fixes to combined-view routes, including deferred items that are still open
- Inputs:
  - `artifacts/sprint/phase1c-combined-audit.json` (primary)
  - `artifacts/verify/combined-verification.json` (fix_patches for all deferred bugs)
  - `artifacts/synthesis/synthesis-report.md`
  - All source files listed for C1C-audit
- Scope: May edit `frontend/src/routes/PlatformDashboard.tsx`, `CampaignDashboard.tsx`, `CreativeDashboard.tsx`, `BudgetDashboard.tsx`, `AudienceDashboard.tsx`, `ParishMapDetail.tsx`, `SavedDashboardPage.tsx`, `frontend/src/state/useDashboardStore.ts` (selector surgery for B-CAMP-01/B-CREA-01 if C1C confirms open), corresponding `__tests__/` files
- Must NOT touch: DashboardLayout.tsx platform-scope effect, Meta routes, Google Ads routes, backend, FilterBar.tsx
- Output artifact: `artifacts/sprint/phase1c-combined-fix.md`
  - Schema: same shape as prior fix reports, agent_id=C2C
- Definition of Done: Targeted vitest suite for combined files passes. Build clean. No TypeScript errors.
- Tools allowed: Read + Edit. Run targeted vitest. Run build.
- Time-box: 40 minutes

**Agent C3C-test**

- Role: Validate combined-view routes against Phase 2 DoD checklist
- Inputs:
  - `artifacts/sprint/phase1c-combined-fix.md`
  - `artifacts/sprint/phase1c-combined-audit.json`
  - Phase 2 DoD checklist (Section 5)
- Scope: Run test suites; add missing test cases if DoD lacks coverage
- Must NOT touch: application source (test files only)
- Output artifact: `artifacts/sprint/phase1c-combined-test.md`
  - Schema: same shape as prior test reports, agent_id=C3C
- Definition of Done: All Phase 2 DoD criteria pass. Targeted vitest GREEN. Build clean.
- Tools allowed: Read + Edit (test files only). Run targeted vitest. Run lint + build.
- Time-box: 20 minutes

---

### Phase 3 — Final E2E

**Gating condition:** `phase1c-combined-test.md` VERDICT=GREEN.

**Agent C4-e2e**

- Role: Full suite validation + manual smoke checklist
- Inputs:
  - All three phase test reports (`phase1a-meta-test.md`, `phase1b-google-test.md`, `phase1c-combined-test.md`)
  - `artifacts/synthesis/synthesis-report.md` (pre-existing failures to track)
  - `frontend/src/routes/__tests__/DataSources.test.tsx` (fix pre-existing scrollIntoView failure)
  - `backend/tests/` (full pytest)
- Scope: May edit `frontend/src/routes/__tests__/DataSources.test.tsx` and vitest setup file to fix scrollIntoView mock. Read all source to write smoke checklist. No application logic edits.
- Must NOT touch: application source files, backend views/models/serializers
- Output artifact: `artifacts/sprint/phase3-e2e-report.md`
  - Schema: `# Phase 3 E2E Report\n## Backend pytest (full output summary)\n## Frontend vitest full suite (files/tests pass/fail counts)\n## Lint (output)\n## Build (output)\n## Pre-existing failures resolved (list)\n## Pre-existing failures still open (list + explanation)\n## Manual Smoke Checklist (see §5)\n## FINAL VERDICT: GREEN|YELLOW|RED`
- Definition of Done: Backend 727+ pass. Frontend vitest: same or better than Phase A baseline (DataSources scrollIntoView fixed; no new failures). Lint clean. Build clean. Smoke checklist written and self-evaluated against code.
- Tools allowed: Read + Edit (test/setup files only). Run full `cd backend && pytest -q`. Run `cd frontend && npm test -- --run`. Run lint + build.
- Time-box: 30 minutes

---

## 4. Chain Prompt Templates

---

### AGENT C1A — Meta Audit

```
Input artifacts (cite at top of output):
- /Users/thristannewman/ADinsights/artifacts/verify/meta-verification.json
- /Users/thristannewman/ADinsights/artifacts/synthesis/synthesis-report.md
- /Users/thristannewman/ADinsights/artifacts/plan.md

## Role
You are C1A-audit. Your job is a deep READ-ONLY audit of every /dashboards/meta/* route in the ADinsights frontend. You determine the TRUE current state of each route — what renders, what fetches, what is broken — by reading the actual source files, not by trusting prior reports.

## Scope
Files you may read: frontend/src/routes/Meta*.tsx, frontend/src/state/useMetaStore*.ts, frontend/src/routes/DashboardLayout.tsx (read-only), frontend/src/lib/dashboardFilters.ts, frontend/src/components/FilterBar.tsx, frontend/src/components/EmptyState.tsx

Do NOT read or touch: backend files, combined-view routes, Google Ads routes, any test files.

## Routes to audit (enumerate all)
/dashboards/meta/accounts, /dashboards/meta/insights, /dashboards/meta/campaigns, /dashboards/meta/status, /dashboards/meta/pages, /dashboards/meta/pages/:pageId/overview, /dashboards/meta/pages/:pageId/posts, /dashboards/meta/posts/:postId

## For each route, verify
1. Does FilterBar render? (Check DashboardLayout hideGlobalFilters predicate for this path)
2. Does account selection propagate from useMetaStore → useDashboardStore.filters.accountId? (Trace the R7 reconciliation effect in DashboardLayout — find the effect, confirm its pathname guard, confirm it fires for this route)
3. What endpoints does the page fetch? Do those fetches include correct scope params?
4. Is the empty/loading/error state handled without a blank render?
5. Are there console-error-producing patterns (undefined access, missing null guards, etc.)?

## Known bugs to re-verify (from synthesis-report.md — check each is truly APPLIED, not just claimed)
M1 (R7 reconciliation), M2 (account row click), M3 (empty state loading guard), M5, M7, M12, M16

## Output
Write /Users/thristannewman/ADinsights/artifacts/sprint/phase1a-meta-audit.json with this exact schema:
{
  "schema_version": "1.0",
  "agent_id": "C1A",
  "timestamp": "<ISO8601>",
  "routes": [
    {
      "route": "/dashboards/meta/...",
      "file": "<absolute path>",
      "filterbar_visible": true|false,
      "account_propagation": "confirmed"|"broken"|"not_applicable",
      "endpoint_scope_correct": true|false|"not_applicable",
      "empty_state_handled": true|false,
      "status": "green"|"yellow"|"red",
      "bugs_confirmed": [{ "id": "M1", "severity": "high", "description": "...", "file": "...", "line": 0, "evidence": "..." }],
      "new_bugs": [{ "id": "C1A-NEW-01", "severity": "...", "description": "...", "file": "...", "line": 0 }],
      "fix_required": true|false
    }
  ],
  "cross_cutting": [{ "concern": "...", "files_affected": [...], "severity": "..." }],
  "summary_verdict": "green"|"yellow"|"red"
}

## Non-goals
Do NOT fix anything. Do NOT run the dev server. Do NOT write test files. Do NOT read backend files.

## Final line of your response
STATUS: <GREEN|YELLOW|RED> — <one sentence summary>
```

---

### AGENT C1B — Google Ads Audit

```
Input artifacts (cite at top of output):
- /Users/thristannewman/ADinsights/artifacts/verify/google-verification.json
- /Users/thristannewman/ADinsights/artifacts/fixes/B1-fix-report.md
- /Users/thristannewman/ADinsights/artifacts/triage/B0-triage.md
- /Users/thristannewman/ADinsights/artifacts/synthesis/synthesis-report.md

## Role
You are C1B-audit. Your job is a deep READ-ONLY audit of the /dashboards/google-ads workspace (GOOGLE_ADS_WORKSPACE_UNIFIED=true, which is the default). You determine the TRUE current state — what renders, what fetches, what is broken — by reading actual source files.

## Scope
Files you may read: frontend/src/routes/google-ads/*.tsx, frontend/src/hooks/useGoogleAdsWorkspaceData.ts, frontend/src/components/google-ads/workspace/WorkspaceHeader.tsx, frontend/src/components/google-ads/workspace/types.ts, frontend/src/components/google-ads/GoogleAdsDataTablePage.tsx, frontend/src/routes/DashboardLayout.tsx (hideGlobalFilters only — read line 196-210 range), frontend/src/router.tsx (lines 115-118 flag resolution only)

Do NOT read or touch: backend files, Meta routes, combined-view routes.

## Workspace tabs to audit
overview (GoogleAdsExecutivePage or workspace summary), campaigns, search, pmax, assets, conversions, pacing, changes, recommendations, reports

## For each tab / component, verify
1. After B1 hot-fix: does FilterBar render on /dashboards/google-ads? (Check hideGlobalFilters predicate)
2. Does the global FilterBar account selection (useDashboardStore.filters.accountId) reach the workspace as customer_id? Trace the exact code path from DashboardLayout FilterBar selection → useDashboardStore → GoogleAdsWorkspacePage → useGoogleAdsWorkspaceData → fetch params.
3. Does every tab fetch include platforms=google_ads? (Check buildCommonParams in useGoogleAdsWorkspaceData.ts)
4. Is there an EmptyState rendered when customer_id is empty?
5. Are there any tab-specific fetches that bypass buildCommonParams and omit customer_id or platforms?
6. SDK migration risk: identify any views/components referencing GoogleAdsSdk* models or tables — document if fallback exists.

## Known items to re-verify
B1 (platforms param — APPLIED in synthesis), B2 (mount seed — removed in B1 hotfix), B3 (back link — APPLIED), B6/B7/B8 (scope params in exec/table/budget/detail — APPLIED)
B4 (colon encoding — DEFERRED as theoretical), B5 (Playwright E2E — DEFERRED)

## Output
Write /Users/thristannewman/ADinsights/artifacts/sprint/phase1b-google-audit.json with this exact schema:
{
  "schema_version": "1.0",
  "agent_id": "C1B",
  "timestamp": "<ISO8601>",
  "filterbar_on_workspace_route": true|false,
  "account_propagation_path": "<description of code path>",
  "workspace_tabs": [
    {
      "tab": "overview",
      "component": "<file>",
      "platforms_param_included": true|false,
      "customer_id_included": true|false,
      "status": "green"|"yellow"|"red",
      "bugs_confirmed": [...],
      "new_bugs": [...]
    }
  ],
  "sdk_migration_risk": { "severity": "low"|"medium"|"high", "description": "...", "affected_files": [...], "fallback_exists": true|false },
  "cross_cutting": [...],
  "summary_verdict": "green"|"yellow"|"red"
}

## Non-goals
Do NOT fix anything. Do NOT run the dev server. Do NOT write test files. Do NOT read backend files.

## Final line of your response
STATUS: <GREEN|YELLOW|RED> — <one sentence summary>
```

---

### AGENT C1C — Combined Audit

```
Input artifacts (cite at top of output):
- /Users/thristannewman/ADinsights/artifacts/verify/combined-verification.json
- /Users/thristannewman/ADinsights/artifacts/synthesis/synthesis-report.md
- /Users/thristannewman/ADinsights/artifacts/sprint/phase1a-meta-test.md
- /Users/thristannewman/ADinsights/artifacts/sprint/phase1b-google-test.md

## Role
You are C1C-audit. Your job is a deep READ-ONLY audit of all combined-view routes in ADinsights: /dashboards/platforms, campaigns, campaigns/:id, creatives, creatives/:id, budget, audience, map (ParishMapDetail). You determine the TRUE current state by reading source files.

## Scope
Files you may read: frontend/src/routes/PlatformDashboard.tsx, CampaignDashboard.tsx, CampaignDetail.tsx, CreativeDashboard.tsx, CreativeDetail.tsx, BudgetDashboard.tsx, AudienceDashboard.tsx, ParishMapDetail.tsx, SavedDashboardPage.tsx, frontend/src/state/useDashboardStore.ts, frontend/src/lib/dashboardFilters.ts, frontend/src/routes/DashboardLayout.tsx (platform-scope effect only — read the useEffect that sets filters.platforms)

Do NOT read or touch: Meta routes, Google Ads routes, backend files.

## For each route, verify
1. When navigating FROM /dashboards/meta/* TO this route: does filters.platforms reset to [] (all)? Trace the DashboardLayout platform-scope effect. Confirm the scoped→unscoped transition is handled.
2. Does the route fetch /api/metrics/combined/ with both platforms? Trace filters → buildFilterQueryParams → fetch.
3. Are deferred bugs still open? For each: B-CAMP-01, B-CREA-01, B-AUD-01, B-PLAT-03, B-CAMP-02 — read the relevant selector/component code and determine if the bug is still present in source.
4. Is SavedDashboardPage correctly restoring platforms field? (B-SAVED-01/02 — confirmed APPLIED, but verify in source)
5. Empty state: does each route show an EmptyState (not blank chart) when data returns 0-length arrays?

## Output
Write /Users/thristannewman/ADinsights/artifacts/sprint/phase1c-combined-audit.json with this exact schema:
{
  "schema_version": "1.0",
  "agent_id": "C1C",
  "timestamp": "<ISO8601>",
  "r7_roundtrip_verified": true|false,
  "scoped_to_unscoped_transition_verified": true|false,
  "routes": [
    {
      "route": "/dashboards/...",
      "component": "<file>",
      "status": "green"|"yellow"|"red",
      "scope_reset_on_entry": true|false,
      "endpoint_scope_correct": true|false,
      "empty_state_handled": true|false,
      "bugs_confirmed": [...],
      "new_bugs": [...]
    }
  ],
  "deferred_items_status": [
    { "bug_id": "B-CAMP-01", "still_open": true|false, "evidence": "...", "fix_required": true|false }
  ],
  "summary_verdict": "green"|"yellow"|"red"
}

## Non-goals
Do NOT fix anything. Do NOT run the dev server. Do NOT write test files. Do NOT read backend files.

## Final line of your response
STATUS: <GREEN|YELLOW|RED> — <one sentence summary>
```

---

### AGENT C2A — Meta Fix

```
Input artifacts (cite at top of output):
- /Users/thristannewman/ADinsights/artifacts/sprint/phase1a-meta-audit.json
- /Users/thristannewman/ADinsights/artifacts/verify/meta-verification.json

## Role
You are C2A-fix. Apply fixes to the Meta dashboard cluster based on the audit. Every fix must be minimal and surgical. Do not refactor unrelated code.

## Scope
You MAY edit:
- frontend/src/routes/Meta*.tsx
- frontend/src/state/useMetaStore*.ts
- frontend/src/routes/DashboardLayout.tsx — ONLY the R7 reconciliation effect (lines around the useMetaStore import and the pathname guard). Do NOT touch the resolveRoutePlatformScope effect or the URL-sync effect.
- frontend/src/routes/__tests__/Meta*.test.tsx (add tests for each fix)

Do NOT edit: backend, combined routes, Google Ads routes, FilterBar.tsx, dashboardFilters.ts, or any file NOT explicitly listed above.

## Fix protocol
For each red/yellow item in phase1a-meta-audit.json:
1. Read the cited file + line
2. Apply the minimal fix (use fix_patches from meta-verification.json as reference; update if audit found something different)
3. Add a vitest test case for the fix in the corresponding __tests__ file
4. Run: cd frontend && npx vitest run --reporter=verbose <test-file-pattern> and confirm pass

## Output
Write /Users/thristannewman/ADinsights/artifacts/sprint/phase1a-meta-fix.md with:
# Phase 1A Meta Fix Report
## Files Modified
| File | Change summary | Lines +/- |

## Tests Added
| File | Kind | Cases |

## Test Results
<paste vitest output for targeted files>

## Build Output
<paste: cd frontend && npm run build — last 5 lines>

## Deferred (with reasons)

## Status: GREEN|YELLOW|RED

## Non-goals
Do NOT add new API endpoints. Do NOT introduce new state stores. Do NOT change platform-scope logic in DashboardLayout beyond the R7 reconciliation effect.

## Final line of your response
STATUS: <GREEN|YELLOW|RED> — <one sentence summary>
```

---

### AGENT C2B — Google Ads Fix

```
Input artifacts (cite at top of output):
- /Users/thristannewman/ADinsights/artifacts/sprint/phase1b-google-audit.json
- /Users/thristannewman/ADinsights/artifacts/verify/google-verification.json
- /Users/thristannewman/ADinsights/artifacts/triage/B0-triage.md

## Role
You are C2B-fix. Apply fixes to the Google Ads workspace cluster. Every fix is minimal and surgical.

## Scope
You MAY edit:
- frontend/src/routes/google-ads/*.tsx
- frontend/src/hooks/useGoogleAdsWorkspaceData.ts
- frontend/src/components/google-ads/workspace/WorkspaceHeader.tsx
- frontend/src/components/google-ads/workspace/types.ts
- frontend/src/components/google-ads/GoogleAdsDataTablePage.tsx
- frontend/src/routes/google-ads/__tests__/*.test.tsx (add tests)

Do NOT edit: DashboardLayout.tsx (do NOT re-hide FilterBar on google-ads route — this was the B1 hot-fix, preserve it), Meta routes, combined routes, backend.

## Fix protocol
For each red/yellow item in phase1b-google-audit.json:
1. Read the cited file + line
2. Apply fix (use fix_patches from google-verification.json as reference)
3. Add vitest test for the fix
4. Run: cd frontend && npx vitest run --reporter=verbose <test-file-pattern>

Pay special attention to:
- SDK migration risk: if audit flagged sdk_migration_risk.severity >= medium, add a graceful fallback or empty-state guard so the page shows a clear "data syncing" message rather than silent zeros.
- Tab-specific fetches that bypass buildCommonParams: trace each and ensure all reach the correct endpoint with customer_id.

## Output
Write /Users/thristannewman/ADinsights/artifacts/sprint/phase1b-google-fix.md with same schema as phase1a-meta-fix.md but agent_id=C2B.

## Non-goals
Do NOT add new backend endpoints. Do NOT change GOOGLE_ADS_WORKSPACE_UNIFIED default. Do NOT touch DashboardLayout hideGlobalFilters.

## Final line of your response
STATUS: <GREEN|YELLOW|RED> — <one sentence summary>
```

---

### AGENT C2C — Combined Fix

```
Input artifacts (cite at top of output):
- /Users/thristannewman/ADinsights/artifacts/sprint/phase1c-combined-audit.json
- /Users/thristannewman/ADinsights/artifacts/verify/combined-verification.json
- /Users/thristannewman/ADinsights/artifacts/synthesis/synthesis-report.md

## Role
You are C2C-fix. Apply fixes to combined-view dashboard routes. This includes closing deferred items confirmed still-open by C1C-audit.

## Scope
You MAY edit:
- frontend/src/routes/PlatformDashboard.tsx
- frontend/src/routes/CampaignDashboard.tsx
- frontend/src/routes/CampaignDetail.tsx
- frontend/src/routes/CreativeDashboard.tsx
- frontend/src/routes/CreativeDetail.tsx
- frontend/src/routes/BudgetDashboard.tsx
- frontend/src/routes/AudienceDashboard.tsx
- frontend/src/routes/ParishMapDetail.tsx
- frontend/src/routes/SavedDashboardPage.tsx
- frontend/src/state/useDashboardStore.ts (selector surgery for B-CAMP-01/B-CREA-01 if audit confirmed still-open — read the fix_patches in combined-verification.json carefully before touching store selectors)
- Corresponding __tests__/ files

Do NOT edit: DashboardLayout.tsx, FilterBar.tsx, dashboardFilters.ts, Meta routes, Google Ads routes, backend.

## Fix protocol
For each red/yellow item in phase1c-combined-audit.json AND each deferred item where still_open=true:
1. Read cited file + line
2. Apply minimal fix
3. Add vitest test
4. Run targeted vitest

Priority order: B-CAMP-01 (row-level platform filter) > B-CREA-01 (same for creatives) > B-AUD-01 (empty state) > B-PLAT-03 (cosmetic label) > B-CAMP-02 (duplicate empty-state branches)

## Output
Write /Users/thristannewman/ADinsights/artifacts/sprint/phase1c-combined-fix.md with same schema as prior fix reports, agent_id=C2C.

## Non-goals
Do NOT add new endpoints. Do NOT re-architect useDashboardStore beyond selector-level guards. Do NOT change DashboardLayout platform-scope effect.

## Final line of your response
STATUS: <GREEN|YELLOW|RED> — <one sentence summary>
```

---

### AGENT C3A — Meta Test

```
Input artifacts (cite at top of output):
- /Users/thristannewman/ADinsights/artifacts/sprint/phase1a-meta-fix.md
- /Users/thristannewman/ADinsights/artifacts/sprint/phase1a-meta-audit.json

## Role
You are C3A-test. Validate the Meta dashboard cluster against the Phase 1A Definition of Done checklist below. Your job: run test suites, trace code to verify DoD criteria, and produce a definitive PASS/FAIL per criterion.

## Phase 1A DoD Checklist (validate each item)
1. FilterBar is visible on /dashboards/meta/accounts (hideGlobalFilters returns false for this path)
2. Clicking an account row on /dashboards/meta/accounts sets useMetaStore.filters.accountId to the row's external_id
3. Clicking a row in recovery-fallback mode does NOT call setFilters (guard present)
4. /dashboards/meta/accounts: empty-state panel NOT shown while status=loading; IS shown after status=loaded with 0 rows
5. Navigating from /dashboards/meta/accounts to /dashboards/platforms: the R7 reconciliation effect bridges useMetaStore.filters.accountId → useDashboardStore.filters.accountId (read DashboardLayout code trace)
6. /dashboards/meta/insights: date range change triggers re-fetch; loading guard on empty state present
7. /dashboards/meta/campaigns: 0-campaign empty state shows EmptyState component with reasonCode (not blank chart)
8. /dashboards/meta/status: NO call to /api/metrics/combined/ is triggered (status page is info-only)
9. /dashboards/meta/pages: resolveRoutePlatformScope returns ['meta_ads'] for this path (verify in dashboardFilters.ts)
10. /dashboards/meta/pages/:pageId/overview: MetaPageOverviewPage period change does NOT call loadTimeseries directly (M12 fix)
11. /dashboards/meta/posts/:postId: MetaPostDetailPage passes { metric, period } overrides to loadPostTimeseries (M16 fix)
12. No TypeScript compile errors in Meta route files
13. Frontend build succeeds

## Output
Write /Users/thristannewman/ADinsights/artifacts/sprint/phase1a-meta-test.md:
# Phase 1A Meta Test Report
## DoD Checklist Results
| # | Criterion | PASS/FAIL | Evidence (file:line or test name) |

## Test Suite Summary
<cd frontend && npx vitest run --reporter=verbose <meta files pattern> — paste output>

## Build
<npm run build last 5 lines>

## Console Error Check
<list any patterns that would produce console errors: undefined access, missing keys, etc.>

## Unresolved Issues
<list anything that blocked a PASS>

## VERDICT: GREEN|YELLOW|RED
(GREEN = all 13 criteria PASS; YELLOW = 1-2 low criteria fail; RED = any medium/high criterion fails)

## Non-goals
Do NOT edit application source. Only edit test files if strictly required to add missing coverage for a DoD criterion.

## Final line of your response
VERDICT: <GREEN|YELLOW|RED> — <one sentence>
```

---

### AGENT C3B — Google Ads Test

```
Input artifacts (cite at top of output):
- /Users/thristannewman/ADinsights/artifacts/sprint/phase1b-google-fix.md
- /Users/thristannewman/ADinsights/artifacts/sprint/phase1b-google-audit.json

## Role
You are C3B-test. Validate the Google Ads workspace cluster against the Phase 1B Definition of Done checklist.

## Phase 1B DoD Checklist (validate each item)
1. Global FilterBar IS visible on /dashboards/google-ads (hideGlobalFilters = false for this path — B1 hot-fix preserved)
2. Global FilterBar account selection (useDashboardStore.filters.accountId) flows to workspace customer_id on mount — trace the exact code path in GoogleAdsWorkspacePage
3. EmptyState with reasonCode="no_customer_selected" renders when useDashboardStore.filters.accountId is empty and useDashboardStore.filters.clientId is empty
4. Every workspace tab fetch (overview, campaigns, search, pmax, assets, conversions, pacing, changes, recommendations, reports) includes platforms=google_ads in request params — verify buildCommonParams in useGoogleAdsWorkspaceData.ts
5. Every workspace tab fetch includes customer_id from useDashboardStore (not from a stale URL param or empty default)
6. /dashboards/google-ads/campaigns/:id (campaign detail drawer): back navigation preserves account scope
7. SDK migration risk: if SDK tables are empty, workspace shows a "data syncing" message or graceful zero-state — NOT a silent blank page
8. GOOGLE_ADS_WORKSPACE_UNIFIED=true (default, per router.tsx:115-118) — legacy redirect routes all point to workspace — verify no infinite redirect loop
9. No TypeScript compile errors in Google Ads route files
10. Frontend build succeeds

## Output
Write /Users/thristannewman/ADinsights/artifacts/sprint/phase1b-google-test.md (same schema as phase1a-meta-test.md but with Phase 1B DoD).

## Non-goals
Do NOT edit application source. Only edit test files if strictly required.

## Final line of your response
VERDICT: <GREEN|YELLOW|RED> — <one sentence>
```

---

### AGENT C3C — Combined Test

```
Input artifacts (cite at top of output):
- /Users/thristannewman/ADinsights/artifacts/sprint/phase1c-combined-fix.md
- /Users/thristannewman/ADinsights/artifacts/sprint/phase1c-combined-audit.json
- /Users/thristannewman/ADinsights/artifacts/sprint/phase1a-meta-test.md
- /Users/thristannewman/ADinsights/artifacts/sprint/phase1b-google-test.md

## Role
You are C3C-test. Validate all combined-view routes against the Phase 2 Definition of Done checklist.

## Phase 2 DoD Checklist (validate each item)
1. /dashboards/platforms: navigating FROM /dashboards/meta/* resets filters.platforms to [] (all) before PlatformDashboard renders — trace the DashboardLayout scoped→unscoped transition effect
2. /dashboards/platforms: when byPlatform.length === 0 after load, EmptyState renders (not blank chart) — B-PLAT-02 fix verified
3. /dashboards/platforms: KPI tiles show correct labels for both meta_ads and google_ads data (B-PLAT-03 cosmetic fix if applied, or documented as still-open)
4. /dashboards/campaigns: campaign rows from wrong platform do NOT appear when platforms filter is set — B-CAMP-01 row-level selector fix verified (or documented as still-open with severity assessment)
5. /dashboards/creatives: same as above for creative rows — B-CREA-01
6. /dashboards/audience: EmptyState renders on loaded+empty data — B-AUD-01 fix verified
7. /dashboards/budget: BudgetDashboard fetches with correct account_id and platform scope
8. /dashboards/map (ParishMapDetail): geo overlay respects platform toggle — verify platform param in parish endpoint call
9. /dashboards/saved/:id: loading a saved dashboard with platforms=[meta_ads] correctly restores filters.platforms — B-SAVED-01/02 verified
10. R7 round-trip: select account on /dashboards/meta/accounts → navigate to /dashboards/platforms → global FilterBar account selector shows the SAME account (code trace)
11. No TypeScript compile errors in combined route files
12. Frontend build succeeds

## Output
Write /Users/thristannewman/ADinsights/artifacts/sprint/phase1c-combined-test.md (same schema as prior test reports).

## Non-goals
Do NOT edit application source. Only edit test files if strictly required.

## Final line of your response
VERDICT: <GREEN|YELLOW|RED> — <one sentence>
```

---

### AGENT C4 — Final E2E

```
Input artifacts (cite at top of output):
- /Users/thristannewman/ADinsights/artifacts/sprint/phase1a-meta-test.md
- /Users/thristannewman/ADinsights/artifacts/sprint/phase1b-google-test.md
- /Users/thristannewman/ADinsights/artifacts/sprint/phase1c-combined-test.md
- /Users/thristannewman/ADinsights/artifacts/synthesis/synthesis-report.md

## Role
You are C4-e2e. Run the full test suite across backend and frontend. Fix pre-existing failures where you have permission. Produce a manual smoke checklist for the user.

## Scope
You MAY edit:
- frontend/src/routes/__tests__/DataSources.test.tsx — add `window.HTMLElement.prototype.scrollIntoView = vi.fn()` in a beforeEach or in the vitest setup file (frontend/src/test/setup.ts or vitest.config.ts setupFiles) to fix the pre-existing 10 scrollIntoView failures
- frontend/vitest.config.ts OR frontend/src/test/setup.ts — add the scrollIntoView mock globally

Do NOT edit: any application source file, any backend file, any test file except the scrollIntoView fix above.

## Commands to run (in order)
1. cd /Users/thristannewman/ADinsights/backend && ruff check .
2. cd /Users/thristannewman/ADinsights/backend && pytest -q
3. cd /Users/thristannewman/ADinsights/frontend && npm run lint
4. cd /Users/thristannewman/ADinsights/frontend && npm run build
5. cd /Users/thristannewman/ADinsights/frontend && npm test -- --run

## Manual Smoke Checklist
Write a step-by-step checklist the user can execute in a browser (dev stack running). Cover:
- Fresh session (no stored JWT): confirm redirect to /login
- Login and land on /dashboards
- Navigate to /dashboards/meta/accounts: confirm FilterBar visible, account table loads
- Click account row: confirm row is clickable and account is selected
- Navigate to /dashboards/platforms: confirm FilterBar shows same account, platforms data loads
- Navigate to /dashboards/google-ads: confirm FilterBar visible, empty state if no account selected
- Select account in FilterBar: confirm workspace loads tabs
- Navigate through workspace tabs (overview, campaigns, pacing): confirm each loads data
- Navigate to /dashboards/campaigns: confirm campaign rows scoped to selected account + both platforms
- Navigate to /dashboards/audience: confirm empty state on zero data (not blank chart)
- Navigate to /dashboards/map: confirm parish map loads
- Navigate to /dashboards/meta/status: confirm NO loading spinner for combined metrics (status page only)

## Output
Write /Users/thristannewman/ADinsights/artifacts/sprint/phase3-e2e-report.md with:
# Phase 3 E2E Report
## Backend ruff (output)
## Backend pytest (summary: N passed, N failed)
## Frontend lint (output)
## Frontend build (last 5 lines)
## Frontend vitest full suite (files: N passed N failed; tests: N passed N failed)
## Pre-existing failures resolved
## Pre-existing failures still open (with explanation)
## Manual Smoke Checklist
<numbered steps with expected vs. actual where you can evaluate from code>
## FINAL VERDICT: GREEN|YELLOW|RED

## Non-goals
Do NOT run Playwright E2E (needs live server). Do NOT fix application bugs. Do NOT change backend code.

## Final line of your response
FINAL VERDICT: <GREEN|YELLOW|RED> — <one sentence>
```

---

## 5. Definition of Done Per Phase

### Phase 1A — Meta DoD

1. FilterBar visible on /dashboards/meta/accounts (hideGlobalFilters=false confirmed)
2. Clicking account row sets useMetaStore.filters.accountId to external_id
3. Recovery-fallback row click guard present (no setFilters for orphaned IDs)
4. Empty-state: NOT shown while status=loading; IS shown after loaded + 0 rows (accounts, insights, campaigns)
5. R7 reconciliation: useMetaStore.filters.accountId → useDashboardStore.filters.accountId bridge confirmed via DashboardLayout code trace
6. /dashboards/meta/insights: date range change re-triggers fetch
7. /dashboards/meta/campaigns: 0-campaign empty state shows EmptyState with reasonCode
8. /dashboards/meta/status: no /api/metrics/combined/ fetch triggered
9. /dashboards/meta/pages: resolveRoutePlatformScope('dashboards/meta/pages') returns ['meta_ads']
10. MetaPageOverviewPage period change does NOT call loadTimeseries directly (M12)
11. MetaPostDetailPage passes { metric, period } overrides (M16)
12. TypeScript: no compile errors in Meta route files
13. Build: `npm run build` exits 0

**Threshold:** GREEN = all 13 pass. YELLOW = criteria 3, 6, 7, 10, 11 fail (low impact only). RED = criteria 1, 2, 4, 5, 8, 9, 12, 13 fail.

### Phase 1B — Google Ads DoD

1. Global FilterBar visible on /dashboards/google-ads
2. account_id from useDashboardStore flows to workspace customer_id on mount
3. EmptyState (reasonCode=no_customer_selected) when both accountId and clientId empty
4. All 10 workspace tab fetches include platforms=google_ads
5. All 10 workspace tab fetches include correct customer_id
6. Campaign detail back navigation preserves account scope
7. SDK zero-state: graceful message, not silent blank page
8. No infinite redirect loop for unified mode legacy routes
9. TypeScript: no compile errors in Google Ads route files
10. Build: `npm run build` exits 0

**Threshold:** GREEN = all 10 pass. YELLOW = criteria 6, 7 fail (low impact). RED = criteria 1–5, 8, 9, 10 fail.

### Phase 2 — Combined DoD

1. scoped→unscoped transition: navigating from /meta/\* to /platforms resets filters.platforms to []
2. /dashboards/platforms: EmptyState on loaded + byPlatform.length===0
3. /dashboards/platforms: KPI labels correct for both platforms (or documented as still-open low)
4. /dashboards/campaigns: row-level platform filter applied (B-CAMP-01 closed or documented)
5. /dashboards/creatives: row-level platform filter applied (B-CREA-01 closed or documented)
6. /dashboards/audience: EmptyState on loaded+empty (B-AUD-01 closed)
7. /dashboards/budget: fetches with correct account_id + platform scope
8. /dashboards/map: parish endpoint includes platform scope param
9. /dashboards/saved/:id: platforms field restored from saved state
10. R7 round-trip: Meta account selection preserved across navigation to combined view
11. TypeScript: no compile errors in combined route files
12. Build: `npm run build` exits 0

**Threshold:** GREEN = all 12 pass. YELLOW = criteria 3, 4, 5 fail if documented as still-open medium. RED = criteria 1, 2, 6–12 fail.

### Phase 3 — E2E DoD

1. Backend ruff: 0 NEW errors (pre-existing analytics/fx.py F841 documented but not blocking)
2. Backend pytest: 727+ tests pass, 0 failures
3. Frontend lint: clean exit
4. Frontend build: clean exit
5. Frontend vitest full suite: all pre-existing DataSources scrollIntoView failures fixed (10 tests now passing); no new failures introduced by sprint work
6. Manual smoke checklist: all 12 steps have expected behavior identified from code
7. Any YELLOW items from Phases 1A, 1B, 2 are catalogued in the report with severity and owner

**Threshold:** GREEN = criteria 1–6 pass. YELLOW = criterion 5 still has scrollIntoView failures if vitest setup not patchable; criterion 1 has pre-existing F841. RED = backend pytest regressions or build failure.

---

## 6. Risk Register

| #   | Risk                                                                                                                                                   | Probability | Impact | Mitigation                                                                                                                  | Escalation trigger                                                |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------- | ------ | --------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| RR1 | R7 reconciliation effect fires AFTER first combined-dashboard fetch, so initial load is un-scoped                                                      | Medium      | High   | C1C-audit traces exact effect ordering in DashboardLayout; C2C-fix adds a one-tick flush guard if needed                    | Audit finds effect is not atomic with route change                |
| RR2 | SDK migration tables empty in dev — Google Ads workspace always shows zeros regardless of fix                                                          | Medium      | Medium | C1B-audit documents SDK risk; C2B-fix adds graceful zero-state; C4 smoke checklist notes as "requires live Google Ads sync" | C3B confirms blank page with no message despite fix attempt       |
| RR3 | B-CAMP-01 / B-CREA-01 useDashboardStore selector surgery breaks other consumers of the selector                                                        | Medium      | High   | C2C reads all callers of the selector before editing; adds targeted tests for each caller                                   | Tests fail outside the targeted suite after selector change       |
| RR4 | DashboardLayout.tsx has been edited by B1, synthesis, and now sprint — merge conflicts or double-effect                                                | Medium      | High   | C2A and C2C read current file state; do NOT re-apply effects already present; diff against git before editing               | Build or vitest reports duplicate effect error                    |
| RR5 | Pre-existing DataSources scrollIntoView failures not fixable via setup mock (e.g. the component calls scrollIntoView in a way that mock doesn't cover) | Low         | Low    | C4 tries setup mock first; if that fails, documents as pre-existing and records test count delta                            | Fixing the mock introduces new failures                           |
| RR6 | Google Ads GOOGLE_ADS_WORKSPACE_UNIFIED=false path is used in some env — audit only covers true                                                        | Low         | Medium | C1B explicitly flags flag mode; smoke checklist asks user to confirm env var                                                | User reports workspace not loading at all                         |
| RR7 | demo mode suppresses clientOptions=[] — combined dashboards look broken in demo even after fix                                                         | Medium      | Low    | B0-triage documents this as intentional; smoke checklist notes demo limitation                                              | User reports no account picker in demo mode — document, not a bug |
| RR8 | Phase 2 gating: one of Phase 1A/1B is YELLOW — combined audit may catch cross-contamination from unfixed item                                          | Low         | Medium | Proceed with explicit YELLOW documentation; C1C notes dependency on incomplete phases                                       | C1C audit finds that a Phase 1B bug directly breaks combined view |

---

## 7. Execution Timeline

| Agent     | Phase | Depends on      | Estimated wall-clock | Can run in parallel with |
| --------- | ----- | --------------- | -------------------- | ------------------------ |
| C1A-audit | 1A    | nothing         | 20 min               | C1B-audit                |
| C1B-audit | 1B    | nothing         | 20 min               | C1A-audit                |
| C2A-fix   | 1A    | C1A done        | 35 min               | C2B-fix                  |
| C2B-fix   | 1B    | C1B done        | 35 min               | C2A-fix                  |
| C3A-test  | 1A    | C2A done        | 20 min               | C3B-test                 |
| C3B-test  | 1B    | C2B done        | 20 min               | C3A-test                 |
| C1C-audit | 2     | C3A + C3B GREEN | 20 min               | —                        |
| C2C-fix   | 2     | C1C done        | 40 min               | —                        |
| C3C-test  | 2     | C2C done        | 20 min               | —                        |
| C4-e2e    | 3     | C3C GREEN       | 30 min               | —                        |

**Critical path (sequential):** C1A → C2A → C3A → C1C → C2C → C3C → C4 = 185 min (~3h 5min)
**With parallelism (1A ∥ 1B):** Max(C1A→C2A→C3A, C1B→C2B→C3B) + Phase 2 + Phase 3 = 75 + 80 + 30 = **~3h 5min total wall-clock**

If Phase 1A and 1B run in true parallel: **~2h 25min**.

---

## 8. Open Questions

The following need a decision before spawning agents:

1. **Demo mode account picker** — B0-triage confirmed `clientOptions=[]` in demo mode is intentional. Should C2B or C2C add any UI affordance (e.g. a banner "Account picker only available in live mode") or leave silent? **User decision needed.**

2. **B-CAMP-01 / B-CREA-01 selector surgery scope** — These are row-level platform filters in useDashboardStore selectors. The synthesis agent deferred them as "store surgery." Should C2C attempt the fix if C1C confirms open, or treat them as Phase 3 deferred? **Recommended: attempt if C1C confirms open and no other selector callers are at risk; else defer.**

3. **GOOGLE_ADS_WORKSPACE_UNIFIED flag in user's local .env** — B0-triage Q3 noted the flag defaults to `true` in router.tsx but `.env` value unknown. Should C1B-audit check `.env.local` / `.env` for this value, or assume default? **Recommended: C1B-audit checks `.env` and `.env.local` and documents the actual runtime value.**

4. **Pre-existing ruff F841 in analytics/fx.py** — Do you want C4 to fix this one-liner (remove unused `earliest` variable) as part of the sprint, or leave it to the SDK migration workstream? **Low risk to fix now — user decision.**

5. **Playwright E2E (B5)** — The synthesis agent deferred E2E Playwright tests. C4 is scoped to vitest + manual smoke checklist only. Do you want a follow-on Playwright sprint after C4 GREEN, or is vitest + manual sufficient? **User decision — no action needed now.**

6. **Phase 2 gating strictness** — If C3A is GREEN but C3B is YELLOW (e.g. SDK zero-state not fully fixable), should C1C proceed? **Recommended: yes, proceed with explicit dependency note in C1C output.**
