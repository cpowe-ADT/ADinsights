# ADinsights Data-Visualization Program — Execution Index

**Input artifacts cited:**
- `/Users/thristannewman/ADinsights/artifacts/plan.md`
- `/Users/thristannewman/ADinsights/artifacts/viz/sprints-plan.md`
- `/Users/thristannewman/ADinsights/artifacts/synthesis/synthesis-report.md`
- `/Users/thristannewman/ADinsights/artifacts/verify/meta-verification.json`
- `/Users/thristannewman/ADinsights/artifacts/verify/google-verification.json`
- `/Users/thristannewman/ADinsights/artifacts/verify/combined-verification.json`

---

## Program Context

ADinsights is a multi-tenant marketing analytics platform for Jamaican agencies. This 4-sprint program upgrades every dashboard page from ad-hoc HTML to a consistent, accessible visualization kit. The program is preceded by a 7-agent verification and synthesis phase (A0–A5) that:
- Audited cross-platform data leakage risks (A0)
- Verified and patched Meta, Google Ads, and combined routes (A1–A3)
- Synthesized all patches into a green build (A4 — 727 backend tests passing, lint clean, build clean)
- Produced a full page-by-page chart specification (A5)

This file (produced by A6) is the handoff to implementation. All 11 open questions from A5 have been resolved below.

---

## How to Execute

Each file in `coder-prompts/sprint-N/` is a self-contained coder-agent prompt. Paste one file into a fresh session with a frontend-engineer agent. The agent needs no other context — every prompt includes the full spec, data binding, test deltas, and constraints.

**Execution model:**
1. Start with **Sprint 1** — all components are prerequisites. Sprint 1 deliverables can be worked in parallel but must all complete before any Sprint 2/3/4 work begins.
2. **Sprint 2** (Meta) and **Sprint 3** (Google Ads) can be run in parallel once Sprint 1 is done.
3. **Sprint 4** (Combined + Map + Web) starts after Sprint 1 is complete. Sprint 4 pages can be worked in parallel except `saved-dashboards.md` which depends on other Sprint 4 components being done.

---

## Recommended Execution Order

```
Sprint 1 (parallel within sprint):
  1a: chart-skeleton.md  ← no dependencies
  1a: kpi-tile.md        ← no dependencies
  1a: sparkline.md       ← no dependencies
  1a: accessible-table-toggle.md ← no dependencies
  1b: trend-line.md      ← after chart-skeleton, accessible-table-toggle
  1b: distribution-bar.md ← after chart-skeleton, accessible-table-toggle
  1b: pie-composition.md ← after chart-skeleton, accessible-table-toggle
  1b: bubble-scatter.md  ← after chart-skeleton, accessible-table-toggle
  1c: data-table.md      ← after chart-skeleton, sparkline
  1d: storybook-stories.md ← after all above

Sprint 2 + Sprint 3 (fully parallel with each other):
  2: meta-accounts.md | meta-insights.md | meta-campaigns.md
     meta-pages-overview.md | meta-posts.md | meta-post-detail.md | meta-status.md
  3: google-ads-overview.md | google-ads-campaigns.md | google-ads-search.md
     google-ads-assets.md | google-ads-pmax.md | google-ads-conversions.md
     google-ads-pacing.md | google-ads-changes.md (includes recommendations)

Sprint 4 (mostly parallel):
  4: platforms.md  ← creates platformLabels.ts (must complete before campaigns.md)
  4: campaigns.md  ← after platforms.md (imports platformLabels.ts)
  4: audience.md | map.md | web-ga4.md | web-search-console.md  ← parallel
  4: saved-dashboards.md  ← after all other Sprint 4 components
```

---

## Per-Sprint Definitions of Done

### Sprint 1
- All 9 components render in Storybook with Default / Loading / Empty story variants
- jest-axe a11y assertions pass in vitest for every component
- DataTable CSV export snapshot test passes
- AccessibleTableToggle keyboard-operable (tab + Enter/Space)
- TrendLine renders peer average line when `peerData` provided
- No new npm packages installed
- `PLATFORM_CHART_TOKENS` exported from `chartTheme.ts`
- Tests green (excluding pre-existing DataSources.test.tsx failures)
- Lint clean, Build clean

### Sprint 2
- All Meta routes render with real data from `useMetaStore` / Meta endpoints
- No `/api/metrics/combined/` call from `meta/status`, `meta/pages`, `meta/posts`
- EmptyState with correct `reasonCode` for zero-account and zero-data tenants
- Playwright: account row click → insights scoped to that account

### Sprint 3
- All Google Ads workspace tabs render charts bound to correct endpoints
- `platforms=google_ads` sent on every combined call from these routes
- `customer_id` seeded from global store on workspace mount
- All charts have EmptyState + loading skeleton

### Sprint 4
- `platforms` page shows both platforms, no cross-platform row leakage
- `map` page renders choropleth with parish data
- `web/ga4` and `web/search-console` make no `/combined/` calls
- Saved dashboards builder renders slots using kit components
- Tests green, Lint clean, Build clean

