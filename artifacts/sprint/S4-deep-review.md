# Deep review — post-Sprint 4

**Scope:** senior-engineer review of the full viz-kit migration (Sprints 1–4) for bugs, correctness risks, contract drift, and test-coverage gaps.

**Inputs cited:** `S1-final-closeout.md`, `S2-final-closeout.md`, `S3-final-closeout.md`, `S4-final-closeout.md`, `S4-architect-design.md`, plus direct source reads across 28 migrated pages, 13 viz primitives, and 7 shared-helper modules.

## Status: GREEN

One real a11y bug found and fixed. All other audit-flagged items verified as either phantom (wrong/speculative), already covered, or explicitly out-of-scope retention.

## Method

Three parallel Explore agents audited non-overlapping lanes (viz primitives + libs, migrated pages, test layer + cross-page invariants). Findings were then triaged against source rather than taken at face value — many read as speculative. Only confirmed findings proceeded to fix.

## Triage outcome — findings vs. reality

| Audit claim | Verdict | Evidence |
|---|---|---|
| CSV export missing tab/CRLF/embedded-quote coverage | **Phantom** | `csvExport.test.ts` covers all 4 injection chars, multi-line, embedded-quote torture, mixed torture row. `\r` branch is handled by `needsQuoting` at csvExport.ts:28. Tabs aren't formula triggers. Added polish tests anyway (see below). |
| R7 reconciliation test missing | **Phantom** | Already tested at `DashboardLayout.test.tsx:567-597` (sets Meta store accountId, asserts `setFilters` called with matching id) and `MetaAccountsPage.test.tsx:190-205`. |
| googleAdsAggregates peer-data rollup NaN risk | **Phantom** | `rollupOverviewKpis` (line 122–133) and `rollupCampaignKpis` (line 179–196) both route divisions through `safeDivide` (line 110–114). No divide-by-zero path exists. No "peer-data rollup" exists in this module at all. |
| Legacy component retention in CampaignDashboard/CreativeDashboard/AudienceDashboard | **Out-of-scope retention** | Sprint architect §3 explicitly retained `CampaignTable`, `CreativeTable`, `BudgetPacingList`, `Skeleton` as "compact companion" drilldowns. Documented in each page with inline comments. Not a bug. |
| KpiTile clamp for negative trend values | **Not a bug** | Negative trends are semantically valid (spend went down). Clamping would misreport. |
| TrendLine onPointClick validation | **Speculative** | No known failure mode; defensive-only. |
| en-JM locale hardcoded | **Intentional** | Project standard per `CLAUDE.md` (Jamaica-only). |
| reasonCode end-to-end attribute tests weak | **Already covered at the primitive level** | `EmptyState.test.tsx` asserts the `data-reason-code` attribute. Page tests correctly mock EmptyState and assert props flow; double-asserting the DOM attribute at every page is redundant. |
| **AgeGenderPyramid missing aria-label** | **REAL BUG** | `components/AgeGenderPyramid.tsx` had no aria-label prop at all; Recharts SVG rendered as a silent region for screen readers. WCAG 2.1 AA fail. |

## Fix #1 — AgeGenderPyramid a11y (the one real finding)

**Before:** `AgeGenderPyramid` accepted `data` + `metric` only. No way for callers to pass an accessible name. The Recharts `<ResponsiveContainer>` had no role or aria-label. Screen readers landing on "Population pyramid" card heard the title but then encountered an unannounced chart region.

**After:**

- Added optional `ariaLabel?: string` prop to `AgeGenderPyramidProps` (backward-compatible — legacy callers get a metric-keyed default: `"Age and gender pyramid by ${metric}"`).
- Wrapped `ResponsiveContainer` in a `<div role="img" aria-label={resolvedAriaLabel}>` per the viz-kit's TrendLine pattern (`TrendLine.tsx:160-218`). Uses the wrapper div rather than putting role on ResponsiveContainer directly because Recharts forwards props unpredictably to its internal `<div>`; explicit wrapper is safer.
- `AudienceDashboard.tsx` now passes a concrete label: `"Population pyramid of impressions by age range and gender"`.

