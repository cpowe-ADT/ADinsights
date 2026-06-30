# S1c-StoriesAndA11y — Fix Report

**Inputs cited:** `/Users/thristannewman/ADinsights/artifacts/sprint/S1-architect-design.md` (§6 Storybook pattern L274–347, §7 Unit + a11y test pattern L351–427), `/Users/thristannewman/ADinsights/artifacts/sprint/S1a-chart-primitives.md`, `/Users/thristannewman/ADinsights/artifacts/sprint/S1b-table-and-kpi.md`, `/Users/thristannewman/ADinsights/frontend/src/components/viz/index.ts`, `/Users/thristannewman/ADinsights/frontend/src/components/DataTable.stories.tsx`, `/Users/thristannewman/ADinsights/frontend/src/components/FilterBar.stories.tsx`, `/Users/thristannewman/ADinsights/frontend/src/components/TenantSwitcher.test.tsx`.

## Status: GREEN

All 10 primitives have Storybook stories + jest-axe tests. `@storybook/addon-a11y@8.6.14` installed and wired. Targeted vitest run: **69/69 passing**. Lint clean. Frontend `npm run build` succeeds. `npm run storybook:build` succeeds (includes the axe addon bundle).

## Files Created

| #   | File                                                            | Kind                                    |
| --- | --------------------------------------------------------------- | --------------------------------------- |
| 1   | `frontend/src/components/viz/KpiTile.stories.tsx`               | Storybook                               |
| 2   | `frontend/src/components/viz/KpiTile.test.tsx`                  | vitest + jest-axe                       |
| 3   | `frontend/src/components/viz/TrendLine.stories.tsx`             | Storybook                               |
| 4   | `frontend/src/components/viz/TrendLine.test.tsx`                | vitest + jest-axe                       |
| 5   | `frontend/src/components/viz/Sparkline.stories.tsx`             | Storybook                               |
| 6   | `frontend/src/components/viz/Sparkline.test.tsx`                | vitest + jest-axe                       |
| 7   | `frontend/src/components/viz/DistributionBar.stories.tsx`       | Storybook                               |
| 8   | `frontend/src/components/viz/DistributionBar.test.tsx`          | vitest + jest-axe                       |
| 9   | `frontend/src/components/viz/BubbleScatter.stories.tsx`         | Storybook                               |
| 10  | `frontend/src/components/viz/BubbleScatter.test.tsx`            | vitest + jest-axe                       |
| 11  | `frontend/src/components/viz/PieComposition.stories.tsx`        | Storybook                               |
| 12  | `frontend/src/components/viz/PieComposition.test.tsx`           | vitest + jest-axe                       |
| 13  | `frontend/src/components/viz/DataTable.stories.tsx`             | Storybook                               |
| 14  | `frontend/src/components/viz/DataTable.test.tsx`                | vitest + jest-axe                       |
| 15  | `frontend/src/components/viz/AccessibleTableToggle.stories.tsx` | Storybook                               |
| 16  | `frontend/src/components/viz/AccessibleTableToggle.test.tsx`    | vitest + jest-axe                       |
| 17  | `frontend/src/components/viz/ChartSkeleton.stories.tsx`         | Storybook                               |
| 18  | `frontend/src/components/viz/ChartSkeleton.test.tsx`            | vitest + jest-axe                       |
| 19  | `frontend/src/components/viz/EmptyState.stories.tsx`            | Storybook (viz-kit)                     |
| 20  | `frontend/src/components/viz/EmptyState.test.tsx`               | vitest + jest-axe                       |
| 21  | `frontend/src/lib/csvExport.test.ts`                            | vitest (torture cases + download smoke) |

Note: `PeerAvgLine` is intentionally skipped per brief; it's tested transitively through `TrendLine.WithPeerAvg` + `TrendLine.test.tsx` (which verifies the `Peer avg` column in the sr-only table when `peerData` is supplied). The viz-kit barrel's 11th export is therefore not directly storied, matching the brief's guidance.

## Files Modified

| File                          | Edit                                                                                          |
| ----------------------------- | --------------------------------------------------------------------------------------------- |
| `frontend/package.json`       | Added `"@storybook/addon-a11y": "8.6.14"` (pinned, matching the essentials/interactions pin). |
| `frontend/.storybook/main.ts` | Appended `'@storybook/addon-a11y'` to the `addons` array.                                     |
| `frontend/package-lock.json`  | npm-managed churn from the addon install.                                                     |

## addon-a11y Install Result

