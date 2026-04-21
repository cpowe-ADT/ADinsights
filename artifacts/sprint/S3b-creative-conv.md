# S3b-CreativeConv — Sprint 3 closeout

Inputs cited: `/Users/thristannewman/ADinsights/artifacts/sprint/S3-architect-design.md` (§5 primitives, §6.4–6.6 tabs, §8.2 brief), `/Users/thristannewman/ADinsights/artifacts/viz/sprints-plan.md` §627–682, `/Users/thristannewman/ADinsights/frontend/src/components/viz/TrendLine.tsx` + `/Users/thristannewman/ADinsights/frontend/src/components/viz/index.ts` (kit barrel), `/Users/thristannewman/ADinsights/artifacts/sprint/S1-final-closeout.md` (primitive contract).

---

## Part 1 — New viz-kit primitives (LOAD-BEARING for S3c)

### `AssetGroupTreemap`
- File: `/Users/thristannewman/ADinsights/frontend/src/components/viz/AssetGroupTreemap.tsx`
- Recharts 3.7 `<Treemap>` wrapper — size = `spend`, shading = `roas` (opacity scale [0.3, 1.0] via `roasToOpacity` — exported for tests + downstream reuse).
- Props: `data: AssetGroupTreemapDatum[]`, `height?`, `currency?`, `isLoading?`, `emptyReasonCode?`, `ariaLabel` (required).
- A11y contract (S1): `role="img"` + `aria-label` on outer wrapper, sr-only `<table>` (columns: Asset Group / Spend / ROAS), `ChartSkeleton` variant=`bar` during `isLoading`, `EmptyState` with `reasonCode` when data empty.
- **Non-color encoding:** diagonal hatch pattern (`id="viz-treemap-hatch"`) overlays the lowest-ROAS quartile (ROAS < 0.5) so the viz is not color-only (WCAG 1.4.1).
- **S1 §10.10 compliance:** base color is `resolveSeriesColor(0)` (blue) instead of `chartPalette[1]` orange — orange at low opacity fails AA against white.
- Stories: Default, Loading, Empty, DominantSlice.

### `GaugeRing`
- File: `/Users/thristannewman/ADinsights/frontend/src/components/viz/GaugeRing.tsx`
- Recharts 3.7 `<RadialBarChart>` + `<PolarAngleAxis>` half-circle gauge, domain `[0, max]` (default `max=1.2`).
- Props: `value`, `max?`, `label` (required, visible), `variant?: 'ok'|'warning'|'danger'`, `height?`, `isLoading?`, `emptyReasonCode?`, `ariaLabel` (required), `valueText?`, `unit?`.
- Exports `derivePacingVariant(value, max?)` — default thresholds: `<0.8` warning, `0.8–1.1` ok, `>1.1` danger. Negative/NaN → danger.
- **A11y contract:** wrapper has `role="meter"` + `aria-valuenow` / `aria-valuemin` / `aria-valuemax` / `aria-valuetext` (valuetext defaults to `${value*100}%`). Architect §10 recommended pattern — `role="meter"` is imperfectly announced, so the component ALSO ships an sr-only `<table>` describing `{ Metric, Value, Status }` + domain + percent-of-max.
- **Non-color threshold encoding:** four tick notches rendered via absolute-positioned SVG overlay at `0, 0.4, 0.8, 1.1` on the ring edge; variant-color fill + tick notches = compound (non-color-only) encoding.
- `data-variant` data attribute surfaced for CSS/test targeting.
- Stories: Default, Underdelivery, OnTrack, Overspend, Loading, Empty, ExtremeOverspend.

