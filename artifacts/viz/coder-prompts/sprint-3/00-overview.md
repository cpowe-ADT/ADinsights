# Sprint 3 Overview — Google Ads Cluster

**Sprint:** 3
**Prerequisite:** Sprint 1 shared viz kit must be fully merged.

## What this sprint does

Upgrades all Google Ads workspace tabs to the viz layout using Sprint 1 components. The workspace operates under `GOOGLE_ADS_WORKSPACE_UNIFIED=true`. All tab endpoints are under `/api/google-ads/*`. A4 synthesis applied fixes B1 (`platforms=google_ads` added to `buildCommonParams`), B2 (customer_id seeding from global store on workspace mount), B6–B8 (scope params on all tab fetches).

## Verified endpoints (from `backend/analytics/google_ads_views.py` + `urls.py`)

| Tab                          | Endpoint                                 | URL pattern                       |
| ---------------------------- | ---------------------------------------- | --------------------------------- |
| Overview / Workspace Summary | `/api/google-ads/workspace/summary/`     | `GoogleAdsWorkspaceSummaryView`   |
| Campaigns                    | `/api/google-ads/campaigns/`             | `GoogleAdsCampaignListView`       |
| Search keywords              | `/api/google-ads/keywords/`              | —                                 |
| Search terms                 | `/api/google-ads/search-terms/`          | —                                 |
| Assets                       | `/api/google-ads/assets/`                | —                                 |
| PMax asset groups            | `/api/google-ads/pmax-asset-groups/`     | —                                 |
| Conversions                  | `/api/google-ads/conversions-by-action/` | —                                 |
| Pacing                       | `/api/google-ads/budget-pacing/`         | —                                 |
| Changes                      | `/api/google-ads/change-events/`         | —                                 |
| Recommendations              | `/api/google-ads/recommendations/`       | `GoogleAdsRecommendationsView`    |
| Channel performance          | `/api/google-ads/channels/`              | `GoogleAdsChannelPerformanceView` |

**Key findings from source inspection:**

- The workspace summary (`/api/google-ads/workspace/summary/`) returns: `metrics` (spend, impressions, clicks, conversions, conversion_value), `comparison`, `pacing` (spend_mtd, budget_month, forecast_month_end, over_under, pacing_pct), `trend[]` (date, spend, conversions, roas), `movers[]` (top 10 by spend), `alerts_summary` (overspend_risk, underdelivery, spend_spike, conversion_drop), `governance_summary` (recent_changes_7d, active_recommendations, disapproved_ads), `top_insights[]`.
- **Impression share is NOT in the executive payload.** The `metrics` object contains only spend, impressions, clicks, conversions, conversion_value. Defer the IS tile.
- Campaign daily time series: `GET /api/google-ads/campaigns/` returns AGGREGATED rows (no date dimension). Use `GET /api/google-ads/channels/` for a cost+conversions trend by channel type. For per-campaign daily series: `[NEW-ENDPOINT]`.
- Recommendations dismiss: `GET /api/google-ads/recommendations/` exists; no `PATCH`/dismiss endpoint found. Suppress dismiss button.
- Channel pie on overview: use `GET /api/google-ads/channels/` endpoint which returns rows by `advertising_channel_type`.

## Deliverable ordering

Can be worked in parallel:

| Deliverable         | File                            | Priority |
| ------------------- | ------------------------------- | -------- |
| Overview tab        | `google-ads-overview.md`        | High     |
| Campaigns tab       | `google-ads-campaigns.md`       | High     |
| Search tab          | `google-ads-search.md`          | Medium   |
| Assets tab          | `google-ads-assets.md`          | Medium   |
| PMax tab            | `google-ads-pmax.md`            | Medium   |
| Conversions tab     | `google-ads-conversions.md`     | Medium   |
| Pacing tab          | `google-ads-pacing.md`          | Medium   |
| Changes tab         | `google-ads-changes.md`         | Low      |
| Recommendations tab | `google-ads-recommendations.md` | Low      |

## Sprint 3 Definition of Done

- [ ] All Google Ads workspace tabs render charts bound to correct endpoints
- [ ] `platforms=google_ads` sent on every combined call from these routes
- [ ] `customer_id` seeded from global store on workspace mount (B2 fix confirmed)
- [ ] All charts have `EmptyState` + loading skeleton
- [ ] vitest: chart binding tests for each tab
- [ ] `cd frontend && npm test -- --run` green
- [ ] `cd frontend && npm run lint` clean
- [ ] `cd frontend && npm run build` clean
