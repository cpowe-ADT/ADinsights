# Local Visual Render Proof

Date: 2026-06-17
Timezone: America/Jamaica
Status: local-only visual proof; not cancellation-review evidence.

## Purpose

Record the post-polish visual state of the local SLB report detail page after frontend report
readability and widget-status improvements.

This proof confirms the local report route is visually renderable on desktop and mobile and that
coverage states are visible. It does not prove DashThis parity, production/staging readiness, or
fixed-target cancellation-review readiness.

## Runtime Target

| Field          | Value                                           |
| -------------- | ----------------------------------------------- |
| Frontend URL   | `https://localhost:5173`                        |
| Backend URL    | `http://localhost:8000`                         |
| Report route   | `/reports/a40abad9-9f1d-4e75-92b0-3e0feaed27b5` |
| Report name    | `SLB Monthly Social Report - Local Demo`        |
| Template key   | `slb_monthly_social_report`                     |
| Schema version | `report.v1`                                     |
| Evidence class | Local visual smoke only                         |

## Screenshot Artifacts

Screenshot files are local artifacts under ignored `output/playwright/`:

| View                 | Path                                            |
| -------------------- | ----------------------------------------------- |
| Desktop top viewport | `output/playwright/slb-report-desktop-top.png`  |
| Desktop full page    | `output/playwright/slb-report-desktop-full.png` |
| Mobile top viewport  | `output/playwright/slb-report-mobile-top.png`   |
| Mobile full page     | `output/playwright/slb-report-mobile-full.png`  |

## Observed Status Labels

The capture script found these report/widget status labels on both desktop and mobile:

- `export with warnings`
- `missing_history`
- `source_disconnected`
- `fresh`
- `completed`

The local visual proof now shows:

- Dataset coverage cards at the top of the report.
- `content_ops` and `organic_facebook_page` marked `missing_history`.
- `paid_meta_ads` marked `source_disconnected`.
- Widget cards reflecting non-fresh coverage instead of always showing green `rendered`.
- Operations panels separated from report content.
- Mobile top viewport fits the coverage summary without horizontal overflow.

Follow-up frontend cleanup also removed duplicated table headings inside governed table widgets, so
the widget card title remains the only visible table title while the inner table keeps an accessible
caption.

Follow-up readiness cleanup changed the report-level badge from `export ready` to `export with
warnings` when the report can export but any dataset/widget coverage is stale, missing, partial, or
disconnected.

## Remaining Visual/Readiness Gaps

- The report is still local-only and not an approved G1 target.
- The UI is more legible, but not final client-ready design.
- The local data still lacks organic Facebook/Page and Content Ops retained history for the
  requested range.
- Paid Meta Ads remains disconnected/stale for the requested range.
- Export readiness means the export path can run with warnings; it does not mean data parity is
  proven.
- This proof does not close G4/G5 because G1 is not approved and fixed-target evidence has not been
  captured.

DashThis cancellation remains `NO-GO`.

## Commands

The local stack was checked first:

```bash
scripts/dev-healthcheck.sh
```

Screenshots were captured with Playwright against:

```text
https://localhost:5173/reports/a40abad9-9f1d-4e75-92b0-3e0feaed27b5
```

The later table-title cleanup was covered by:

```bash
npm --prefix frontend test -- ReportDetailPage
make frontend-lint
make frontend-build
```

The later export-with-warnings cleanup was covered by the same focused checks:

```bash
npm --prefix frontend test -- ReportDetailPage
make frontend-lint
make frontend-build
```
