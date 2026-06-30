# Report export CLI overview

## Purpose

The report exporter turns aggregated advertising metrics into printable deliverables. It merges JSON payloads with the HTML template in `integrations/exporter/templates/`, renders the report in headless Chromium, and emits an A4 PDF plus a first-page PNG preview. This makes it easy to hand off consistent performance summaries without opening the full BI stack.

The application report export flow (`POST /api/reports/{id}/exports/`) now uses this renderer for
generic PDF/PNG requests and writes CSV artifacts directly from the tenant-scoped aggregate
snapshot. A job is marked `completed` only after its requested artifact exists and is non-empty;
download it through `GET /api/exports/{job_id}/download/`.
CSV artifacts neutralize formula-leading text cells before download, and both generic and Google
Ads artifact download handlers reject paths that escape the expected export directory.
In container profiles, the API and summary worker use `REPORT_EXPORT_ARTIFACT_ROOT` on a shared
volume so successfully rendered worker artifacts are immediately downloadable by the API.

For `report.v1` exports, `ReportExportJob.metadata.report_preview` is the reproducibility record.
It includes schema/template/catalog identifiers, the requested date range, coverage summary,
blocking reasons, warnings, preview hash, and a durable `report_snapshot` with ordered pages and
widget preview payloads. The async worker renders CSV/PDF/PNG from that stored snapshot, not from a
live provider call or the generic aggregate snapshot path. CSV rows use page/widget/metric/value
columns, while PDF/PNG use the `report_v1_snapshot` template so unavailable organic metrics remain
notes or warnings instead of being forced into paid-media columns. Support should compare the
visible preview hash with the latest export snapshot hash before claiming an export reflects the
current report state.
When a report-scoped saved builder layout exists (`SavedReportLayout.config.id ==
report-<report_id>`), export metadata also includes an additive `report_layout` snapshot. Manual
exports prefer the requesting user's saved layout and fall back to the newest shared tenant layout;
scheduled dry-runs follow the same requester-first/shared fallback rule. PDF/PNG rendering uses
that saved grid config for client-facing visual layout while still sourcing values from the queued
governed report snapshot; CSV keeps the governed snapshot row shape so coverage/status audit
columns remain comparable across evidence runs. Before the snapshot is stored, the backend appends
any governed preview widgets that are missing from the saved grid, matching by widget id and
dataset/widget/metric source signature and placing them below the custom grid. The additive
`report_layout.governed_widget_append_count` records how many widgets were appended. If no saved
layout exists, PDF/PNG fall back to the governed snapshot table renderer.
The `report_v1_snapshot` PDF/PNG template is intentionally client-facing: the first visible header
uses monthly report language, warning text is labeled as data-availability notes, and technical
template/preview-hash metadata is kept in a small report-evidence footer.
For partial retained-history coverage, `coverage_summary.datasets[].coverage_gap` carries requested
day count, covered day count, missing day count, leading/trailing gap booleans, and exact missing
dates for monthly/90-day evidence windows. Use that field to diagnose partial paid Meta coverage
before deciding whether to backfill, adjust the account/date/report filters, or accept the dataset
as warning-only.
The SLB monthly template has an explicit warning-only export policy for organic Facebook, Content
Ops, and scoped selected-account paid `missing_history`/`not_previously_synced` states. That policy
allows truthful CSV/PDF/PNG artifacts with visible "no retained rows" warnings, while permission
gaps, unsupported metrics, and unscoped paid widgets remain blockers.
For SLB fixed-target evidence, paid widgets must be scoped by `account_id` or `client_id` before
export. If the scoped account/client has no retained paid rows, the report may export only as
explicit warning-only no-data evidence; do not let it fall back to tenant-wide Meta rows or older
unscoped snapshots.
`GET /api/reports/data-availability/` now mirrors that paid scoping: `client_id` resolves to linked
Meta ad accounts, `client_id` + `account_id` uses their intersection, and a scoped paid miss may
return `datasets.paid_meta_ads.scope_diagnostic` with the required reconnect/link/backfill action.
For account-scoped misses, `scope_diagnostic.credential_status.status=missing` means the selected
ad account has no retained Meta credential. The export can still prove current no-data behavior with
warnings, but paid parity and cancellation readiness stay blocked until the account is reconnected
and backfilled or an approved daily paid CSV is imported.
The SLB evidence bundle command resolves those stored `/exports/...` artifact paths through
`REPORT_EXPORT_ARTIFACT_ROOT` before recording `artifact_present`, `artifact_size_bytes`,
`source`, `row_count`, `report_layout_source`, and
`report_layout_governed_widget_append_count`, so G5 evidence reflects the same files and saved
layout path the API download endpoint serves.
The bundle also includes the same compact `data_availability` summary used by blocked export
evidence, so G2-G9 packets preserve paid scope diagnostics and selected-account credential status
without requiring a separate API lookup.
`slb_report_evidence_validate` selects the newest reproducible completed export row per format from
the bundle and reports those rows under additive `export_evidence.selected_completed_exports`. Use
that validation block, not older same-hash rows in the raw bundle, when proving the current
layout-backed CSV/PDF/PNG evidence set.
For fixed-target SLB evidence runs, operators can generate the required CSV/PDF/PNG artifacts and
one sanitized scheduled dry-run in a single backend-only pass:

```bash
backend/.venv/bin/python backend/manage.py slb_report_export_evidence \
  --report-id <report-id> \
  --start-date 2026-05-01 \
  --end-date 2026-05-31
```

The command creates normal `ReportExportJob` rows, runs the export task synchronously, verifies
non-empty artifacts under `REPORT_EXPORT_ARTIFACT_ROOT`, and emits a redacted
`slb_export_evidence_run.v1` JSON summary keyed by export format. Successful runs include
`export_ready=true`, `coverage_summary`, `blocking_reasons`, and `warnings` so reviewers can see
which warning-only sections were rendered. When a matching saved `report-<report_id>` layout exists,
the command attaches the same augmented `metadata.report_layout` snapshot used by API exports; each
export row includes additive `report_layout_source` and
`report_layout_governed_widget_append_count` fields so G5/G7 evidence proves whether PDF/PNG used
the governed saved-grid path. It does not call live providers or send client email.
If required stored coverage is still missing, the command exits non-zero after writing the same
schema with `status: "blocked_by_coverage"`, requested CSV/PDF/PNG rows marked
`blocked_by_coverage`, the preview hash, coverage summary, a compact `data_availability` summary,
blocking reasons, warnings, and a sanitized scheduled dry-run job with
`delivery_status.status == "blocked_by_coverage"`. The `data_availability` summary omits large
account lists and exact missing-date arrays, but keeps per-dataset coverage status plus any
`paid_meta_ads.scope_diagnostic.credential_status` guidance. Keep that blocked JSON with the
evidence packet; it proves no artifact was generated from incomplete coverage and identifies the
missing reconnect/backfill/import work. `slb_report_evidence_validate` reads that summary when
present and emits `data_availability_paid_credential` when the selected paid Meta account has no
retained credential.

Scheduled report delivery starts with dry-run evidence. `POST /api/reports/{id}/scheduled-dry-run/`
creates a normal export job with `metadata.delivery_status.mode == "dry_run"` and does not send
client email. Coverage-blocked dry-runs are recorded as failed jobs with sanitized
`blocked_by_coverage` status plus preview hash and coverage summary so operators can prove the
schedule gate without reading logs.

## Setup

1. Install prerequisites (Node.js 18+). Linux deployments use the bundled
   native Chromium executable configured with `CHROMIUM_EXECUTABLE_PATH`; this keeps container
   rendering compatible with both x86-64 and ARM64 images. Other Linux runtimes may use the
   bundled `@sparticuz/chromium` build. Local macOS/Windows development uses Playwright's
   installed platform browser; run `npx playwright-core install chromium` if no cached browser
   exists.
2. Install dependencies:
   ```bash
   cd integrations/exporter
   npm ci
   ```
3. Optional: run the no-op build script if you want to verify the package.json scripts wire up correctly:
   ```bash
   npm run build
   ```

## Running the sample export

The CLI ships with a sample payload under `integrations/exporter/examples/data.sample.json`. Generate a report and preview using the bundled data:

```bash
node bin/export-report \
  --data examples/data.sample.json \
  --out out/sample-report.pdf \
  --png out/sample-report.png
```

The command creates an `out/` directory inside `integrations/exporter/` on demand. With the current template, the sample run produces:

- `integrations/exporter/out/sample-report.pdf` (~71 KB)
- `integrations/exporter/out/sample-report.png` (~53 KB)

Your exact sizes may vary slightly when templates or assets change, but both files are regenerated every execution. If you point `--out` or `--png` to another location, those paths will be created for you.

## Expected output and artifacts

The PDF captures all report pages with background graphics enabled, while the PNG is a full-page render of the first sheet—handy for quick previews or embedding into slides. Keep the `out/` directory in `.gitignore`; it is transient output. When the exporter runs, it also invokes the Canva stub and logs whether Canva credentials are present so ops teams can verify integration readiness.

## Environment configuration

Future Canva exports require authenticated calls. Copy `.env.example` (in the exporter package) to `.env` and populate the placeholder values—currently just `CANVA_API_KEY`. The CLI loads this file automatically via `dotenv`, enabling Playwright rendering to continue even when Canva credentials are absent. Until real Canva uploads land, the stub logs the payload and exits, but wiring the API key now avoids runtime warnings.

## Using custom JSON payloads

To render real tenant data, point the `--data` flag at your own JSON document, for example:

```bash
node bin/export-report \
  --data /tmp/my-report.json \
  --out out/tenant-2024-09.pdf \
  --png out/tenant-2024-09.png
```

Ensure the payload matches the shape expected by `examples/data.sample.json`. Keep custom payloads out of the repository—store them in a secure blob or generate them on demand from the data warehouse.

Application-generated payloads and artifacts contain aggregate report metrics only. Export logs
may contain tenant/job identifiers, format, status, and duration, but never exported row content.
