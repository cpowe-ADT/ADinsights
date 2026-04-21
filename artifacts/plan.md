# ADinsights Per-Page Scope Verification + Dashboard Visualization Program

**Source of truth for all 7 program agents (A0–A6). Every agent must cite this file's path in its first line of context.**

## 1. Goal

- Every dashboard page (Meta, Google Ads, combined/Platforms, Map, Web, Uploads, Saved) correctly honors route-scoped platform filtering AND a user-chosen account, with no cross-platform bleed and no filter/URL/store desync.
- Every known/suspected bug is documented per-page, then fixed by scoped sub-agents whose outputs feed a final synthesizer that merges patches and re-runs full test suites.
- A data-viz sprint plan is produced that upgrades each page to rich, purposeful charts (line/bar/pie/bubble/table/map/KPI) bound to filtered and unfiltered `account_id` state, handed off as ready-to-run coder-agent prompts.

## 2. Pre-flight risk audit (A0 input)

Owner: A0 Audit agent. Read-only. Output: `artifacts/audit/audit-report.json`.

| # | Risk | Failure mode | Detection | Mitigation |
|---|---|---|---|---|
| R1 | Cross-platform data leakage | Meta-only page renders Google rows because a store was hydrated earlier with both platforms and cache reused on route change | Network tab: every `/dashboards/meta/*` request sends `platforms=meta_ads` only; snapshot tests on `combined_metrics_service` request shape | Assert in `resolveRoutePlatformScope` integration test; add selector guard that drops stale rows where `platform !== scope` |
| R2 | State-sync races (filters ↔ URL ↔ stores) | User toggles account on Meta page, navigates to Google Ads; `useDashboardStore.filters` still holds old `account_id` | Playwright rapid route swap; assert store snapshot matches route scope before first fetch fires | Single effect in `DashboardLayout` is sole writer to `filters.platforms`; per-page stores subscribe, never write |
| R3 | Adapter divergence | `warehouse` respects `client_scoped_*_ids`; `meta_direct` / `demo` / `fake` / `upload` may ignore and return unscoped rows | Parameterize `test_combined_platforms_only.py` over adapter modes; compare row sets | If any adapter drops scope keys, service rejects with 400 instead of widening silently |
| R4 | Auth/tenant scoping | `_collect_tenant_platform_accounts` returns wrong tenant set for impersonation/staff users | Test that impersonates staff user; assert `X-Adinsights-Resolved-Via` ties to active tenant | Centralize tenant resolution; do not derive from `request.user.tenant` in multiple paths |
| R5 | Empty-state handling | Tenant with zero Meta accounts: backend returns `[]`, frontend shows silent blank chart | Cypress fixture with no accounts; assert empty-state component, not infinite spinner | Standard `EmptyState` with reason codes (`no_accounts`, `no_data_for_range`, `adapter_error`) |
| R6 | Test coverage gaps | Route-scope logic has backend tests but no frontend unit test for `resolveRoutePlatformScope` across all prefixes; `useMetaStore` not covered against route changes | Vitest coverage diff; list routes from `router.tsx` untouched by any test | Table-driven test mapping every dashboard route to expected scope |
| R7 | Account-selector UX drift | Meta pages use `useMetaStore`, combined pages use `useDashboardStore`. Picker may write to only one, so Platforms page shows different selected account than Meta pages | Manual: pick account on Meta, navigate to `/dashboards/platforms`; confirm selector state | Define store ownership per page (see §3) and add reconciliation effect |
| R8 | Header contract regression | Downstream consumers parse `X-Adinsights-Resolved-Via`; new `platforms:<enabled>` may break consumers expecting only `client:<id>` | Grep frontend for header consumers; add contract test | Version the header or expose parsed values in dedicated response field |

## 3. Per-page verification matrix

Routes prefixed with `/dashboards/` unless noted. Agents must enumerate from `frontend/src/router.tsx` — treat this matrix as a seed, not a closed list.

### Meta cluster (expected scope: `platforms=[meta_ads]`)