---

## Agent Roster

| Role | Sprints | Skills needed |
|------|---------|---------------|
| `frontend-engineer` | Sprint 1 (kit), Sprint 2 (Meta), Sprint 4 (combined/web) | React 18, Recharts, TanStack Table, vitest, jest-axe |
| `data-viz-specialist` | Sprint 1 (Storybook/A11y), Sprint 3 (Pacing gauge, PMax treemap) | Recharts advanced, WCAG AA, Storybook 8 |
| `frontend-engineer` | Sprint 3 (Google Ads) | Recharts, workspace hooks, Google Ads domain |
| `frontend-engineer` | Sprint 4 (Leaflet map) | Leaflet 1.9, choropleth, GeoJSON |

---

## Progress Tracking

| Sprint | Deliverable | File | Status | Owner |
|--------|------------|------|--------|-------|
| 1 | KpiTile | `sprint-1/kpi-tile.md` | not started | — |
| 1 | TrendLine | `sprint-1/trend-line.md` | not started | — |
| 1 | Sparkline | `sprint-1/sparkline.md` | not started | — |
| 1 | DistributionBar | `sprint-1/distribution-bar.md` | not started | — |
| 1 | BubbleScatter | `sprint-1/bubble-scatter.md` | not started | — |
| 1 | PieComposition | `sprint-1/pie-composition.md` | not started | — |
| 1 | DataTable | `sprint-1/data-table.md` | not started | — |
| 1 | ChartSkeleton | `sprint-1/chart-skeleton.md` | not started | — |
| 1 | AccessibleTableToggle | `sprint-1/accessible-table-toggle.md` | not started | — |
| 1 | Storybook stories | `sprint-1/storybook-stories.md` | not started | — |
| 2 | Meta Accounts | `sprint-2/meta-accounts.md` | not started | — |
| 2 | Meta Insights | `sprint-2/meta-insights.md` | not started | — |
| 2 | Meta Campaigns | `sprint-2/meta-campaigns.md` | not started | — |
| 2 | Meta Pages + Overview | `sprint-2/meta-pages-overview.md` | not started | — |
| 2 | Meta Posts | `sprint-2/meta-posts.md` | not started | — |
| 2 | Meta Post Detail | `sprint-2/meta-post-detail.md` | not started | — |
| 2 | Meta Status | `sprint-2/meta-status.md` | not started | — |
| 3 | Google Ads Overview | `sprint-3/google-ads-overview.md` | not started | — |
| 3 | Google Ads Campaigns | `sprint-3/google-ads-campaigns.md` | not started | — |
| 3 | Google Ads Search | `sprint-3/google-ads-search.md` | not started | — |
| 3 | Google Ads Assets | `sprint-3/google-ads-assets.md` | not started | — |
| 3 | Google Ads PMax | `sprint-3/google-ads-pmax.md` | not started | — |
| 3 | Google Ads Conversions | `sprint-3/google-ads-conversions.md` | not started | — |
| 3 | Google Ads Pacing | `sprint-3/google-ads-pacing.md` | not started | — |
| 3 | Google Ads Changes + Recs | `sprint-3/google-ads-changes.md` | not started | — |
| 4 | Platforms Dashboard | `sprint-4/platforms.md` | not started | — |
| 4 | Campaigns + Creatives + Budget | `sprint-4/campaigns.md` | not started | — |
| 4 | Audience Dashboard | `sprint-4/audience.md` | not started | — |
| 4 | Parish Map | `sprint-4/map.md` | not started | — |
| 4 | GA4 Dashboard | `sprint-4/web-ga4.md` | not started | — |
| 4 | Search Console Dashboard | `sprint-4/web-search-console.md` | not started | — |
| 4 | Saved Dashboards Builder | `sprint-4/saved-dashboards.md` | not started | — |

---

## Open Questions from A5 — Resolutions

All 11 open questions from A5's plan have been resolved by A6. Resolutions are embedded in each prompt file's "Open questions resolved" section and summarized here:

| # | Question | Resolution | Prompt file |
|---|----------|-----------|-------------|
| OQ-1 | Campaign daily series — may need new endpoint | SCOPED DOWN: `/api/google-ads/campaigns/` returns aggregate rows only. Replace TrendLine with DistributionBar (top campaigns by spend). Per-campaign daily series is `[NEW-ENDPOINT]` if needed later. | `sprint-3/google-ads-campaigns.md` |
| OQ-2 | Post comments endpoint (none exists) | SCOPED DOWN: Comments block suppressed. Add `[NEW-ENDPOINT]` JSX comment for `GET /api/integrations/posts/:postId/comments/`. | `sprint-2/meta-post-detail.md` |
| OQ-3 | Per-asset sparklines (no endpoint) | SCOPED DOWN: Sparkline column suppressed. Add `[NEW-ENDPOINT]` comment for `GET /api/google-ads/assets/:assetId/timeseries/`. | `sprint-3/google-ads-assets.md` |
| OQ-4 | Impression Share metric (unconfirmed in Google Ads payload) | CONFIRMED NOT AVAILABLE: `_build_executive_payload` (line 270–433 in `google_ads_views.py`) returns `metrics: { spend, impressions, clicks, conversions, conversion_value }` — no IS field. IS tile deferred with `[DEFERRED]` comment. | `sprint-3/google-ads-overview.md` |
| OQ-5 | Recommendations dismiss PATCH (unconfirmed) | CONFIRMED NOT AVAILABLE: `GoogleAdsRecommendationsView` has only `get()`. No PATCH in `urls.py`. Dismiss button suppressed, `[NEW-ENDPOINT]` comment added. | `sprint-3/google-ads-changes.md` |
| OQ-6 | FunnelChart availability in Recharts v3.7.0/3.8.1 | CONFIRMED NOT AVAILABLE: Recharts 3.x removed FunnelChart. Verified via package-lock.json (installed: 3.8.1). Resolution: use stepped-bar `DistributionBar` with 3 bars + drop-off annotations. | `sprint-2/meta-campaigns.md`, `sprint-3/google-ads-conversions.md` |
| OQ-7 | PapaParse dependency check | CONFIRMED NOT INSTALLED: `papaparse` absent from `frontend/package.json`. Resolution: hand-rolled CSV serializer in `DataTable` (no new package). | `sprint-1/data-table.md` |
| OQ-8 | `@storybook/addon-a11y` availability | CONFIRMED NOT INSTALLED: Storybook 8.6.14 installed without addon-a11y. Resolution: use `jest-axe` (already installed as devDependency) for a11y assertions in vitest. Storybook stories don't run axe. | `sprint-1/storybook-stories.md` |
| OQ-9 | Parish daily time series for map sparkline tooltip | CONFIRMED NOT AVAILABLE: `/api/metrics/combined/` returns `parish[]` with aggregate totals, no daily breakdown. Sparkline in tooltip suppressed. `[NEW-ENDPOINT]` comment added. | `sprint-4/map.md` |
| OQ-10 | `by_channel` in executive payload vs channels endpoint | CONFIRMED SEPARATE ENDPOINT: `_build_executive_payload` does not include `by_channel`. Use `GET /api/google-ads/channels/` (confirmed at `urls.py:72` — `GoogleAdsChannelPerformanceView`). | `sprint-3/google-ads-overview.md` |
| OQ-11 | `account_id` field presence in `campaign.rows` for multi-account TrendLine | DISCOVERY STEP ADDED: `campaign.rows` from `/api/metrics/combined/` may or may not include `account_id`. Each prompt that uses multi-series TrendLine includes a "verify field availability" note and a single-series fallback. | `sprint-2/meta-accounts.md`, `sprint-2/meta-insights.md` |

---

## Deferred to Future Sprints

These items are out of scope for all 4 sprints and should be tracked separately:

| Item | Reason | Marker in codebase |
|------|--------|-------------------|
| Post comments table | No backend endpoint | `[NEW-ENDPOINT]` comment in MetaPostDetailPage |
| Per-asset sparklines | No per-asset daily series endpoint | `[NEW-ENDPOINT]` comment in Assets tab |
| Per-campaign daily time series | No date dimension on campaigns endpoint | `[NEW-ENDPOINT]` comment in Campaigns tab |
| Impression Share KPI tile | Not in executive payload | `[DEFERRED]` comment in Overview tab |
| Recommendations dismiss PATCH | No PATCH endpoint | `[NEW-ENDPOINT]` comment in Recs tab |
| Parish sparkline in map tooltip | No daily series for parishes | `[NEW-ENDPOINT]` comment in map popup |
| Age×Gender heatmap | Requires custom SVG or new chart lib — use grouped bar instead | noted in audience.md |
| Saved dashboard per-slot endpoint resolution | Future sprint — uses combined payload for now | noted in saved-dashboards.md |
| B-CAMP-01 / B-CREA-01 row-level platform filter | Store surgery deferred by A4 | synthesis-report.md |
| B-AUD-01 full fix | Partially applied; zero-row guard done | synthesis-report.md |
| Playwright E2E for Google Ads workspace (B5) | Authored separately in qa/ | synthesis-report.md |
| DataSources.test.tsx scrollIntoView | Pre-existing JSDOM incompatibility, unrelated to this program | synthesis-report.md |

---

## Non-Goals (from plan.md §7)

The following were explicitly out of scope for the entire program. Do not implement:
- Changes to auth, tenant-middleware, or RLS
- Changes to adapter priority / selection in `combined_metrics_service`
- Changes to `_resolve_platform_only_scoping` or `_collect_tenant_platform_accounts`
- Re-architecting `useDashboardStore` / `useMetaStore` (reconciliation effects only)
- Introducing a new charting library (extend Recharts only)
- New backend endpoints in the verification phase (viz sprints may add them only if strictly required)
- Changes to `SavedDashboardPage` serialization format in the verification phase