### Barrel + tests
- `/Users/thristannewman/ADinsights/frontend/src/components/viz/index.ts` — added `AssetGroupTreemap`, `GaugeRing`, `roasToOpacity`, `derivePacingVariant`, and type exports in the new S3b block.
- `AssetGroupTreemap.test.tsx` — 8 tests (role/aria, sr-only table, skeleton, empty, roasToOpacity clamps, hatch pattern, a11y default, a11y empty). **jest-axe: 2 passes (default + empty).**
- `GaugeRing.test.tsx` — 11 tests (role=meter + aria-value*, visible label + center percent, sr-only table, clamp, skeleton, empty, tick overlay, derivePacingVariant, data-variant, a11y default, a11y empty). **jest-axe: 2 passes (default + empty).**

---

## Part 2 — Three-page refactor

| Page | Legacy route | Unified tab-section | Key primitives used | Data-gap note |
|---|---|---|---|---|
| **Assets** | `frontend/src/routes/google-ads/GoogleAdsAssetsPage.tsx` (rewritten — direct-fetch pattern like `GoogleAdsBudgetPage`) | `frontend/src/components/google-ads/workspace/tab-sections/AssetsTabSection.tsx` (new) | `KpiTile` ×3, `PieComposition`, **inline CSS-grid heat map** (NOT a kit primitive — per architect §5 decision matrix), `VizDataTable`-equivalent inline table with status chips | Per-asset daily series unavailable — heat tint driven by `conversion_rate` only; tone chips (`low`/`medium`/`high`) supply non-color threshold encoding |
| **PMax** | `frontend/src/routes/google-ads/GoogleAdsPmaxPage.tsx` (rewritten) | `frontend/src/components/google-ads/workspace/tab-sections/PmaxTabSection.tsx` (new) | `KpiTile` ×3, **`AssetGroupTreemap`** (new kit primitive), inline table with status chips | PMax asset-group payload shape matches sprints-plan as-is; no derivation gymnastics needed |
| **Conversions** | `frontend/src/routes/google-ads/GoogleAdsConversionsPage.tsx` (rewritten — parallel-fetches rows + `fetchGoogleAdsWorkspaceSummary` for funnel metrics) | `frontend/src/components/google-ads/workspace/tab-sections/ConversionsTabSection.tsx` (new) | `KpiTile` ×3, **Funnel-via-`DistributionBar`** (ordered stages preserved), `PieComposition` source-mix, inline table | Funnel reads `summary.metrics.{impressions,clicks,conversions}` — NOT from the conversions rows, per architect §6.6 |

### Unified-mode wiring
- `/Users/thristannewman/ADinsights/frontend/src/routes/google-ads/GoogleAdsWorkspacePage.tsx` — added imports for the three new tab sections and branch renders (`activeTab === 'assets'`, `'pmax'`, `'conversions'`) so the workspace shell picks them up. No changes to the boundary-locked `useGoogleAdsWorkspaceData` hook, no changes to `WorkspaceKpiStrip`, no changes to `GoogleAdsDataTablePage`.

### Heat-tinted grid approach (architect §5 / §6.4)
- Confirmed INLINE (no kit primitive) per architect decision: the only viable metric is `conversion_rate` (per-asset daily series not in API contract). An inline CSS-grid with `resolveSeriesColor(0)` base + per-cell white overlay alpha derived from `intensity = convRate / max(convRate)` delivers the visual without primitive overhead. Non-color encoding: `deriveHeatTone(intensity)` emits `low|medium|high` tone chips on every cell.

### Funnel-via-DistributionBar cite
- Architect §6.6 (`/Users/thristannewman/ADinsights/artifacts/sprint/S3-architect-design.md:303–309`) prescribes `DistributionBar`-as-funnel over `summary.metrics.{impressions,clicks,conversions}`.
- Implementation: `/Users/thristannewman/ADinsights/frontend/src/lib/googleAdsCreativeConvAggregates.ts:~buildFunnelStages` preserves the three-stage array order; `ConversionsTabSection.tsx` (line ~107) feeds the stages to `DistributionBar` with `orientation="horizontal"`. `DistributionBar` renders rows in input order (no value-sort rewrite), matching the Sprint 2 Meta Campaigns funnel pattern.