| Route | Store | Endpoint(s) | Account UX | Expected scope | Suspected bugs | Verification |
|---|---|---|---|---|---|---|
| `meta/accounts` | `useMetaStore` | Meta accounts list + `/api/metrics/combined/` | Row click sets active Meta account | Meta-only | Selector may not propagate to `useDashboardStore`; table may show Google KPIs | Click account → assert request has `platforms=meta_ads` + `account_id=<selected>` |
| `meta/insights` | `useMetaStore` | `/api/metrics/combined/` | Inherits selected Meta account | Meta-only | Ranges may default to combined | Assert scope, toggle range, toggle account |
| `meta/campaigns` | `useMetaStore` | `/api/metrics/combined/` + campaigns endpoint | Account picker in header | Meta-only | Empty state unhandled when 0 campaigns | 0-account tenant fixture |
| `meta/status` | `useMetaStore` | Meta connection health | N/A | N/A (no metrics) | Should not fetch combined | Assert no `/combined/` call |
| `meta/pages` + children | `useMetaStore` | Meta Pages endpoints | Page selector | Meta-only | `resolveRoutePlatformScope` prefix rule may miss | Check `meta/pages` maps to `meta_ads` |
| `meta/posts/:postId` | `useMetaStore` | Meta post detail | N/A | Meta-only | Same prefix concern | Same |

### Google Ads cluster (expected scope: `platforms=[google_ads]`)

Workspace flag `GOOGLE_ADS_WORKSPACE_UNIFIED` redirects legacy pages into `GoogleAdsWorkspacePage` tabs. Verify BOTH modes.

| Route | Store | Endpoint(s) | Account UX | Expected scope | Suspected bugs | Verification |
|---|---|---|---|---|---|---|
| `google-ads` (workspace) | Workspace-local + `useDashboardStore` | `/api/metrics/combined/` + Google Ads tab endpoints | Customer-ID selector in workspace header | Google-only | Tab redirects may lose query params; drawer redirect for campaign detail needs scope preservation | Tab-by-tab: overview, campaigns, search, assets, pmax, conversions, pacing, changes, recommendations, reports |
| `google-ads/campaigns/:campaignId` | Workspace | Campaign detail + combined | Inherits customer | Google-only | Drawer redirect under unified flag may drop `account_id` | Manual navigation + URL snapshot |

### Combined / cross-platform

| Route | Store | Endpoint(s) | Account UX | Expected scope | Suspected bugs | Verification |
|---|---|---|---|---|---|---|
| `platforms` | `useDashboardStore` | `/api/metrics/combined/` | Unified picker | Both | New platform-only resolver must NOT fire here when client is selected | Assert request sends `platforms=[meta_ads,google_ads]`, header = `client:<id>` |
| `campaigns` | `useDashboardStore` | combined + campaigns | Account picker | Both | Previously filtered by platform dropdown; must still work | Toggle platform, toggle account |
| `creatives` / `budget` / `audience` | `useDashboardStore` | combined + feature endpoints | Account picker | Both | Platform-only scope injection should NOT happen when client is selected | Verify header = `client:<id>` |
| `map` | `useDashboardStore` | parish/geo endpoint | Account picker | Both | Geo overlay may not respect platform toggle | Toggle platform, inspect overlay |
| `web/ga4`, `web/search-console` | Own stores | GA4/GSC endpoints | Own selectors | Non-ads (should NOT hit combined) | May inherit `filters.platforms` | Network: no `/combined/` call |
| `uploads`, `uploads/:id` | Own | Upload endpoints | N/A | N/A | Adapter=upload may bypass scoping | No ads-scope parameters leak |
| `data-sources`, `create`, `saved/:id`, library | Various | Various | N/A | N/A | `SavedDashboardPage` may persist stale filters | Load saved with `platforms=[meta_ads]` → assert effect re-syncs |

**Verifier template (same for every page):**
1. Reset stores; navigate to route.
2. Capture first N network calls; assert `platforms`, `account_id`, `client_id` params.
3. Switch account; assert re-fetch.
4. Switch date range; assert re-fetch.
5. Navigate to sibling in different cluster; assert scope flip + no stale data flash (<500ms).
6. Empty-state fixture: tenant with zero eligible accounts.
7. Header assertion: `X-Adinsights-Resolved-Via` matches expectation.

## 4. Sub-agent topology