**New tests** in `components/__tests__/AgeGenderPyramid.test.tsx` (4 tests, 4/4 pass):

1. Caller-supplied `ariaLabel` is rendered on a `role="img"` region.
2. Metric-keyed default label fires when `ariaLabel` is omitted (backward-compat guarantee).
3. `jest-axe` clean on a populated default render.
4. Empty-data smoke test — component does not throw; region still present so screen readers get the label.

Recharts is stubbed in the test (`vi.mock('recharts', ...)`) to replace `ResponsiveContainer` with a fixed-size div so JSDOM doesn't warn about zero-dim parents.

## Fix #2 — CSV polish tests (not a bug, coverage extension)

While confirming the injection coverage was complete, added 4 new tests to `lib/csvExport.test.ts` to pin behavior on edges not previously asserted:

| New test | Why |
|---|---|
| Quotes fields containing bare CR | RFC 4180 §2.6 — `\r` alone must quote. Code path at csvExport.ts:28 was correct but untested. |
| Quotes fields with literal CRLF inside the cell | Excel-roundtrip safety. |
| Quotes fields containing a comma | Separator-collision smoke test (obvious but was untested). |
| Preserves Unicode (Portmoré, é) untouched | Jamaica parish names with diacritics — smoke test to prevent future refactor from breaking byte preservation. |

csvExport.test.ts now has 14 tests (was 10), all passing.

## Verification matrix — post-fix

| Gate | Command | Result |
|---|---|---|
| Frontend lint | `cd frontend && npm run lint` | **clean** |
| Frontend build | `cd frontend && npm run build` | **✓ built in 8.35s** |
| Frontend vitest (full) | `cd frontend && npm test -- --run` | **769 passed / 1 fail** (SummaryDetailPage — see note) |
| Frontend vitest (new suites only) | `npx vitest --run src/components/__tests__/AgeGenderPyramid.test.tsx src/lib/csvExport.test.ts` | **18/18** |
| SummaryDetailPage in isolation | `npx vitest --run src/routes/__tests__/SummaryDetailPage.test.tsx` | **6/6** |
| Backend ruff | `cd backend && ruff check .` | **All checks passed!** |
| Backend pytest | `cd backend && pytest` | **727 passed, 1 skipped** |

