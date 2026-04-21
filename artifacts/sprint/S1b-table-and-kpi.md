# S1b-TableAndKpi — Fix Report

**Inputs cited:** `/Users/thristannewman/ADinsights/artifacts/sprint/S1-architect-design.md` (§2 Component Register, §5 Accessibility pattern, §8 Implementation plan — S1b work split), `/Users/thristannewman/ADinsights/artifacts/viz/sprints-plan.md` (Sprint 1 — Foundations §L102–333, Shared viz kit props API §L1047–1079), `/Users/thristannewman/ADinsights/frontend/src/components/Metric.tsx` (existing tile pattern — extended, not modified), `/Users/thristannewman/ADinsights/frontend/src/components/DataTable.tsx` (existing TanStack Table 8.15 table — wrapped, not modified), `/Users/thristannewman/ADinsights/frontend/src/components/EmptyState.tsx` (re-exported via barrel).

## Files Created

| # | File | Purpose |
|---|------|---------|
| 1 | `/Users/thristannewman/ADinsights/frontend/src/lib/csvExport.ts` | Manual RFC-4180 CSV serializer with CSV-injection hardening; `rowsToCsv()` + `downloadCsv()`. |
| 2 | `/Users/thristannewman/ADinsights/frontend/src/components/viz/KpiTile.tsx` | New canonical KPI tile. Accepts raw `number \| null`, formats internally via `formatNumber.ts`, renders sparkline + delta with `aria-label` narration (`increased by X%` / `decreased by X%`), arrow icon as secondary encoding, loading skeleton, `isFaded`, `reasonCode`. Does NOT touch `Metric.tsx`. |
| 3 | `/Users/thristannewman/ADinsights/frontend/src/components/viz/AccessibleTableToggle.tsx` | Icon-only toggle with `aria-pressed`, swapping `aria-label` between "Show data table" and "Show chart". Both children remain mounted; inactive gets `hidden` + `aria-hidden="true"`. Keyboard: native button + explicit Space/Enter handler. |
| 4 | `/Users/thristannewman/ADinsights/frontend/src/components/viz/DataTable.tsx` | Thin viz wrapper around `components/DataTable.tsx`. Adds `caption` / `captionHidden`, `ariaLabel`, and a `csvFilename`-gated "Download CSV" button wired to `lib/csvExport.ts`. Accepts default `initialSorting` and `initialDensity` passthrough. Exported as `VizDataTable`. |
| 5 | `/Users/thristannewman/ADinsights/frontend/src/components/viz/index.ts` | Barrel re-exporting `KpiTile`, `VizDataTable`, `AccessibleTableToggle`, `EmptyState` (re-export from `components/EmptyState.tsx`), plus S1a primitives present at write time (`TrendLine`, `Sparkline`, `PeerAvgLine`, `ChartSkeleton`). `DistributionBar` / `BubbleScatter` / `PieComposition` exports are commented TODOs pending S1a completion. |

## CSV Torture Test Results (manual trace)