```
                    +---------------------------+
                    |  A0. Audit agent          |
                    |  output: audit-report.json|
                    +------------+--------------+
                                 |
           +---------------------+---------------------+
           |                     |                     |
+----------v---------+ +---------v---------+ +---------v-----------+
| A1. Meta verifier  | | A2. Google Ads    | | A3. Combined/Other  |
|  /meta/**          | |     verifier      | |     verifier        |
|  useMetaStore      | |  /google-ads/**   | |  platforms,campaigns|
|                    | |  (both flag modes)| |  creatives,budget,  |
|                    | |                   | |  audience,map,web,* |
+----------+---------+ +---------+---------+ +----------+----------+
           |                     |                      |
           +---------------------+----------------------+
                                 |
                    +------------v--------------+
                    | A4. Synthesizer           |
                    | merges patches, runs CI   |
                    +------------+--------------+
                                 |
                    +------------v--------------+
                    | A5. Data-viz planner      |
                    +------------+--------------+
                                 |
                    +------------v--------------+
                    | A6. Agentic workflow spec |
                    +---------------------------+
```

**A0 Audit** — read-only, scans repo against §2 risks. Output: `artifacts/audit/audit-report.json` with `{risk_id, status: open|mitigated, evidence: [{file, line, snippet}], mitigation, owner_agent}`. Blocking.

**A1 Meta verifier** — inputs: audit-report. Scope: `frontend/src/routes/Meta*.tsx`, `frontend/src/stores/useMetaStore*`, `frontend/src/routes/DashboardLayout.tsx` (read-only ref). Output: `artifacts/verify/meta-verification.json`: `{route, bugs_found[], fix_patches[], test_deltas[]}`. Parallel with A2, A3.

**A2 Google Ads verifier** — inputs: audit-report. Scope: `frontend/src/routes/google-ads/**`, `GoogleAdsLegacyRedirects.tsx`, workspace store. Tests BOTH `GOOGLE_ADS_WORKSPACE_UNIFIED` modes. Output: `artifacts/verify/google-verification.json`. Parallel.

**A3 Combined/Other verifier** — inputs: audit-report. Scope: `PlatformDashboard.tsx`, `CampaignDashboard.tsx`, `CreativeDashboard.tsx`, `BudgetDashboard.tsx`, `AudienceDashboard.tsx`, `ParishMapDetail.tsx`, `GoogleAnalyticsDashboardPage.tsx`, `SearchConsoleDashboardPage.tsx`, `CsvUpload*.tsx`, `DashboardLibrary.tsx`, `SavedDashboardPage.tsx`, `DashboardCreate.tsx`, `useDashboardStore`. Output: `artifacts/verify/combined-verification.json`. Parallel.

**A4 Synthesizer** — inputs: all three verification JSONs. Merges patches, resolves file-overlap conflicts, runs `pytest backend/tests/` + `pnpm -C frontend test && pnpm -C frontend build`. Output: `artifacts/synthesis/synthesis-report.md` + `merged.patch`. Max 2 loops back to verifiers on failure. Sequential.

**A5 Data-viz planner** — inputs: green synthesis. Output: `artifacts/viz/sprints-plan.md` (§5 expanded page-by-page). Read-only.

**A6 Agentic workflow specialist** — inputs: sprints-plan. Output: `artifacts/viz/coder-prompts/<sprint-N>/<page>.md`. Read-only.

Parallelism: `A0 → (A1 ∥ A2 ∥ A3) → A4 → A5 → A6`.

## 5. Dashboard visualization sprint plan

**Design principles** (every page):
- KPI strip top (4–6 tiles)
- Trend chart
- Distribution/composition chart
- Drill-down table
- Optional specialized viz (map, bubble, funnel)

**Filtered vs unfiltered `account_id`:**
- Selected: single-series + faded "peer average" line
- Unselected: multi-series colored by account, legend

**Empty state**: skeleton → illustration with reason code.
**Loading**: shimmer matching final footprint (no layout shift).
**A11y**: every chart has tabular equivalent toggle, WCAG AA palette, non-color encodings on bubble/pie.