**Installed at 8.6.14 (exact pin).** Verified with `npm ls @storybook/addon-a11y` → `@storybook/addon-a11y@8.6.14`. Added to `.storybook/main.ts` addons array. Confirmed Storybook builds successfully with the addon in place (`npm run storybook:build` emits `axe-D_imH7Hx.js` 572.61 kB chunk, proving the rule engine is bundled).

## Per-primitive story coverage

Every required story from the architect's per-primitive table is present. Spot-check:

- `KpiTile`: Default, Loading, Empty, WithDeltaUp, WithDeltaDown, Faded, DarkTheme (7)
- `TrendLine`: Default, Loading, Empty, SingleSeries, MultiSeries, DualAxis, WithPeerAvg, DarkTheme (8; `StackedArea` deferred — primitive does not currently expose the `variant="stacked-area"` prop in the shipped S1a implementation, so the story would not render anything new)
- `Sparkline`: Default, Flat, Rising, Falling, DarkTheme (5)
- `DistributionBar`: Default, Loading, Empty, Horizontal, Vertical, WithPercent, DarkTheme (7)
- `BubbleScatter`: Default, Loading, Empty, Clustered, WithShapes, DarkTheme (6)
- `PieComposition`: Default, Loading, Empty, Donut, Pie, WithCenterLabel, DarkTheme (7)
- `DataTable`: Default, Loading, Empty, WithCsvExport, RowClick, LongList, DarkTheme (7)
- `EmptyState` (viz): NoAccounts, NoData, AdapterError, NoDataForScope (4)
- `ChartSkeleton`: Line, Bar, Pie, Table, KpiStrip, Kpi, Sparkline, Bubble (8)
- `AccessibleTableToggle`: Default, DefaultTable, WithKeyboardFocus (3)

## Targeted vitest results (verbatim tail)

```
$ npx vitest run src/components/viz src/lib/csvExport.test.ts

 ✓ src/lib/csvExport.test.ts (10 tests) 8ms
 ✓ src/components/viz/KpiTile.test.tsx (8 tests) 1125ms
 ✓ src/components/viz/AccessibleTableToggle.test.tsx (7 tests) 1830ms
 ✓ src/components/viz/DataTable.test.tsx (5 tests) 191ms
 ✓ src/components/viz/Sparkline.test.tsx (5 tests) 1371ms
 ✓ src/components/viz/PieComposition.test.tsx (6 tests) 1593ms
 ✓ src/components/viz/BubbleScatter.test.tsx (6 tests) 1786ms
 ✓ src/components/viz/DistributionBar.test.tsx (7 tests) 1904ms
 ✓ src/components/viz/TrendLine.test.tsx (7 tests) 1863ms
 ✓ src/components/viz/EmptyState.test.tsx (4 tests) 250ms
 ✓ src/components/viz/ChartSkeleton.test.tsx (4 tests) 175ms

 Test Files  11 passed (11)
      Tests  69 passed (69)
   Duration  5.23s
```

**Total: 11 files, 69 tests, 0 failures.** Every primitive has at least one `expect(await axe(container)).toHaveNoViolations()` assertion (most have two — one for the happy path and one for the empty/loading variant).

### Per-primitive sanity coverage honored

- `KpiTile`: value rendered, delta has `aria-label` (increased/decreased), loading skeleton renders with `aria-busy="true"`, `reasonCode` propagated as `data-reason-code`.
- `DataTable`: caption rendered, `captionHidden` → `.visually-hidden` class, CSV button present only when `csvFilename` set, CSV click creates a Blob + revokes the URL, blob text contains header + row content.
- `AccessibleTableToggle`: click / Enter / Space each flip `aria-pressed`; inactive node has `hidden` + `aria-hidden="true"`; `defaultView="table"` starts pressed.
- `TrendLine` / `Sparkline` / `DistributionBar` / `BubbleScatter` / `PieComposition`: chart root has `role="img"` + `aria-label`, hidden `<table class="sr-only">` has one `<tbody><tr>` per data point, empty state carries the requested `data-reason-code`, `isLoading` renders `.viz-chart-skeleton`.
- `ChartSkeleton`: root has `role="presentation"` + `aria-hidden="true"`, height honored on line variant, kpi-strip renders 4 placeholder cells, table variant renders `rows+1` skeletons.
- `EmptyState`: reason code rendered as `data-reason-code`; absent when prop omitted; primary action click fires handler.

## CSV torture test results

All required torture cases from the S1b report pass in `src/lib/csvExport.test.ts`:

| Input                                                    | Expected                     | Status |
| -------------------------------------------------------- | ---------------------------- | ------ |
| `"Hello, world"` (string literally contains quote chars) | `"""Hello, world"""`         | ✓      |
| `Line1\nLine2` (multi-line)                              | `"Line1\nLine2"`             | ✓      |
| `=SUM(A1:A10)`                                           | `'=SUM(A1:A10)`              | ✓      |
| `@attacker`                                              | `'@attacker`                 | ✓      |
| `+cmd`, `-whatever`                                      | `'+cmd`, `'-whatever`        | ✓      |
| `null` / `undefined`                                     | empty string                 | ✓      |
| Mixed torture row                                        | correct RFC-4180 + hardening | ✓      |

`downloadCsv` smoke test stubs `URL.createObjectURL` / `URL.revokeObjectURL`, spies on `HTMLAnchorElement.prototype.click`, and asserts the Blob MIME type contains `text/csv`. A harmless "Not implemented: navigation" warning appears from jsdom on anchor `.click()` — this is expected in JSDOM and does not fail the test (jsdom's dummy navigation attempt for the synthetic click). Recommend the parent sprint's Definition-of-done accepts this as a known JSDOM limitation.

## Lint + build results

```
$ npm run lint
> adinsights-frontend@0.1.0 lint
> eslint .
(clean exit — no output, no warnings, no errors)
```

```
$ npm run build
tsc -p tsconfig.build.json && vite build
...
✓ built in 4.00s
```

```
$ npm run storybook:build
...
✓ built in 18.26s
info => Preview built (23 s)
info => Output directory: /Users/thristannewman/ADinsights/frontend/storybook-static
```

## A11y violations observed

**Zero violations across all 11 test files.** Every `expect(await axe(container)).toHaveNoViolations()` assertion passes. Notable positives:

1. All chart primitives render a hidden-but-present `<table class="sr-only">` with `<caption>` + column scope, so axe does not flag the SVG `role="img"` as a contentless image.
2. `AccessibleTableToggle` passes with the canonical `hidden` + `aria-hidden="true"` pattern on the inactive branch. Axe accepts it as non-interactive content.
3. `EmptyState` carries `role="status"` + `aria-live="polite"` + `data-reason-code` — axe does not flag the status region when the icon is `aria-hidden="true"`.
4. `KpiTile` passes with `aria-label="{label}: no data"` on the value node when `value === null` and `aria-label="{direction} by {change}"` on the delta span.

Nothing in S1a/S1b needs a follow-up for a11y. The only spec-nice-to-have not yet in the repo is the `prefers-reduced-motion` hook (S1a's report flagged this as deferred to S1c or Sprint 2). Since the architect §5.3 explicitly allows deferring it to a shared hook, and no axe rule covers it, leaving it for Sprint 2.

## Known JSDOM noise

The `DataTable.test.tsx` CSV click test and the `csvExport.test.ts` `downloadCsv` smoke emit a single `stderr` line each about "Not implemented: navigation (except hash changes)" — this is jsdom warning that it does not implement full anchor-element navigation when `.click()` is synthesized on an anchor with `href`. The tests assert the stubs (`createObjectURL`, `revokeObjectURL`, `HTMLAnchorElement.prototype.click` spy) and the Blob content, which is the correct behavior contract. The warning is **not** a test failure and matches the pattern already used elsewhere in the codebase.

## Boundary compliance

- Zero edits to any `frontend/src/components/viz/*.tsx` primitive file (S1a/S1b owned).
- Zero edits to any existing `*.stories.tsx` or `*.test.tsx` file.
- Zero edits to `viz-tokens.css` or `chartTheme.ts`.
- The only three touched pre-existing files are `frontend/package.json`, `frontend/package-lock.json`, and `frontend/.storybook/main.ts` — exactly the files listed as owned by S1c in the architect's §8.3 work split.

## Handoff / Sprint 2 notes

1. **`TrendLine.StackedArea` story**: the shipped `TrendLine` interface does not yet expose a `variant` prop for stacked-area. If a future sprint adds it, the story file should get a new `StackedArea` entry; the test file should add a corresponding `<Area>` element presence check.
2. **`prefers-reduced-motion`**: no polyfill added in `setupTests.ts`. None of the delivered primitives call `window.matchMedia` today, so the JSDOM gap is moot; if Sprint 2 adds a shared `useReducedMotion()` hook, ship the polyfill with it.
3. **Coverage gate**: targeted run excluded (per architect §10.10 Recharts-SVG coverage inflation note). All 69 tests pass; fully landing Vitest coverage ≥ 80% per primitive is a Sprint 2 task when domain wrappers migrate to these primitives and exercise more branches.
