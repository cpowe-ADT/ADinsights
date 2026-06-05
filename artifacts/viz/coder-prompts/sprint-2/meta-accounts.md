# Meta Accounts Page — Visualization Upgrade

**Sprint:** 2
**Estimated size:** M
**Depends on:** sprint-1/kpi-tile.md, sprint-1/trend-line.md, sprint-1/pie-composition.md, sprint-1/data-table.md, sprint-1/chart-skeleton.md
**Blocks:** none
**Role needed:** frontend-engineer

## Context

`MetaAccountsPage` is the entry point for the Meta cluster at `/dashboards/meta/accounts`. It lists all connected Meta ad accounts with aggregate KPIs. The A4 synthesis already added a row-click handler that sets `useMetaStore.filters.accountId` (M2 fix), and the R7 reconciliation effect in `DashboardLayout` bridges that value to `useDashboardStore`. This sprint upgrades the page from ad-hoc HTML to the shared viz kit layout.

## Inputs already in the repo (do not re-invent)

- `frontend/src/routes/MetaAccountsPage.tsx`: existing route file to modify. A4 patches applied (M1–M3).
- `frontend/src/stores/useMetaStore*`: account data store.
- `frontend/src/components/viz/KpiTile.tsx`: Sprint 1 output.
- `frontend/src/components/viz/TrendLine.tsx`: Sprint 1 output.
- `frontend/src/components/viz/PieComposition.tsx`: Sprint 1 output.
- `frontend/src/components/viz/DataTable.tsx`: Sprint 1 output.
- `frontend/src/components/viz/ChartSkeleton.tsx`: Sprint 1 output.
- `frontend/src/components/EmptyState.tsx`: `reasonCode` prop present.
- `frontend/src/styles/chartTheme.ts`: `PLATFORM_CHART_TOKENS` added in Sprint 1.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/routes/MetaAccountsPage.tsx` (modify — add viz layout)
  - `frontend/src/routes/__tests__/MetaAccountsPage.test.tsx` (modify — add viz tests)

- **Data binding**:
  - KPI strip: from `useMetaStore` accounts list aggregate — compute client-side: total spend = sum of `account.spend`, total impressions = sum of `account.impressions`, total reach = sum of `account.reach`; avg CTR = total clicks / total impressions; avg CPM = (total spend / total impressions) \* 1000; active accounts = count where `account.status === 'ACTIVE'`.
  - NOTE: The accounts list endpoint (`/api/integrations/meta/ad-accounts/`) returns per-account metrics. Verify which fields are present in `useMetaStore.accounts.rows[]` before implementing KPI aggregation. If `spend`, `impressions`, `reach` are not present on the accounts list, show 0 / `--` and add a `[NEW-ENDPOINT]` comment.
  - TrendLine: `payload.campaign.trend` from `/api/metrics/combined/?platforms=meta_ads` — aggregated spend by day. For multi-account series: group `payload.campaign.rows` by `account_id` field, sum spend per day per account using `trend` dates as X axis. **If `account_id` field is absent from `campaign.rows`, fall back to a single total-spend line.**
  - PieComposition: `payload.campaign.rows` grouped by `objective` field.
  - DataTable: `useMetaStore.accounts.rows[]` — columns: Account Name, Spend, Impressions, Reach, CTR, CPM, ROAS.

- **Interactions**:
  - DataTable row click → `navigate('/dashboards/meta/insights?account_id=' + row.external_id)`. This is already wired by A4 (M2 fix); confirm the `onClick` pattern is consistent with `DataTable.onRowClick`.
  - TrendLine `onPointClick` → no-op for this page.

- **Empty/loading/error states**:
  - `accounts.status === 'loading'`: all blocks show `ChartSkeleton` variant matching block shape.
  - `accounts.rows.length === 0 && accounts.status !== 'loading'`: `EmptyState reasonCode="no_accounts"` full-page.
  - `payload empty but accounts exist`: `EmptyState reasonCode="no_data_for_range"` per block.
  - Do NOT show EmptyState while status is loading (A4 M3 fix already guards this — verify it is present in the file).

- **A11y**: KPI strip `role="list"` container with each tile as `role="listitem"`. Table: existing `DataTable` a11y. No new a11y work beyond using kit components.

## Design

```
┌──────────────────────────────────────────────────────────┐
│ [Spend] [Impressions] [Reach] [Avg CTR] [Avg CPM] [Active]│  ← 6 KpiTiles
├──────────────────────────────────────────────────────────┤
│ Spend by Day (TrendLine — multi-series by account)        │  ← height=260
├──────────────────────────────┬───────────────────────────┤
│ Spend by Objective (Pie)     │    [reserved for future]  │  ← 50/50
├──────────────────────────────┴───────────────────────────┤
│ DataTable: accounts with Spend, Impressions, Reach, CTR..│  ← sortable, CSV export
└──────────────────────────────────────────────────────────┘
```

## Definition of Done

- [ ] 6 KpiTiles render with loading shimmer and correct values
- [ ] TrendLine renders spend over time (single series if `account_id` in rows absent)
- [ ] PieComposition renders spend by objective
- [ ] DataTable replaces ad-hoc `<table>` with sortable, clickable rows
- [ ] Row click navigates to `/dashboards/meta/insights?account_id=...`
- [ ] Loading: all blocks show ChartSkeleton (no flash of empty state)
- [ ] Zero accounts: `EmptyState reasonCode="no_accounts"` shown
- [ ] Tests green: `cd frontend && npm test -- --run src/routes/__tests__/MetaAccountsPage.test.tsx`
- [ ] Lint clean: `cd frontend && npm run lint`
- [ ] Build clean: `cd frontend && npm run build`

## Test deltas

Modify `frontend/src/routes/__tests__/MetaAccountsPage.test.tsx`. Add:

```typescript
// Mock useMetaStore with accounts data
const mockAccounts = [
  { id: 1, external_id: 'act_111', name: 'Brand Account', status: 'ACTIVE', spend: 50000, impressions: 1000000 },
  { id: 2, external_id: 'act_222', name: 'Retargeting', status: 'ACTIVE', spend: 20000, impressions: 400000 },
]

