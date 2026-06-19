# Local Browser Render/Export Proof

Date: 2026-06-17
Timezone: America/Jamaica
Status: local-only implementation proof; not cancellation-review evidence.

## Purpose

Record what the local browser-visible SLB report currently proves after opening the report detail
page at:

`https://localhost:5173/reports/a40abad9-9f1d-4e75-92b0-3e0feaed27b5`

This packet confirms the reporting engine is working locally at the preview/export mechanics level.
It does not prove DashThis parity, production/staging readiness, fixed-target approval, or complete
SLB data coverage.

## Local Target

| Field                  | Value                                           |
| ---------------------- | ----------------------------------------------- |
| Report ID              | `a40abad9-9f1d-4e75-92b0-3e0feaed27b5`          |
| Report name            | `SLB Monthly Social Report - Local Demo`        |
| Template key           | `slb_monthly_social_report`                     |
| Schema version         | `report.v1`                                     |
| Date range             | `last_month` resolved in preview to May 2026    |
| Frontend route         | `/reports/a40abad9-9f1d-4e75-92b0-3e0feaed27b5` |
| Cancellation evidence? | No                                              |

## Browser Observation

The in-app browser rendered the report detail page and showed:

- Coverage/export readiness summary.
- Ordered report pages including cover, executive summary, paid Meta Ads, organic Facebook/Page,
  top posts, export actions, and scheduled delivery sections.
- Paid Meta Ads retained data.
- Missing-history states for organic Facebook/Page and Content Ops.
- Manual export buttons for CSV, PDF, and PNG.

The UI is visually rough and is not client-ready. The proof here is functional routing and
reporting mechanics, not final report design.

## API Preview Proof

Command shape:

```bash
curl -ksS -X POST \
  https://localhost:5173/api/reports/a40abad9-9f1d-4e75-92b0-3e0feaed27b5/preview/ \
  -H "Authorization: Bearer <dev-admin-token>" \
  -H "Content-Type: application/json" \
  -d "{}"
```

Observed summary:

| Field            | Value                                                              |
| ---------------- | ------------------------------------------------------------------ |
| `export_ready`   | `true`                                                             |
| Report pages     | `8`                                                                |
| Blocking reasons | `[]`                                                               |
| Preview hash     | `e795fb08d22ec0ee02015c771f7cef15d19cf8188140f0baaaadc90dd07fa6ff` |

Coverage summary:

| Dataset                 | Row count | Coverage state        | Covered range                | Interpretation                                                                                     |
| ----------------------- | --------: | --------------------- | ---------------------------- | -------------------------------------------------------------------------------------------------- |
| `paid_meta_ads`         |        21 | `source_disconnected` | `2026-02-27` to `2026-03-29` | Local retained paid data exists, but the source is disconnected/stale for the requested May range. |
| `organic_facebook_page` |         0 | `missing_history`     | None                         | No retained Page/Post rows for the requested range.                                                |
| `content_ops`           |         0 | `missing_history`     | None                         | No retained Content Ops aggregate rows for the requested range.                                    |

## Diagnostics Proof

Command shape:

```bash
curl -ksS \
  https://localhost:5173/api/reports/a40abad9-9f1d-4e75-92b0-3e0feaed27b5/diagnostics/ \
  -H "Authorization: Bearer <dev-admin-token>"
```

Observed dataset diagnostics:

| Dataset                 | Status                | Rows | Recommended next action                                                     |
| ----------------------- | --------------------- | ---: | --------------------------------------------------------------------------- |
| `content_ops`           | `missing_history`     |    0 | Confirm backfill or upload fallback before claiming DashThis parity.        |
| `organic_facebook_page` | `missing_history`     |    0 | Confirm backfill or upload fallback before claiming DashThis parity.        |
| `paid_meta_ads`         | `source_disconnected` |   21 | Reconnect the source; retained history can still support limited reporting. |

## Export Proof

Manual export requests were tested through the authenticated local API.

Completed jobs:

| Format | Job ID                                 | Status      | Download proof                                                         |
| ------ | -------------------------------------- | ----------- | ---------------------------------------------------------------------- |
| CSV    | `d9e393e2-f7c2-4e41-a559-f04e8d3dfb2e` | `completed` | HTTP `200`, `775` bytes, `file` reports CSV text.                      |
| PDF    | `0b4c79ac-d83d-48d4-9f1a-f2f162f88e0c` | `completed` | HTTP `200`, `72,931` bytes, `file` reports PDF document version 1.4.   |
| PNG    | `f5b93451-23f9-4dce-bff7-284f27102952` | `completed` | HTTP `200`, `92,143` bytes, `file` reports PNG image data, 1280 x 720. |

Export artifact paths were tenant/report/job scoped under `/exports/`.

## What This Proves

- The local report detail route can render a `report.v1` SLB report scaffold.
- `POST /api/reports/<id>/preview/` returns ordered page/widget payloads.
- Coverage states are surfaced instead of hidden.
- `GET /api/reports/<id>/diagnostics/` returns support-safe dataset status.
- CSV, PDF, and PNG export jobs can complete locally and download non-empty artifacts.

## What This Does Not Prove

- G0 Raj/Mira architecture/scope review.
- G1 approved fixed SLB runtime target.
- G2/G3 complete stored-data coverage or 90-day retained-history proof.
- G4/G5 cancellation-grade render/export proof for the approved fixed target.
- G6 DashThis/source parity comparison.
- G7 scheduled delivery dry-run proof for the fixed target.
- G8/G9 safety proof for cancellation review.
- G10 adversarial review.
- G11 24-48 hour hardening.
- G12 final keep/cancel recommendation.

DashThis cancellation remains `NO-GO`.

## Follow-Up

The next productive work is no longer more proof of basic mechanics. It is:

1. Clear or conditionally clear G0 with Raj/Mira.
2. Lock G1 with an approved SLB report ID, tenant/client, and date range.
3. Backfill or prove retained stored data for organic Facebook/Page and Content Ops.
4. Fill DashThis/source comparison values for the same date range.
5. Rerun preview/export/diagnostics against the approved fixed target.