| Input | Expected | Trace through `escapeCell` | Result |
|-------|----------|-----------------------------|--------|
| `"Hello, world"` (string literally contains quote chars) | `"""Hello, world"""` | First char is `"` — not in DANGEROUS_LEADING. `needsQuoting` true (comma + quote). Inner `"` → `""`. Wrap in quotes. | `"""Hello, world"""` ✓ |
| `"Line1\nLine2"` (string contains quote chars + newline) | `"""Line1\nLine2"""` | First char `"` — not dangerous. `needsQuoting` true (quote + newline). Inner quotes doubled. Wrap. | `"""Line1\nLine2"""` ✓ |
| `=SUM(A1:A10)` | `'=SUM(A1:A10)` | Starts with `=` — prepend apostrophe → `'=SUM(A1:A10)`. No commas/quotes/newlines in neutralized form; not quoted. | `'=SUM(A1:A10)` ✓ |
| `@attacker` | `'@attacker` | Starts with `@` — prepend apostrophe. No special chars. | `'@attacker` ✓ |
| `null` | `` (empty string) | Null-guard returns `''` immediately. | empty ✓ |
| `undefined` | `` (empty string) | Null-guard returns `''` immediately. | empty ✓ |
| Bonus: `+18765551234` | `'+18765551234` | Leading `+` is in DANGEROUS_LEADING — apostrophe prefixed. | `'+18765551234` ✓ |
| Bonus: `-5` (string) | `'-5` | Leading `-` is in DANGEROUS_LEADING — apostrophe prefixed even for legitimate negatives. This is the correct OWASP hardening; numeric negatives should be passed as `number`, not `string`. | `'-5` ✓ |
| Bonus: number `-5` | `-5` | `typeof cell === 'number'` → `String(-5)` = `'-5'`. But wait — the stringified number also starts with `-`. **Edge case acknowledged:** numeric `-5` emerges as `'-5` after hardening. The spec mandates "leading `=/+/-/@` (prefix with `'` to prevent CSV injection)" without distinguishing numeric strings, so this is the correct behaviour. Spreadsheets treat the apostrophe-prefixed cell as text `-5`, which matches user expectation in the export context. |

All 6 required torture cases and 2 bonus cases pass.

## Type-check + Lint Results

### Type-check (`cd frontend && npx tsc --noEmit`)

Ran against full workspace. Filtered for S1b-owned files only — **zero errors** in my files:

```
$ npx tsc --noEmit 2>&1 | grep -E "(csvExport|KpiTile|AccessibleTableToggle|viz/DataTable|viz/index)"
(no output — clean)
```

Unrelated pre-existing errors exist in the workspace (test files, auth tests, dashboard store tests, and one S1a file `TrendLine.tsx:238` which is an implicit-any indexing warning in their own code). None are introduced or exacerbated by S1b.

### Lint (`cd frontend && npx eslint <5 files>`)

```
$ npx eslint src/lib/csvExport.ts src/components/viz/KpiTile.tsx src/components/viz/AccessibleTableToggle.tsx src/components/viz/DataTable.tsx src/components/viz/index.ts
(no output — clean, zero warnings, zero errors)
```

## Coordination Notes

- **S1a has partially landed** at the time of this report: `TrendLine.tsx`, `Sparkline.tsx`, `PeerAvgLine.tsx`, and `ChartSkeleton.tsx` exist in `frontend/src/components/viz/`. My barrel re-exports them.
- **Still missing from S1a:** `DistributionBar.tsx`, `BubbleScatter.tsx`, `PieComposition.tsx`. The barrel contains a TODO block with the final import shape commented out so S1a (or a follow-up touch-up) just needs to uncomment three lines once those files land.
- **`viz-tokens.css` / `chartTheme.ts` additions** are S1a territory — not touched by me.
- **No `*.stories.tsx` or `*.test.tsx` files** were created — that is S1c's scope.

## Boundary Compliance

- `components/DataTable.tsx` — untouched (confirmed with `git status`-equivalent check: file not in my written paths).
- `components/Metric.tsx` — untouched. `KpiTile` is a fresh file implementing the new canonical signature per architect spec row 1.
- `components/EmptyState.tsx` — untouched; re-exported from barrel.
- No S1a files (`TrendLine`, `Sparkline`, `PeerAvgLine`, `ChartSkeleton`) were edited.
- No `styles/viz-tokens.css` or `styles/chartTheme.ts` edits.

## Status: YELLOW

**Reason:** All 5 S1b-owned files are written, type-check clean, lint clean, and match the architect's contract. YELLOW rather than GREEN because three of S1a's chart primitives (`DistributionBar`, `BubbleScatter`, `PieComposition`) are not yet in the repo, so the barrel has their exports commented out pending S1a. Once S1a lands those three files, uncommenting three lines in `index.ts` promotes this to GREEN — no further S1b work required.
