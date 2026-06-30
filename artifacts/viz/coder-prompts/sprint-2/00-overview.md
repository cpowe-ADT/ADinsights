# Sprint 2 Overview — Meta Cluster

**Sprint:** 2
**Prerequisite:** Sprint 1 shared viz kit must be fully merged.

## What this sprint does

Upgrades all Meta dashboard pages to the 5-block viz layout using Sprint 1 components. All Meta routes talk exclusively to `useMetaStore` and Meta-specific endpoints — they do NOT call `/api/metrics/combined/`. The R7 reconciliation effect (bridging `useMetaStore.accountId` → `useDashboardStore` when on `/dashboards/meta/*` routes) is already applied by A4 synthesis.

## Deliverable ordering within Sprint 2

These files can be worked in parallel:

| Deliverable                                  | File                     | Store/Endpoint                              | Parallelizable? |
| -------------------------------------------- | ------------------------ | ------------------------------------------- | --------------- |
| MetaAccountsPage viz                         | `meta-accounts.md`       | `useMetaStore` + combined(meta)             | Yes             |
| MetaInsightsDashboardPage viz                | `meta-insights.md`       | `useMetaStore` + combined(meta)             | Yes             |
| MetaCampaignOverviewPage viz                 | `meta-campaigns.md`      | `useMetaStore` + combined(meta)             | Yes             |
| MetaPagesListPage viz                        | `meta-pages-overview.md` | `useMetaStore` + `/api/integrations/pages/` | Yes             |
| MetaPageOverviewPage + MetaPagePostsPage viz | `meta-posts.md`          | pages endpoints                             | Yes             |
| MetaPostDetailPage viz                       | `meta-post-detail.md`    | post detail + timeseries                    | Yes             |
| Meta status page check                       | `meta-status.md`         | —                                           | Yes (tiny)      |

## Key constraints for all Sprint 2 work

- All patches to existing route files — do NOT create new route files
- Do NOT call `/api/metrics/combined/` from `meta/status`, `meta/pages`, `meta/posts/:id`
- Import viz components from `frontend/src/components/viz/` (Sprint 1 output)
- `EmptyState` is at `frontend/src/components/EmptyState.tsx` with `reasonCode` prop
- `useMetaStore` is the authoritative store for all Meta pages
- FunnelChart is NOT available in Recharts 3.8.1 — use stepped-bar fallback (see `meta-campaigns.md`)
- `payload.campaign.trend` is aggregated across all accounts; per-account series requires client-side grouping from `campaign.rows` on `account_id` — **verify `campaign.rows` includes `account_id` field before implementing multi-series TrendLine**

## Sprint 2 Definition of Done

- [ ] All Meta routes render with real data from `useMetaStore` / Meta endpoints
- [ ] No `/api/metrics/combined/` call fired from `meta/status` or `meta/pages` list
- [ ] `account_id` selection from MetaAccountsPage propagates to MetaInsightsDashboardPage (R7 reconciliation already applied)
- [ ] EmptyState with correct `reasonCode` for zero-account and zero-data tenants
- [ ] vitest: new tests for each new chart component wiring
- [ ] Playwright test: account row click → insights scoped to that account (add to `qa/tests/meta-accounts.spec.ts`)
- [ ] `cd frontend && npm test -- --run` green (excluding pre-existing DataSources failures)
- [ ] `cd frontend && npm run lint` clean
- [ ] `cd frontend && npm run build` clean
