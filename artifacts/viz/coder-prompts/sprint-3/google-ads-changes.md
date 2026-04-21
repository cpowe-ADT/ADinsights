# Google Ads Changes + Recommendations Tabs — Visualization Upgrade

**Sprint:** 3
**Estimated size:** S
**Depends on:** sprint-1/kpi-tile.md, sprint-1/distribution-bar.md, sprint-1/data-table.md, sprint-1/chart-skeleton.md
**Blocks:** none
**Role needed:** frontend-engineer

## Context

Two low-complexity tabs combined in one prompt (both are primarily tables with minimal chart work):

1. **Changes tab** — `GET /api/google-ads/change-events/`: change log with type distribution bar and table.
2. **Recommendations tab** — `GET /api/google-ads/recommendations/`: active recommendations with type pie and table. Dismiss PATCH endpoint does NOT exist — suppress dismiss button.

## Inputs already in the repo (do not re-invent)

- Change event row fields: `customer_id, change_date_time, user_email, client_type, change_resource_type, resource_change_operation, campaign_id, ad_group_id, ad_id, changed_fields`
- Recommendation row fields (verified from `backend/analytics/google_ads_views.py:1413–1442`): `customer_id, recommendation_type, resource_name, campaign_id, ad_group_id, dismissed, impact_metadata, last_seen_at`
- All Sprint 1 viz components.

## Deliverables

- **Files to create/modify**: Changes tab component + Recommendations tab component (identify paths in `frontend/src/routes/google-ads/`).
- Create test files for both.

### Changes Tab

- **Data binding**:
  - KPI strip (2 tiles): Total Changes = count rows; Changes Last 7d = count where `change_date_time > now - 7d` (compute client-side).
  - DistributionBar: group rows by `change_resource_type`, count per type. Top 8 types.
  - DataTable: Date/Time (formatted), User Email, Resource Type, Operation, Campaign ID (truncated), Changed Fields (truncated at 100 chars). No row click. CSV export filename `google-ads-changes`. Paginated (25 per page).

- **Design**:
```
┌────────────────────────────────────────────────────────┐
│ [Total Changes] [Last 7d]                              │  ← 2 KpiTiles
├────────────────────────────────────────────────────────┤
│ DistributionBar: Changes by resource type              │
├────────────────────────────────────────────────────────┤
│ DataTable: Date | User | Type | Operation | Campaign   │  ← paginated, CSV
└────────────────────────────────────────────────────────┘
```

### Recommendations Tab

- **Data binding**:
  - KPI strip (2 tiles): Active Recommendations = count where `dismissed === false`; Dismissed = count where `dismissed === true`.
  - PieComposition: group rows by `recommendation_type`, count per type. Filter to `dismissed === false` rows for the pie.
  - DataTable: Type, Campaign ID, Impact (from `impact_metadata` — render as JSON summary or key value), Status chip (`dismissed ? 'Dismissed' : 'Active'`), Last Seen. **No dismiss button** (no PATCH endpoint).
  - CSV export filename `google-ads-recommendations`.

- **Design**:
```
┌────────────────────────────────────────────────────────┐
│ [Active Recs] [Dismissed]                              │  ← 2 KpiTiles
├──────────────────────────────┬─────────────────────────┤
│ PieComposition: by rec type  │  [reserved]             │
├──────────────────────────────┴─────────────────────────┤
│ DataTable: Type | Campaign | Impact | Status | Seen    │  ← CSV export
│ {/* Dismiss: [NEW-ENDPOINT] PATCH dismiss - pending */}│
└────────────────────────────────────────────────────────┘
```

## Definition of Done

- [ ] Changes tab: 2 KpiTiles, DistributionBar, DataTable
- [ ] Recommendations tab: 2 KpiTiles, PieComposition, DataTable
- [ ] Dismiss button suppressed with `[NEW-ENDPOINT]` comment
- [ ] Loading and empty states for both tabs
- [ ] Tests green for both
- [ ] Lint clean and build clean

## Test deltas

Changes tab:
```typescript
it('renders 2 KpiTiles for changes', () => { ... })
it('renders DistributionBar for change types', () => { ... })
it('DataTable renders change log rows', () => { ... })
```

Recommendations tab:
```typescript
it('renders 2 KpiTiles for recommendations', () => { ... })
it('renders PieComposition for rec types', () => { ... })
it('DataTable does NOT render a dismiss button', () => {
  expect(screen.queryByRole('button', { name: /dismiss/i })).not.toBeInTheDocument()
})
```

## Out of scope

- Do NOT implement dismiss PATCH endpoint
- Do NOT add accept/apply recommendation actions

## Open questions resolved

- **OQ-5 (Recommendations dismiss PATCH — unconfirmed)**: CONFIRMED NOT AVAILABLE. `GoogleAdsRecommendationsView` only has a `get()` method. No PATCH endpoint in `backend/analytics/urls.py`. Resolution: suppress dismiss button, add `{/* Dismiss: [NEW-ENDPOINT] PATCH /api/google-ads/recommendations/:id/dismiss/ */}` comment.