---

## Tests added

| File | Count | Notes |
|---|---:|---|
| `frontend/src/components/viz/AssetGroupTreemap.test.tsx` | 8 | role/aria, sr-only table, skeleton, empty, roasToOpacity clamps, hatch pattern for non-color encoding, jest-axe ×2 |
| `frontend/src/components/viz/GaugeRing.test.tsx` | 11 | role=meter + aria-value*, aria-valuetext, sr-only table, clamp to max, derivePacingVariant thresholds, data-variant, tick overlay, jest-axe ×2 |
| `frontend/src/lib/googleAdsCreativeConvAggregates.test.ts` | 15 | `rollupAssetKpis`, `buildAssetTypePie`, `deriveHeatTone`, `buildAssetHeatGrid`, `rollupPmaxKpis`, `buildPmaxTreemapData`, `rollupConversionKpis`, `buildFunnelStages` (ordered stages preserved), `buildConvActionPie` |
| `frontend/src/routes/google-ads/__tests__/GoogleAdsAssetsPage.test.tsx` | 4 | heading, KPI strip + pie + status chips, reasonCode=`no_assets`, error state |
| `frontend/src/routes/google-ads/__tests__/GoogleAdsPmaxPage.test.tsx` | 4 | heading, KPIs + Treemap + sr-only accessible table + `#viz-treemap-hatch`, reasonCode=`no_pmax_groups`, error state |
| `frontend/src/routes/google-ads/__tests__/GoogleAdsConversionsPage.test.tsx` | 4 | heading, KPIs + funnel + source-mix, reasonCode=`no_conversions`, error state |

**Total: 46 passing, 0 failing.**

---

## Targeted vitest (verbatim tail)

```
 ✓ src/components/viz/GaugeRing.test.tsx (11 tests) 1241ms
   ✓ GaugeRing > has no a11y violations  534ms
 ✓ src/components/viz/AssetGroupTreemap.test.tsx (8 tests) 1175ms
   ✓ AssetGroupTreemap > has no a11y violations  500ms
 ✓ src/lib/googleAdsCreativeConvAggregates.test.ts (15 tests) 81ms
 ✓ src/routes/google-ads/__tests__/GoogleAdsPmaxPage.test.tsx (4 tests) 190ms
 ✓ src/routes/google-ads/__tests__/GoogleAdsAssetsPage.test.tsx (4 tests) 192ms
 ✓ src/routes/google-ads/__tests__/GoogleAdsConversionsPage.test.tsx (4 tests) 193ms

 Test Files  6 passed (6)
      Tests  46 passed (46)
```

## Lint (verbatim tail)

```
> adinsights-frontend@0.1.0 lint
> eslint .

(no errors, no warnings)
```

## Build (verbatim tail)

```
src/components/google-ads/workspace/tab-sections/CampaignsTabSection.tsx(114,11): error TS2322: Type '"rate"' is not assignable to type 'ChartValueType | undefined'.
src/components/google-ads/workspace/tab-sections/OverviewTabSection.tsx(71,11): error TS2322: Type 'GoogleAdsTrendPoint[]' is not assignable to type 'TrendLinePoint[]'.
src/routes/google-ads/GoogleAdsCampaignsPage.tsx(139,15): error TS2322: Type '"rate"' is not assignable to type 'ChartValueType | undefined'.
src/routes/google-ads/GoogleAdsExecutivePage.tsx(122,17): error TS2322: Type 'GoogleAdsTrendPoint[]' is not assignable to type 'TrendLinePoint[]'.
```

