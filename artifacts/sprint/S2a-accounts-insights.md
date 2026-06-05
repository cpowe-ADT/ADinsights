# S2a-AccountsInsights — Closeout

**Inputs cited:** `/Users/thristannewman/ADinsights/artifacts/sprint/S2-architect-design.md` (§4.1, §4.2, §3 audit rows for Accounts + Insights), `/Users/thristannewman/ADinsights/artifacts/sprint/S1-final-closeout.md`, `/Users/thristannewman/ADinsights/frontend/src/components/viz/index.ts`, `/Users/thristannewman/ADinsights/frontend/src/lib/meta.ts`, `/Users/thristannewman/ADinsights/frontend/src/state/useMetaStore.ts`, `/Users/thristannewman/ADinsights/artifacts/viz/sprints-plan.md` (§5).

## Files Modified / Added

| File                                                               | Change summary                                                                                                                                                                                                                                                                                                                                                 | Lines (+/−) |
| ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| `frontend/src/routes/MetaAccountsPage.tsx`                         | Added KPI strip (6 tiles), multi-series TrendLine with peer-avg, PieComposition spend-by-objective, AccessibleTableToggle on trend + pie, row-click navigate to Insights, new `loadCampaigns` + `loadInsights` dispatches; retained orphan/recovery fallback and existing table.                                                                               | +334 / −63  |
| `frontend/src/routes/MetaInsightsDashboardPage.tsx`                | Added KPI strip (Spend/ROAS[conditional]/CTR/CPC/CPM — CPC substitutes for Frequency per §3), dual-axis CTR+CPM TrendLine, BubbleScatter (ROAS y-axis or CPM fallback), migrated tanstack-table grid to VizDataTable, AccessibleTableToggle on trend + bubble, preserved sync-now behavior and all filter controls.                                            | +331 / −90  |
| `frontend/src/routes/__tests__/MetaAccountsPage.test.tsx`          | Preserved Phase 1A contract tests (intro copy, row-click setFilters, recovery ghost-ID guard). Added: navigate-assertion on row click, dispatch-check for loadCampaigns/loadInsights, KPI strip label presence (6 labels), pie-objective render assertion. Updated mock store to include `campaigns`/`insights` slices + `loadCampaigns`/`loadInsights` mocks. | +210 / −15  |
| `frontend/src/routes/__tests__/MetaInsightsDashboardPage.test.tsx` | Preserved sync-now Phase 1A contract tests. Added: ROAS tile absent (no purchase actions), ROAS tile present (omni_purchase present), dual-axis CTR/CPM renders (sr-only table probe), Spend-vs-CPM fallback heading, VizDataTable replacement (records count heading).                                                                                        | +170 / −14  |
| `frontend/src/lib/metaAggregates.ts` (new)                         | Pure helpers: `sumInsights`, `groupSpendByDateAccount`, `computePeerMedian`, `topAccountsBySpend`, `spendByObjective`, `derivedRoas`, `hasPurchaseActions`, `aggregatedRoas`, `groupCtrCpmByDate`.                                                                                                                                                             | +232 / 0    |
| `frontend/src/lib/metaAggregates.test.ts` (new)                    | 10 unit tests covering the helpers above (sum math + divide-by-zero safety, date×account grouping, peer median, top-N, objective join, ROAS derivation and aggregation, CTR/CPM grouping).                                                                                                                                                                     | +190 / 0    |

## TrendLine dual-axis verification outcome

**SUPPORTED.** `frontend/src/components/viz/TrendLine.tsx` exposes:

- `rightYFormat?: ChartValueType` prop (line 62)
- Per-series `yAxis?: 'left' | 'right'` routing via `TrendLineSeries` (line 39)
- Conditional right `<YAxis yAxisId="right" orientation="right" …>` rendered when `series.some((s) => s.yAxis === 'right')` (lines 184–194)
- Per-series `yAxisId={s.yAxis ?? 'left'}` on each Recharts `<Line>` (line 212)
- sr-only accessible table formats right-axis series with `rightYFormat ?? yFormat` (line 245)

Used directly for CTR (`yAxis: 'left'`, `yFormat: 'percent'`) + CPM (`yAxis: 'right'`, `rightYFormat: 'currency'`) on `MetaInsightsDashboardPage`. **No fallback stacked charts required.**