it('renders 6 KpiTile components', () => {
  // Set up store with loaded accounts
  renderWithProviders(<MetaAccountsPage />)
  expect(screen.getAllByRole('figure').length).toBeGreaterThanOrEqual(4) // min 4 KPIs visible
})

it('renders DataTable with account rows', () => {
  renderWithProviders(<MetaAccountsPage />)
  expect(screen.getByText('Brand Account')).toBeInTheDocument()
  expect(screen.getByText('Retargeting')).toBeInTheDocument()
})

it('row click navigates to insights with account_id', async () => {
  const user = userEvent.setup()
  renderWithProviders(<MetaAccountsPage />)
  await user.click(screen.getByText('Brand Account'))
  expect(mockNavigate).toHaveBeenCalledWith('/dashboards/meta/insights?account_id=act_111')
})

it('shows EmptyState with reasonCode="no_accounts" when no accounts', () => {
  // set accounts.rows = [], status = 'loaded'
  renderWithProviders(<MetaAccountsPage />)
  expect(screen.getByTestId('empty-state')).toHaveAttribute('data-reason-code', 'no_accounts')
})

it('does NOT show EmptyState while accounts.status === "loading"', () => {
  // set status = 'loading'
  renderWithProviders(<MetaAccountsPage />)
  expect(screen.queryByTestId('empty-state')).not.toBeInTheDocument()
  expect(screen.getByRole('status')).toBeInTheDocument() // skeleton
})
```

## Out of scope

- Do NOT modify `useMetaStore`
- Do NOT add a new endpoint for per-account spend time series (use fallback to single-series if `account_id` not in rows)
- Do NOT replace the existing account-row click handler — extend it to work with DataTable's `onRowClick`
