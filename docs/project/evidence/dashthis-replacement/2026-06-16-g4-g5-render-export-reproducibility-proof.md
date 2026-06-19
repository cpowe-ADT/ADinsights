# G4/G5 Render And Export Reproducibility Proof Packet

Date: 2026-06-16
Timezone: America/Jamaica
Goal IDs: G4, G5
Status: evidence protocol prepared; blocked on G1 fixed target/runtime values and G2/G3 coverage proof.

## Purpose

Prove that ADinsights can render the fixed SLB reporting experience and export reproducible
CSV/PDF/PNG artifacts from stored aggregate data for the same report/date range.

This packet does not close G4 or G5. It defines the evidence to collect once G1 locks the target
runtime/report/date range and G2/G3 prove stored-data coverage and retained history.

## Guardrails

- Use stored aggregate ADinsights data only.
- Do not call live provider APIs during report preview, dashboard rendering, export, or download.
- Do not expose secrets, raw provider payloads, OAuth tokens, private recipient emails, ad account
  IDs, Page IDs, or user-level metrics in screenshots, logs, export files, or evidence summaries.
- Keep Instagram absent from the v1 SLB proof unless separately approved by Raj/Mira and data owners.
- Do not treat an export as cancellation evidence if it uses demo/default/wrong-tenant data or a
  date range different from G1.

## Inputs Required Before Collection

| Input | Required source | Status |
| --- | --- | --- |
| Target environment and frontend/backend URLs | G1 fixed target | Pending |
| Safe tenant/client identifier | G1 fixed target | Pending |
| SLB `ReportDefinition.id` | G1 fixed target | Pending |
| SLB `template_key` | Expected `slb_monthly_social_report` | Pending |
| Fixed monthly date range | G1 fixed target | Pending |
| Coverage/retention classification | G2/G3 proof packet | Pending |
| Saved `dashboard.v1` dashboard ID | Runtime proof setup | Pending |
| Operator auth/session | Runtime proof setup | Pending |

## G4 Rendering Proof

### Saved `dashboard.v1` Rendering

Route:

- `/dashboards/saved/<dashboard-id>`

Expected frontend path:

- `SavedDashboardPage` loads a saved `dashboard.v1` layout.
- Each governed widget calls `POST /api/dashboards/widget-preview/`.
- `GovernedWidgetRenderer` renders KPI, line/bar/table, coverage warnings, blocked/error states,
  and empty states without mutating the layout.

Evidence to capture:

| Evidence item | Required value |
| --- | --- |
| Dashboard ID | Safe ID or redacted ID |
| `layout.schema_version` | `dashboard.v1` |
| Widget IDs rendered | List of governed widget IDs |
| Widget preview source | `POST /api/dashboards/widget-preview/` only |
| Coverage notes | Visible beside affected widgets |
| Tenant scope | Dashboard belongs to the authenticated tenant |
| Screenshot paths | Desktop and mobile screenshots, or equivalent verified UI paths |
| Failure states | Record any blocked/error widgets and reason |

### SLB `report.v1` Rendering

Route:

- `/reports/<report-id>`

Expected frontend path:

- `ReportDetailPage` loads `GET /api/reports/<id>/`.
- For `report.v1`, it calls `POST /api/reports/<id>/preview/` and
  `GET /api/reports/<id>/diagnostics/`.
- `ReportPreviewPanel` renders ordered pages and coverage/export readiness.
- `SnapshotPanel` shows the latest export snapshot and whether it matches the visible preview.
- `DiagnosticsPanel` shows support-safe dataset status.

Required SLB pages:

| Page | Required evidence |
| --- | --- |
| Cover and period | Page is visible and uses the fixed G1 date range. |
| Executive summary | Paid and organic KPI widgets render or clearly block with coverage notes. |
| Paid Meta Ads | Paid trend/table widgets render from stored aggregate data. |
| Organic Facebook/Page | Page insights widgets render from stored Page/Post rows. |
| Top posts | Top-post table renders or records a coverage/history blocker. |
| Content activity | Content Ops summary renders from aggregate records/snapshots. |
| Recommendations | Narrative section renders and does not hide coverage caveats. |
| Appendix/data notes | Coverage summary and notes are visible. |
| Instagram | Absent/deferred in v1 proof. |

Evidence to capture:

| Evidence item | Required value |
| --- | --- |
| Report ID | Same report ID as G1/G2/G3 |
| `template_key` | `slb_monthly_social_report` |
| `schema_version` | `report.v1` |
| `catalog_schema_version` | `reporting_catalog.v1` |
| `preview_hash` | From `POST /api/reports/<id>/preview/` |
| `export_ready` | `true` for export proof, or explicit blocker recorded |
| `coverage_summary` | Same datasets/statuses as G2/G3 proof |
| Screenshot paths | Desktop and mobile report screenshots, or equivalent verified UI paths |
| Long label/table behavior | No overlap; tables scroll or wrap predictably |

## G5 CSV/PDF/PNG Export Reproducibility Proof

### Create Exports

Use the same report ID and date range established in G1. Manual export requests should be blocked
with `409` if required coverage is missing.

```bash
curl -fsS \
  -H "Authorization: Bearer <operator-token>" \
  -H "Content-Type: application/json" \
  -X POST \
  "<backend-url>/api/reports/<report-id>/exports/" \
  -d '{"export_format":"csv"}'

curl -fsS \
  -H "Authorization: Bearer <operator-token>" \
  -H "Content-Type: application/json" \
  -X POST \
  "<backend-url>/api/reports/<report-id>/exports/" \
  -d '{"export_format":"pdf"}'

curl -fsS \
  -H "Authorization: Bearer <operator-token>" \
  -H "Content-Type: application/json" \
  -X POST \
  "<backend-url>/api/reports/<report-id>/exports/" \
  -d '{"export_format":"png"}'
```