### Sprint 1 — Foundations (shared viz kit)
Deliverables: `KpiTile`, `TrendLine`, `Sparkline`, `DistributionBar`, `BubbleScatter`, `PieComposition`, `DataTable` (sortable, CSV export), `EmptyState`, `ChartSkeleton`, `AccessibleTableToggle`. Theming tokens bound to existing design system. Storybook + a11y snapshot tests.

### Sprint 2 — Meta cluster
- Accounts: KPIs (spend, impressions, reach, CTR, CPM, active accounts). TrendLine spend/day/account. PieComposition spend by objective. Table per-account, drill to Insights.
- Insights: KPIs (spend, ROAS, CTR, frequency). TrendLine CTR+CPM dual axis. Bubble campaigns (x=spend, y=ROAS, size=impressions). Table top campaigns.
- Campaigns: KPIs at roll-up. Funnel (impressions→clicks→conversions). Bar spend by campaign. Table with inline sparklines.
- Pages: KPIs (followers, reach, engagement). TrendLine follower growth. Pie post type mix.
- Post detail: KPIs (reactions, shares, reach). Sparklines. Comments table.

### Sprint 3 — Google Ads cluster
- Overview: KPIs (cost, conv, CPA, ROAS, IS%). TrendLine cost+conv dual axis. Pie cost by channel.
- Campaigns: Bubble (x=cost, y=conv rate, size=impressions, shape=channel type). Table with change-log badges.
- Search: Bar top keywords by conv. Scatter quality score vs CPC.
- Assets: Grid with heat-tinted thumbnails + per-asset sparkline.
- Pmax: Asset-group treemap (size=spend, color=ROAS).
- Conversions: Funnel + source-mix pie.
- Pacing: Gauge ring + MTD bar vs budget line.
- Changes / Recommendations / Reports: Tables with severity chips.

### Sprint 4 — Combined + Map + Web
- `platforms`: cross-platform KPIs. Stacked area trend by platform. Small-multiples bar per KPI. Platform-comparison table.
- `campaigns` / `creatives` / `budget` / `audience`: each gets 5-block layout bound to both platforms, platform-color legend.
- `map` (ParishMapDetail): choropleth with KPI picker, bubble overlay per account location, sparkline tooltip.
- `web/ga4`, `web/search-console`: KPI strip + trend + device/source pies. Do NOT fetch `/combined/`.
- Saved dashboards + builder: grid-snapped slot system using shared kit.

## 6. Agentic workflow wiring

```
[repo state] ──> A0 Audit ──► artifacts/audit/audit-report.json
                                   │
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
   A1 Meta                   A2 Google Ads            A3 Combined
   artifacts/verify/         artifacts/verify/        artifacts/verify/
   meta-verification.json    google-verification.json combined-verification.json
          │                        │                        │
          └────────────────────────┼────────────────────────┘
                                   ▼
                          A4 Synthesizer
                          artifacts/synthesis/synthesis-report.md
                          artifacts/synthesis/merged.patch
                                   │
                                   ▼
                          A5 Data-viz planner
                          artifacts/viz/sprints-plan.md
                                   │
                                   ▼
                          A6 Agentic workflow spec
                          artifacts/viz/coder-prompts/<sprint-N>/<page>.md
```

**Artifact conventions:**
- Every JSON artifact has `schema_version`, `agent_id`, `inputs_hash`, `findings[]` or equivalent array.
- Downstream agent names upstream artifact by path in its first line of context.

## 7. Out of scope / non-goals

- Do NOT change auth, tenant-middleware, or RLS.
- Do NOT alter adapter priority / selection in `combined_metrics_service`.
- Do NOT modify `_resolve_platform_only_scoping` or `_collect_tenant_platform_accounts` — they just landed and have tests.
- Do NOT re-architect `useDashboardStore` / `useMetaStore`. Reconciliation effects only.
- Do NOT introduce a new charting library; extend the one in use.
- Do NOT add backend endpoints in verification phase (viz sprints may, only if a chart strictly cannot be served by `/api/metrics/combined/`).
- Do NOT touch `SavedDashboardPage` serialization format in verification phase.

## 8. Critical files
- `frontend/src/router.tsx`
- `frontend/src/routes/DashboardLayout.tsx`
- `backend/analytics/combined_metrics_service.py`
- `backend/analytics/views.py`
- `frontend/src/routes/PlatformDashboard.tsx`