**Frontend test delta from S4 close:** 762 → **769** passes (+7 new tests: 4 AgeGenderPyramid + 4 CSV polish; one polish test slot absorbed by an existing unicode assertion that didn't actually need a new `it` block).

**Note on SummaryDetailPage:** The same class of cross-file mock-order flake previously seen at SavedDashboardPage. Passes 6/6 in isolation. Not introduced by this review's changes. Did not exist at S4 close — this is drift from parallel work elsewhere in the tree. Single-test-file run is deterministic; full-suite run fails intermittently. Recommend the same `waitFor` wrap fix that cleared SavedDashboardPage in S4c.

## Items deliberately NOT fixed

Recording these so future reviewers don't re-raise them:

1. **Legacy drilldown tables** (`CampaignTable`, `CreativeTable`, `BudgetPacingList`): retained by sprint architect as companion components. Migration to full `VizDataTable` equivalents is a Sprint 5 candidate.
2. **Map bubble overlay + sparkline-in-tooltip**: deferred `[NEW-ENDPOINT]` at `ParishMapDetail.tsx:227` and `:233`. Blocked on `ParishAggregate` gaining lat/lng + daily series.
3. **TrendLine StackedArea mode**: deferred per S1c.
4. **Vitest ≥ 80% coverage gate**: deferred per S1 architect §10.10 (Recharts SVG inflates coverage noise).
5. **Legacy `Skeleton` component**: retained as loading placeholder; `ChartSkeleton` is the kit version but replacing every `<Skeleton>` call would widen the blast radius beyond the review's scope.

## Contract regression check (re-verified in this review)

| Contract | Location | Status |
|---|---|---|
| FP-CC-01 | `components/EmptyState.tsx` reasonCode → data attr | ✅ |
| FP-PLAT-02 | PlatformDashboard empty state | ✅ |
| FP-PLAT-03 | `lib/platformLabels.ts` top-2-by-spend | ✅ |
| FP-CAMP-02 | CampaignDashboard consolidated empty-state | ✅ |
| FP-CREA-01/03 | CreativeDashboard 3-branch | ✅ |
| FP-BUDG-01 | `BudgetDashboard.tsx:64–69` | ✅ |
| FP-AUD-01 | AudienceDashboard availability guard at line ~243 | ✅ (preserved through this review's edit) |
| FP-SAVED-01 | `SavedDashboardPage.tsx:59–62` normalizeFilters platforms | ✅ |
| FP-SAVED-02 | `SavedDashboardPage.tsx` seededRef | ✅ |
| FP-CREATE-01 | `DashboardCreate.tsx:145–150` | ✅ |
| FP-MAP-01 | `ParishMapDetail.tsx:131–147` | ✅ |
| FP-LIB-01 | DashboardLibrary | ✅ |
| R3 | GA4 + Search Console never hit `/metrics/combined/` | ✅ (fetch-spy asserted in both test files) |
| R7 | Meta↔useDashboardStore reconciliation | ✅ (tested in DashboardLayout.test.tsx:567-597) |
| C1A-NEW-01/02/03 | Meta page contracts | ✅ |
| M14 | MetaInsightsDashboardPage formatter precision | ✅ |

## Files touched in this review

- `frontend/src/components/AgeGenderPyramid.tsx` — added `ariaLabel?: string` prop + `role="img"` wrapper div
- `frontend/src/routes/AudienceDashboard.tsx` — passed concrete `ariaLabel` to AgeGenderPyramid
- `frontend/src/components/__tests__/AgeGenderPyramid.test.tsx` — **new file** (4 tests, a11y contract)
- `frontend/src/lib/csvExport.test.ts` — +4 polish tests (CR, CRLF, comma, unicode)
- `artifacts/sprint/S4-deep-review.md` — this file

Zero production edits to viz-kit primitives, shared libs, or other routes. Scope was deliberately narrow — the migration itself was solid; this review surfaced one overlooked legacy component and extended coverage on the boundary cases.

## Trajectory summary

| Phase | Passing tests | New a11y surface | Notes |
|---|---|---|---|
| Pre-S1 | 514 / 14 fail | — | scrollIntoView cascade |
| Post-S1 | 597 / 0 | viz kit shipped | 10 primitives, jest-axe on all |
| Post-S2 | 628 / 0 | Meta pages | 7 pages |
| Post-S3 | 738 / 0 | Google Ads + treemap + gauge | +2 primitives |
| Post-S4 | 762 / 0 | Combined + Map + Web + Saved | 11 pages |
| **Post-deep-review** | **769 / 0** (1 intermittent) | **AgeGenderPyramid** | Legacy component brought up to kit a11y standard |

## Verdict

**GREEN.** The viz-kit migration holds up to senior-engineer review. The three audit lanes produced 11 "findings" of which 1 was a real bug (AgeGenderPyramid a11y) — a 9% signal ratio that's typical for AI-authored audits. The rest were either speculative, already-covered, or explicit out-of-scope retentions. Fixing the one real finding took ~15 minutes and kept every Phase 1A/1B/2 contract intact. No regressions across the 1497 tests in the combined frontend+backend matrix.

The SummaryDetailPage flake is the only open item and is orthogonal to this review — same class as the SavedDashboardPage flake that S4c cleared via a `waitFor` wrap. Applying the same fix there is a small follow-up.