Poll export history:

```bash
curl -fsS \
  -H "Authorization: Bearer <operator-token>" \
  "<backend-url>/api/reports/<report-id>/exports/"
```

Download artifacts:

```bash
curl -fsS \
  -H "Authorization: Bearer <operator-token>" \
  -o slb-report.<format> \
  "<backend-url>/api/exports/<export-job-id>/download/"
```

### Export Metadata To Capture

For each `csv`, `pdf`, and `png` job:

| Field | Required proof |
| --- | --- |
| `ReportExportJob.id` | Recorded in evidence packet |
| `export_format` | `csv`, `pdf`, or `png` |
| `status` | `completed` |
| `artifact_path` | Starts with `/exports/` and belongs to the same tenant/report/job |
| Download size | Non-zero byte count |
| `metadata.report_preview.report_schema_version` | `report.v1` |
| `metadata.report_preview.template_key` | `slb_monthly_social_report` |
| `metadata.report_preview.catalog_schema_version` | `reporting_catalog.v1` |
| `metadata.report_preview.generated_at` | Timestamp recorded |
| `metadata.report_preview.date_range` | Matches G1 |
| `metadata.report_preview.coverage_summary` | Matches G2/G3 summary |
| `metadata.report_preview.preview_hash` | Matches report preview hash when no data changed |
| `metadata.report_preview.report_snapshot.pages[*].id` | Contains ordered SLB pages |
| `metadata.delivery_status.mode` | `manual_export` for manual exports |

### Artifact Safety Checks

Required checks:

- Download endpoint returns `200` only for completed jobs.
- Incomplete jobs return `409 Export is not ready`.
- Empty or missing artifact returns a failure, not a successful download.
- Artifact path cannot escape the configured export root.
- CSV values that could be spreadsheet formulas are escaped.
- PDF and PNG files are non-empty and open/render successfully.
- Export metadata is redacted and contains no secrets/raw provider payloads/user-level metrics.

Suggested local artifact checks after download:

```bash
wc -c slb-report.csv slb-report.pdf slb-report.png
file slb-report.csv slb-report.pdf slb-report.png
python3 - <<'PY'
from pathlib import Path
for path in ["slb-report.csv", "slb-report.pdf", "slb-report.png"]:
    data = Path(path).read_bytes()
    if not data:
        raise SystemExit(f"{path} is empty")
print("artifacts_non_empty=true")
PY
```

## Reproducibility Pass Rules

G4 rendering proof can pass only when:

- Saved `dashboard.v1` renders through governed widget preview payloads.
- SLB `report.v1` renders ordered pages for the same report/date range as G1.
- Coverage notes appear near affected widgets and in appendix/data notes.
- Desktop and mobile screenshots or equivalent browser evidence show no severe overlap.
- Instagram is absent/deferred.
- Legacy dashboards/reports remain outside the proof claim unless separately tested.

G5 export reproducibility proof can pass only when:

- CSV, PDF, and PNG jobs complete for the same fixed report/date range.
- Downloads are non-empty and artifact paths are safe.
- `report_snapshot.preview_hash` matches the visible report preview hash when data has not changed.
- Export metadata preserves report schema, template key, catalog schema, generated timestamp, date
  range, coverage summary, blocking reasons, export readiness, and ordered pages.
- Coverage-blocked exports fail clearly with `409` and do not produce misleading artifacts.
- No export evidence contains secrets, raw provider payloads, or user-level metrics.

## Current Implementation Evidence

Local backend regression coverage now verifies completed `report.v1` CSV, PDF, and PNG exports preserve the
request-time durable report snapshot and preview hash:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_report_v1_completed_export_preserves_preview_snapshot_hash
```

Result: `3 passed`.

The regression captures `POST /api/reports/<id>/preview/`, requests CSV, PDF, and PNG exports, runs
each export task, verifies each artifact is non-empty, and asserts:

- `job.metadata.report_preview.preview_hash` matches the visible preview hash.
- `job.metadata.report_preview.report_snapshot.preview_hash` matches the visible preview hash.
- `job.metadata.report_preview.report_snapshot.pages` preserves the ordered SLB pages.

The broader reporting slice and canonical backend gate also passed:

```bash
backend/.venv/bin/pytest -q backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py
make backend-lint && make backend-test
```

This strengthens G5 implementation evidence for snapshot reproducibility. It does not close
fixed-target CSV/PDF/PNG artifact proof, browser rendering proof, or cancellation readiness.

## Reviewer Route

- Lina: report/dashboard rendering UX, frontend payload assumptions, visible coverage states.
- Joel: shared widget renderer behavior, responsive layout, long labels/table overflow.
- Sofia: report export API, serializer payloads, tenant scoping, blocked export behavior.
- Omar: operational states, stale/partial/disconnected warnings, export failure clarity.
- Nina: artifact safety, redaction, path safety, and sensitive evidence review if artifacts are
  stored or shared.
- Raj/Mira: required if render/export proof exposes cross-stream architecture, schema versioning, or
  cancellation-gate changes.
- Carlos/Mei: required only if packaged renderer/runtime/storage/deployment behavior changes.

## Current Decision

G4 and G5 are not passed. The implementation path exists, but fixed-range rendering and export
reproducibility evidence still needs a real G1 report/date range plus G2/G3 stored-data coverage
proof.

DashThis cancellation remains no-go.