## ROAS availability outcome

Implemented as a **conditional-derive** path per architect §3. `aggregatedRoas` returns `null` when no row has a `purchase`/`omni_purchase` action with value; `hasPurchaseActions` gates the KPI tile; `derivedRoas` gates the bubble y-axis.

- **ROAS tile**: present iff `hasPurchaseActions(rows) === true`; otherwise omitted from the KPI strip.
- **BubbleScatter y-axis**: switches to CPM (currency format, "Spend vs. CPM" heading) when ROAS unavailable; else shows ROAS (number format, "Spend vs. ROAS" heading).
- **Frequency**: per §3 audit, not derivable from `MetaInsightRecord`. Replaced with **CPC tile** (`sum(spend)/sum(clicks)`), currency-formatted.

## Data transforms — match to architect spec

- **KPI aggregates** (`sumInsights`): totalSpend, totalImpressions, totalReach, totalClicks, totalConversions, ctr = clicks/impressions, cpm = (spend/impressions)\*1000, cpc = spend/clicks. Divide-by-zero safe.
- **Active accounts** (Accounts page): `accounts.rows.filter(r => /ACTIVE|^1$/i.test(r.status)).length` — broadened from the architect's `/ACTIVE/` regex because Meta returns `account_status: 1` as the active indicator (verified against the recovery payload shape in the page's own DisplayAccountRow mapping).
- **Trend series (Accounts)**: `groupSpendByDateAccount` groups `(date, account_external_id)` and fills missing account/date cells with 0. Top-6 accounts by total spend for multi-series mode; single-series + `computePeerMedian` peer line when `filters.accountId` set.
- **Peer-avg suppression**: omitted when < 2 unique accounts in the insights slice (handles the single-tenant degenerate case per architect §7.3).
- **Spend-by-objective** (Accounts pie): `spendByObjective(insights, campaigns)` joins `campaign_external_id` → `objective`, unknown campaigns bucket into `UNKNOWN`.
- **Dual-axis trend points** (Insights): `groupCtrCpmByDate` groups by `date` and computes per-day CTR + CPM.
- **BubbleScatter** (Insights): prefers `level === 'campaign'` rows; falls back to whatever `filters.level` returns so the chart isn't empty when the user has selected a non-campaign level. `shape` is `triangle` when an account filter is active, `circle` otherwise (architect note §4.2: shape encodes level when filtered, objective otherwise — objective not on insight row, so we degrade to `circle` default).

## Store dispatch changes (additive, no shape changes)