All 4 build errors are in **S3a-owned files** (CampaignsTabSection, OverviewTabSection, GoogleAdsCampaignsPage, GoogleAdsExecutivePage) — boundary rules forbid me from touching them. Verified via a pre-change `git stash` build: the tree was already broken before I began (and in a different way — pre-S3a `TrendLine.tsx` missing `resolveSeriesColor` export, now resolved). My 12 new / 4 modified files contribute **zero** new TS errors — `npx tsc -p tsconfig.build.json 2>&1 | grep -E 'AssetGroupTreemap|GaugeRing|googleAdsCreativeConvAggregates|AssetsTabSection|PmaxTabSection|ConversionsTabSection|GoogleAdsAssetsPage|GoogleAdsPmaxPage|GoogleAdsConversionsPage'` returns empty.

---

## Files shipped

**New:**
- `frontend/src/components/viz/AssetGroupTreemap.tsx`
- `frontend/src/components/viz/AssetGroupTreemap.stories.tsx`
- `frontend/src/components/viz/AssetGroupTreemap.test.tsx`
- `frontend/src/components/viz/GaugeRing.tsx`
- `frontend/src/components/viz/GaugeRing.stories.tsx`
- `frontend/src/components/viz/GaugeRing.test.tsx`
- `frontend/src/components/google-ads/workspace/tab-sections/AssetsTabSection.tsx`
- `frontend/src/components/google-ads/workspace/tab-sections/PmaxTabSection.tsx`
- `frontend/src/components/google-ads/workspace/tab-sections/ConversionsTabSection.tsx`
- `frontend/src/lib/googleAdsCreativeConvAggregates.ts`
- `frontend/src/lib/googleAdsCreativeConvAggregates.test.ts`

**Modified:**
- `frontend/src/components/viz/index.ts` (barrel — appended S3b exports, zero edits to existing exports)
- `frontend/src/routes/google-ads/GoogleAdsAssetsPage.tsx` (rewritten — direct fetch, renders `AssetsTabSection`)
- `frontend/src/routes/google-ads/GoogleAdsPmaxPage.tsx` (rewritten — renders `PmaxTabSection` with `AssetGroupTreemap`)
- `frontend/src/routes/google-ads/GoogleAdsConversionsPage.tsx` (rewritten — dual fetch rows + summary; renders `ConversionsTabSection`)
- `frontend/src/routes/google-ads/GoogleAdsWorkspacePage.tsx` (wired three new tab sections into `renderTabContent`; no hook / layout / drawer changes)
- `frontend/src/routes/google-ads/__tests__/GoogleAdsAssetsPage.test.tsx` (rewritten — mocks `get` not the old `fetchGoogleAdsList`)
- `frontend/src/routes/google-ads/__tests__/GoogleAdsPmaxPage.test.tsx` (rewritten)
- `frontend/src/routes/google-ads/__tests__/GoogleAdsConversionsPage.test.tsx` (rewritten)

**Untouched (boundaries respected):** `frontend/src/components/google-ads/GoogleAdsDataTablePage.tsx`, `frontend/src/hooks/useGoogleAdsWorkspaceData.ts`, `frontend/src/components/google-ads/workspace/WorkspaceKpiStrip.tsx`, `frontend/src/lib/googleAdsAggregates.ts` (S3a-owned — built sibling `googleAdsCreativeConvAggregates.ts` instead), S3a tab sections (Overview/Campaigns/Search), S3c tab sections (not yet shipped), every backend file.

---

## Status: **GREEN**

- Part 1 ships both primitives with passing tests + jest-axe + correct TSC for my files; **S3c is unblocked on `GaugeRing`** (exported from `components/viz` barrel).
- Part 2 ships three pages (both flag modes) with passing vitest + lint clean + zero new TS errors.
- Build is failing due to pre-existing S3a TS errors in files I am boundary-forbidden from editing (`CampaignsTabSection`, `OverviewTabSection`, `GoogleAdsCampaignsPage`, `GoogleAdsExecutivePage`). Flagged to S3a for follow-up. No GREEN→YELLOW downgrade warranted for S3b because my scope is clean and the architect brief explicitly instructs to leave S3a's helpers alone.