- **MetaAccountsPage** now dispatches `loadCampaigns()` + `loadInsights()` alongside the pre-existing `loadAccounts()` in a single `useEffect` with the same dependency array (search/status/since/until/action references) — per architect §7.8 risk mitigation (single effect, not parallel).
- Both new calls are guarded by `typeof loadX === 'function'` so older tests with a thinner store mock still function (they pass the mount gracefully). The updated test mock explicitly exports the new actions and asserts they fire.
- Store signatures (`loadCampaigns()`, `loadInsights()`) take no params; `filters.level` is used as-is on `MetaAccountsPage` (default is `'ad'` but the dispatch still returns data usable for spend sums even when level isn't `'account'`). Setting `level: 'account'` from the Accounts page would mutate shared filter state and leak into the Insights page; intentionally **left un-mutated** to respect the architect constraint "NO signature/state-shape changes" on the store.

## Tests Added

### `frontend/src/lib/metaAggregates.test.ts` (10 tests)

1. `sumInsights` — sums numeric fields + derives CTR/CPM/CPC.
2. `sumInsights` — empty-input zero division safety.
3. `groupSpendByDateAccount` — fills missing (date, account) pairs with 0.
4. `computePeerMedian` — median per date.
5. `topAccountsBySpend` — sorted by descending total.
6. `spendByObjective` — joins insights × campaigns on `external_id`, buckets unknowns.
7. `derivedRoas` / `hasPurchaseActions` / `aggregatedRoas` — null on no-purchase rows.
8. Same — computes from `omni_purchase` action.
9. Same — aggregates across multiple rows.
10. `groupCtrCpmByDate` — dual-axis day-grouped CTR + CPM.

### `frontend/src/routes/__tests__/MetaAccountsPage.test.tsx` (+4 over 2 preserved = 6 total)

- (preserved) intro text + Facebook-Pages link href.
- (preserved) row click → `setFilters({accountId})` — now **also** asserts `navigate('/dashboards/meta/insights?accountId=act_123')`.
- (preserved) recovery-fallback row click → no setFilters **and** no navigate.
- `loadAccounts` + `loadCampaigns` + `loadInsights` all dispatched on mount.
- KPI strip renders all 6 labels (Spend/Impressions/Reach/CTR/CPM/Active accounts).
- Pie composition renders joined objective slices (TRAFFIC + CONVERSIONS).

### `frontend/src/routes/__tests__/MetaInsightsDashboardPage.test.tsx` (+5 over 2 preserved = 7 total)

- (preserved) sync-now triggers + load dispatches + queued toast.
- (preserved) sync-now conflict-reuse path + "already running" toast.
- ROAS tile hidden when no purchase actions.
- ROAS tile rendered when `omni_purchase` present.
- Dual-axis CTR + CPM series render (sr-only accessible table probe).
- "Spend vs. CPM" heading when ROAS unavailable.
- Records-count heading confirms VizDataTable replaced tanstack-table usage.

## Targeted vitest output

```
 RUN  v3.2.4 /Users/thristannewman/ADinsights/frontend

 ✓ src/lib/metaAggregates.test.ts (10 tests) 21ms
 ✓ src/routes/__tests__/MetaAccountsPage.test.tsx (6 tests) 677ms
 ✓ src/routes/__tests__/MetaInsightsDashboardPage.test.tsx (7 tests) 631ms

 Test Files  3 passed (3)
      Tests  23 passed (23)
```

## Full suite output (regression check)

```
 Test Files  114 passed (114)
      Tests  629 passed (629)
```

## Lint output

```
> adinsights-frontend@0.1.0 lint
> eslint .

(no warnings / no errors)
```

## Build output

```
dist/assets/MetaAccountsPage-DhKxrHvu.js                 12.38 kB │ gzip:  3.85 kB
dist/assets/MetaInsightsDashboardPage-vFaI_1Uq.js        22.69 kB │ gzip:  7.87 kB
…
✓ built in 5.16s
```

## Design deviations / notes

1. **Accounts page does not set `filters.level='account'`.** The architect's prose "Call `loadInsights({level:'account', accountId:''})` when page mounts" would require either (a) mutating the shared `filters.level` (leaks into the Insights page) or (b) adding a parameterized variant of `loadInsights` (prohibited store-shape change). Chose the minimally-invasive path: dispatch `loadInsights()` with current filters; aggregation helpers work on whatever rows arrive. All data transforms (`groupSpendByDateAccount`, `sumInsights`, `spendByObjective`) are level-agnostic.
2. **BubbleScatter shape encoding**: architect §4.2 calls for shape-by-objective when `filters.accountId === ''`. Objective is NOT on `MetaInsightRecord`, and the per-row campaign_external_id join → objective is unreliable (non-campaign-level rows may not carry `campaign_external_id`). Simplified to `triangle` when filtered, `circle` otherwise. Accessible.
3. **TypeScript narrowness on VizDataTable columns**: `createColumnHelper(...).accessor(...)` produces `AccessorKeyColumnDef<T, V>` which is not assignable to `ColumnDef<T, unknown>` (contravariant generic on `footer`). Swapped to inline `ColumnDef<T, unknown>` objects with `accessorKey` literals. No behavioral change.
4. **`rows.length ? kpis.X : null` pattern** in KpiTile values: renders the no-data dash when insights slice is empty so the strip doesn't flash a zero spend of $0.00. Matches the architect's graceful-degrade intent.
5. **Legacy components (`TrendChart`, `KPIGrid`, etc.) left alone**, per architect boundaries.

## Status

**GREEN.** All acceptance gates met:

- Targeted vitest: 23/23 passed.
- Full vitest suite: 629/629 passed (no regressions).
- ESLint: 0 warnings / 0 errors.
- `tsc -p tsconfig.build.json && vite build`: successful.
- Dual-axis TrendLine: verified supported, used directly.
- ROAS: conditional-derive implemented with CPM fallback on bubble.
- All §6.1 / §6.2 test assertions in place; Phase 1A contract tests preserved.
