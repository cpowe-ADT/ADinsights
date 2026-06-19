# G2-G9 Fixed-Range Evidence Execution Checklist

Date: 2026-06-16
Timezone: America/Jamaica
Goal IDs: G2, G3, G4, G5, G6, G7, G8, G9
Status: execution checklist prepared; blocked until G0/G1 are cleared or explicitly allowed to proceed.

## Purpose

Use this checklist after the G1 runtime target is filled to collect cancellation-review evidence in
one consistent chain. The goal is to prevent mixed report IDs, date ranges, source scopes, tenants,
or environments from being used across coverage, parity, rendering, exports, dry-run delivery,
diagnostics, and safety proof.

This checklist does not replace the detailed G2-G9 proof packets. It is the ordered runbook for
executing them against the same fixed SLB target.

## Preconditions

Do not start this checklist until all are true:

- G0 Raj/Mira either clears scope/architecture review or explicitly allows fixed-range evidence
  capture while review remains open.
- G1 runtime target checklist is completed:
  `docs/project/evidence/dashthis-replacement/2026-06-16-g1-runtime-target-intake-checklist.md`
- Target environment, backend URL, frontend URL, safe tenant/client, report ID, template key,
  `report.v1`, date range, source scopes, comparison owner, and Instagram deferral are recorded.
- DashThis remains active.
- Stored aggregate ADinsights data is the only report preview/export data source.
- No live provider calls are made at render/export time.
- Any production-readiness blocker, including `AIRBYTE_TEMPLATE_META_METRICS_CONNECTION_ID`, is
  tracked in `external-prerequisites-checklist.md`.

## Fixed Inputs

Copy these from G1 before running anything.

| Input | Value |
| --- | --- |
| Evidence operator | TBD |
| Target environment | TBD |
| Backend URL | TBD |
| Frontend URL | TBD |
| Safe tenant/client | TBD |
| `ReportDefinition.id` | TBD |
| `template_key` | `slb_monthly_social_report` expected |
| Report schema | `report.v1` expected |
| Primary date range | TBD |
| 90-day retained-history range | TBD |
| Paid Meta account scope | TBD |
| Organic Facebook Page scope | TBD |
| Content Ops workspace/client scope | TBD |
| DashThis/source comparison owner | TBD |
| Instagram | Deferred in v1 |

If any input changes, stop and update G1 before continuing.

## Single-Run Evidence Sheet

Create one completed copy of this table per fixed G1 evidence run. Use safe filenames or evidence
paths only; do not paste raw JSON, screenshots with secrets, OAuth tokens, private recipient lists,
raw provider payloads, or user-level rows into this packet.

Machine-readable run template:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g2-g9-fixed-range-evidence-run.template.json`

Validate the filled run JSON before starting G10:

```bash
python3 scripts/validate_slb_g2_g9_evidence_run.py \
  --run-file <filled-g2-g9-evidence-run.json> \
  --intake-file <filled-g1-runtime-target-intake.json>
```

The validator fails if G1 target values drift, required sections are missing, parity rows remain
failed/blocked, CSV/PDF/PNG exports are empty or hash-mismatched, scheduled dry-run evidence sent
real client email, safety controls are incomplete, or preflight `GATE_BLOCK` is not accepted by the
G0 decision.

For G5 reproducibility, an export is counted only when all of these are true:

- the export job is completed;
- the artifact is present and non-empty;
- `preview_hash` matches the fixed evidence-bundle preview hash;
- `snapshot_preview_hash` matches the fixed evidence-bundle preview hash.

For G6 parity, the parity comparison artifact must also carry the same `report.id`,
`report.template_key`, and `preview_hash` as the fixed evidence bundle. Do not reuse a parity
worksheet from a different report preview, date range, tenant/client, or source-scope run.
The artifact's `row_count` and `result_summary` must match the actual `rows` content; a summary-only
pass is not valid evidence.
Allowed row results are `pass`, `fail`, `blocked_missing_dashthis_value`,
`blocked_missing_source_value`, and `blocked_metric_semantics`. Unsupported manual labels are blocked,
and at least one row must pass before G10 can start.
Each `pass` row must include metric identity, ADinsights value, source value, absolute delta,
accepted tolerance, and an explanation.

| Field | Value |
| --- | --- |
| Evidence run ID | `slb-YYYYMMDD-<operator-initials>` |
| Evidence run timestamp America/Jamaica | TBD |
| Operator | TBD |
| Code branch/commit or worktree note | TBD |
| Target environment | TBD |
| Safe tenant/client | TBD |
| Report ID | TBD |
| Date range | TBD |
| Preview payload file/path | TBD |
| Diagnostics payload file/path | TBD |
| History probe file/path | TBD |
| Parity output file/path | TBD |
| Evidence bundle file/path | TBD |
| Evidence validation file/path | TBD |
| Report UI screenshot/path | TBD |
| Dashboard UI screenshot/path if applicable | TBD |
| CSV export job ID/path/byte count | TBD |
| PDF export job ID/path/byte count | TBD |
| PNG export job ID/path/byte count | TBD |
| Scheduled dry-run job ID/path/status | TBD |
| G9 redaction scan result/path | TBD |
| Gate output path | TBD |
| Evidence copied into packets? | Pending |

Minimum safe summary to copy into the packet:

- HTTP status codes.
- `preview_hash`.
- `export_ready`.
- coverage summary by dataset/status.
- blocking reasons and warnings.
- export job IDs and non-zero byte counts.
- dry-run `delivery_status.mode` and `delivery_status.status`.
- parity row count and comparison worksheet path.
- redaction scan result.

Do not copy:

- operator tokens or authorization headers.
- raw provider payloads.
- private recipient emails.
- raw ad account/Page IDs unless reviewer-approved for internal evidence.
- user-level comments, reactions, profile IDs, or viewer identifiers.
- full artifact contents.

## Recommended Local Output Names

Use a dedicated temporary/evidence staging folder for each run. Review and summarize before moving
anything into tracked docs.

```bash
export ADI_EVIDENCE_RUN_ID="slb-YYYYMMDD-operator"
export ADI_EVIDENCE_TMP="/tmp/adinsights-${ADI_EVIDENCE_RUN_ID}"
mkdir -p "$ADI_EVIDENCE_TMP"
```

Suggested output files:

| Evidence | Suggested path |
| --- | --- |
| Preview | `$ADI_EVIDENCE_TMP/preview.json` |
| Diagnostics | `$ADI_EVIDENCE_TMP/diagnostics.json` |
| Monthly/90-day history probe | `$ADI_EVIDENCE_TMP/history-probe.json` |
| Parity JSON/Markdown | `$ADI_EVIDENCE_TMP/parity.json` or `$ADI_EVIDENCE_TMP/parity.md` |
| Combined evidence bundle | `$ADI_EVIDENCE_TMP/evidence-bundle.json` |
| Comparison values | `$ADI_EVIDENCE_TMP/comparison-values.json` |
| Parity comparison | `$ADI_EVIDENCE_TMP/parity-comparison.json` or `$ADI_EVIDENCE_TMP/parity-comparison.md` |
| Evidence validation | `$ADI_EVIDENCE_TMP/evidence-validation.json` |
| Export create responses | `$ADI_EVIDENCE_TMP/export-csv.json`, `export-pdf.json`, `export-png.json` |
| Export history | `$ADI_EVIDENCE_TMP/export-history.json` |
| Scheduled dry-run | `$ADI_EVIDENCE_TMP/scheduled-dry-run.json` |
| Redaction scan | `$ADI_EVIDENCE_TMP/redaction-scan.txt` |
| Gate output | `$ADI_EVIDENCE_TMP/gates.txt` |

Required pre-G10 validation output:

```bash
backend/.venv/bin/python backend/manage.py slb_report_evidence_validate \
  --evidence-bundle "$ADI_EVIDENCE_TMP/evidence-bundle.json" \
  --parity-comparison "$ADI_EVIDENCE_TMP/parity-comparison.json" \
  --expected-start-date "<YYYY-MM-DD>" \
  --expected-end-date "<YYYY-MM-DD>" \
  --format json \
  > "$ADI_EVIDENCE_TMP/evidence-validation.json"
```

Do not start G10 unless the validator returns `readiness_status="pass"` and `blocker_count=0`.
The resulting `evidence-validation.json` must identify the same report ID, template key, custom
date range, and preview hash used by the G2-G9 run record.
It must also pass the diagnostics `source_health` check so G8 support proof includes
stored-aggregate/no-live-provider guardrails, Meta credential state, Page connection state,
Airbyte state, stored row counts, and recommended next actions.

## Execution Order

### 0. Generate The Combined Fixed-Range Evidence Bundle

Detailed packets:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g2-g3-coverage-retained-history-proof.md`
- `docs/project/evidence/dashthis-replacement/2026-06-16-g4-g5-render-export-reproducibility-proof.md`
- `docs/project/evidence/dashthis-replacement/2026-06-16-g6-parity-worksheet-proof.md`
- `docs/project/evidence/dashthis-replacement/2026-06-16-g7-g8-delivery-diagnostics-proof.md`
- `docs/project/evidence/dashthis-replacement/2026-06-16-g9-safety-controls-proof.md`

Command shape:

```bash
backend/.venv/bin/python backend/manage.py slb_report_evidence_bundle \
  --report-id <report-id> \
  --start-date <YYYY-MM-DD> \
  --end-date <YYYY-MM-DD> \
  > "$ADI_EVIDENCE_TMP/evidence-bundle.json"
```

Record:

- `schema_version == "slb_evidence_bundle.v1"`.
- Report ID, template key, catalog schema version, date range, and preview hash.
- Rendering summary: page count, widget count, ordered page IDs/titles, and per-page widget states.
- Coverage summary and diagnostics dataset rows for the same custom date range.
- Diagnostics `source_health`: stored-aggregate/no-live-provider flags, Meta credential health,
  Page connection health, Airbyte health, stored row counts, and recommended next actions.
- Export summary: export job IDs, formats, statuses, non-empty artifact byte counts where available,
  preview hashes, snapshot preview hashes, and sanitized delivery status.
- Parity row count and `blocked_missing_dashthis_value` rows for manual DashThis/source comparison.
- Audit evidence for `report_evidence_bundle_generated`.

Stop condition:

- The bundle date range does not match G1.
- The diagnostics date range differs from the preview date range.
- Export metadata leaks recipient emails, provider tokens, raw provider payloads, raw user-level
  identifiers, or unsafe artifact paths.
- The bundle output is used as a substitute for missing DashThis/source values, screenshots,
  artifact downloads, reviewer approvals, or the hardening window.

### 1. Capture Preview Coverage For G2/G3

Detailed packet:

`docs/project/evidence/dashthis-replacement/2026-06-16-g2-g3-coverage-retained-history-proof.md`

Command shape:

```bash
curl -fsS \
  -H "Authorization: Bearer <operator-token>" \
  -H "Content-Type: application/json" \
  -X POST \
  "<backend-url>/api/reports/<report-id>/preview/" \
  -d '{
    "date_range": "custom",
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD"
  }'
```

Record:

- Preview hash.
- Export readiness.
- Coverage summary by dataset.
- `paid_meta_ads`, `organic_facebook_page`, and `content_ops` row counts.
- Covered start/end dates.
- Fresh/stale/partial/missing/disconnected states.
- Blocking reasons and warnings.

Stop condition:

- Any required non-Instagram dataset is missing, wrong-tenant, demo/default, or live-provider-backed
  without an explicit Raj/Mira-approved exception.

Local Airbyte destination check, when using the local Airbyte workspace:

```bash
python3 scripts/check_local_airbyte_destination.py \
  --connection-id <airbyte-connection-id> \
  --run-airbyte-check \
  --format json \
  > "$ADI_EVIDENCE_TMP/local-airbyte-destination-check.json"
```

Equivalent backend/frontend plus local Airbyte destination healthcheck:

```bash
scripts/dev-healthcheck.sh \
  --airbyte-connection-id <airbyte-connection-id>
```

Use the healthcheck shortcut when the evidence step needs one local preflight proving app
reachability plus Airbyte destination readiness. It does not trigger a live provider sync.

Record:

- `valid`.
- Redacted destination host/port/database/schema/username.
- Airbyte destination-check status.
- Any mismatch between expected local Postgres target and Airbyte destination config.

Stop condition:

- `valid` is false.
- Destination check is not `succeeded`.
- The output exposes password, token, raw connector logs, or provider payload values.

History probe command shape:

```bash
backend/.venv/bin/python backend/manage.py slb_report_history_probe \
  --report-id <report-id> \
  --primary-start-date <YYYY-MM-DD> \
  --primary-end-date <YYYY-MM-DD> \
  --history-start-date <YYYY-MM-DD> \
  --history-end-date <YYYY-MM-DD> \
  > "$ADI_EVIDENCE_TMP/history-probe.json"
```

Record:

- Primary-month dataset status, row count, and retained range.
- 90-day retained-history dataset status, row count, and retained range.
- `decision` for `paid_meta_ads`, `organic_facebook_page`, and `content_ops`.
- `source_health` credential, Page connection, Airbyte, stored asset, and stored row summaries.
- `source_health.recommended_next_actions` for reauth, sync repair, Page/Post backfill, and
  Content Ops snapshot gaps.
- Any `blocked_retained_history` or `blocked_no_aggregate_rows` row as a G2/G3 blocker.
- Any `meta_credentials.has_reauth_required`, Airbyte sync failure category, missing Page rows,
  missing post rows, or missing Content Ops rows as a G2/G3/G8 blocker or operator action.

### 2. Capture Diagnostics For G2/G3 And G8

Detailed packets:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g2-g3-coverage-retained-history-proof.md`
- `docs/project/evidence/dashthis-replacement/2026-06-16-g7-g8-delivery-diagnostics-proof.md`

Command shape:

```bash
curl -fsS \
  -H "Authorization: Bearer <operator-token>" \
  "<backend-url>/api/reports/<report-id>/diagnostics/"
```

Record:

- Dataset status.
- Retained range for monthly and 90-day proof.
- Aggregate row counts.
- Source label.
- Last successful sync where available.
- Export history summary.
- Blocking reasons.
- Recommended next action.
- Alignment with the history probe `source_health` summary so support can distinguish Meta auth,
  Airbyte sync, retained warehouse rows, Page Insights rows, post rows, and Content Ops snapshots.

Stop condition:

- Diagnostics include secrets, raw provider payloads, user-level rows, unredacted recipient data, or
  unsafe account/Page identifiers.

### 3. Generate ADinsights-Side Parity Rows For G6

Detailed packet:

`docs/project/evidence/dashthis-replacement/2026-06-16-g6-parity-worksheet-proof.md`

Command shape:

```bash
backend/.venv/bin/python backend/manage.py slb_report_parity_evidence \
  --report-id <report-id> \
  --start-date <YYYY-MM-DD> \
  --end-date <YYYY-MM-DD> \
  --format markdown
```

Record:

- Aggregate-only ADinsights rows.
- Preview hash.
- Coverage status per row.
- Audit evidence that parity generation was recorded, if available.

Then fill the redacted comparison values file and run the comparator. Manual calculations should be
used only as reviewer cross-checks:

- DashThis/source value.
- Tolerance.
- Explanation.

Stop condition:

- Missing DashThis/source values for required non-Instagram metrics remain unresolved.

Comparator command shape after comparison values are filled:

```bash
backend/.venv/bin/python backend/manage.py slb_report_parity_compare \
  --evidence-bundle "$ADI_EVIDENCE_TMP/evidence-bundle.json" \
  --comparison-values "$ADI_EVIDENCE_TMP/comparison-values.json" \
  --format markdown \
  > "$ADI_EVIDENCE_TMP/parity-comparison.md"
```

Record:

- Result summary counts.
- Every `pass`, `fail`, and `blocked_*` row.
- Any row where source reference was redacted.
- Andre/Raj/business approval or blocker decision for every non-pass row.

### 4. Capture Saved Dashboard And SLB Report Rendering For G4

Detailed packet:

`docs/project/evidence/dashthis-replacement/2026-06-16-g4-g5-render-export-reproducibility-proof.md`

Routes:

```text
<frontend-url>/dashboards/saved/<dashboard-id>
<frontend-url>/reports/<report-id>
```

Record:

- Saved `dashboard.v1` evidence, if a fixed dashboard is part of the proof.
- SLB `report.v1` page list.
- Cover, executive summary, paid Meta Ads, organic Facebook/Page, top posts, Content Ops,
  recommendations, and appendix/data notes.
- Coverage notes beside affected widgets and in appendix/data notes.
- Desktop and mobile screenshots or browser evidence.
- Long label/table behavior.

Stop condition:

- Report hides coverage warnings, includes Instagram as v1 parity, or renders from the wrong report
  ID/date range.

### 5. Create And Verify CSV/PDF/PNG Exports For G5

Detailed packet:

`docs/project/evidence/dashthis-replacement/2026-06-16-g4-g5-render-export-reproducibility-proof.md`

Command shape:

```bash
for format in csv pdf png; do
  curl -fsS \
    -H "Authorization: Bearer <operator-token>" \
    -H "Content-Type: application/json" \
    -X POST \
    "<backend-url>/api/reports/<report-id>/exports/" \
    -d "{\"export_format\":\"${format}\"}"
done
```

Record:

- Export job IDs.
- Job status.
- Download response.
- Non-empty byte counts.
- Safe artifact path.
- `report_snapshot`.
- Snapshot generated timestamp.
- Preview hash and snapshot hash match when data has not changed.
- Coverage metadata.

Stop condition:

- Any export is empty, unsafe-path, missing snapshot metadata, missing coverage metadata, or
  inconsistent with the fixed preview hash without explanation.

### 6. Capture Scheduled Delivery Dry-Run For G7

Detailed packet:

`docs/project/evidence/dashthis-replacement/2026-06-16-g7-g8-delivery-diagnostics-proof.md`

Command shape:

```bash
curl -fsS \
  -H "Authorization: Bearer <operator-token>" \
  -H "Content-Type: application/json" \
  -X POST \
  "<backend-url>/api/reports/<report-id>/scheduled-dry-run/" \
  -d '{"export_format":"pdf"}'
```

Record:

- Dry-run export job ID.
- `delivery_status.mode == "dry_run"`.
- Rendered or `blocked_by_coverage` state.
- Proof no client email was sent.
- Sanitized failure reason if blocked.

Stop condition:

- Any real client email is sent, recipient data is exposed, or failure details include secrets/raw
  provider payloads.

### 7. Capture Safety Controls For G9

Detailed packet:

`docs/project/evidence/dashthis-replacement/2026-06-16-g9-safety-controls-proof.md`

Record:

- Permission matrix for report view, preview, diagnostics, export, schedule, edit, and delete.
- Cross-tenant report/export/client/account/Page rejection evidence.
- Audit events for preview, diagnostics, export, blocked export, scheduled dry-run, parity
  generation, and report mutation actions.
- Preview/export/scheduled dry-run quota proof.
- Aggregate-only and redaction proof for preview, diagnostics, export metadata, dry-run metadata,
  parity output, and evidence files.

Stop condition:

- Any cross-tenant leakage, user-level data, secret, raw provider payload, quota bypass, or unsafe
  artifact metadata appears.

### 8. Attach Gates For The Evidence State

Run the gates against the exact code/runtime state used for evidence.

```bash
make backend-lint
make backend-test
make frontend-guardrails
make frontend-lint
make frontend-test
make frontend-build
scripts/dev-healthcheck.sh
# Optional when local Airbyte destination readiness is part of evidence:
scripts/dev-healthcheck.sh --airbyte-connection-id <airbyte-connection-id>
make adinsights-preflight PROMPT="Assess SLB DashThis cancellation-readiness fixed-target evidence"
```

If any gate fails, record it as a blocker in the relevant packet and do not advance to G10
adversarial review until the failure is fixed, waived by the correct reviewer, or explicitly
accepted as a cancellation blocker.

## Evidence Routing

| Goal | Primary packet to update |
| --- | --- |
| G2/G3 | `2026-06-16-g2-g3-coverage-retained-history-proof.md` |
| G4/G5 | `2026-06-16-g4-g5-render-export-reproducibility-proof.md` |
| G6 | `2026-06-16-g6-parity-worksheet-proof.md` |
| G7/G8 | `2026-06-16-g7-g8-delivery-diagnostics-proof.md` |
| G9 | `2026-06-16-g9-safety-controls-proof.md` |
| Overall status | `2026-06-16-slb-cancellation-readiness-goals.md` |
| Main evidence rollup | `2026-06-16-slb-reporting-render-export-parity-evidence.md` |

## Completion Matrix Before G10

Fill this matrix after routing evidence. Any `No` blocks G10.

| Check | Yes/No | Evidence link or note |
| --- | --- | --- |
| All evidence uses the same target environment. | Pending | Pending |
| All evidence uses the same safe tenant/client. | Pending | Pending |
| All evidence uses the same `ReportDefinition.id`. | Pending | Pending |
| All evidence uses the same primary date range. | Pending | Pending |
| `template_key` is `slb_monthly_social_report`. | Pending | Pending |
| `schema_version` is `report.v1`. | Pending | Pending |
| Instagram remains deferred/absent from v1 pass claims. | Pending | Pending |
| G2/G3 coverage/history packet is filled. | Pending | Pending |
| G4/G5 render/export packet is filled. | Pending | Pending |
| G6 parity worksheet is filled or blocker recorded. | Pending | Pending |
| G7/G8 delivery/diagnostics packet is filled. | Pending | Pending |
| G9 safety packet is filled. | Pending | Pending |
| Evidence files passed redaction scan. | Pending | Pending |
| Required gates are attached. | Pending | Pending |
| Reviewer route for any warnings/blockers is recorded. | Pending | Pending |

## Pass To G10

G10 adversarial review can start only after:

- G2-G9 packets all have fixed-range evidence for the same G1 target.
- Any failed or blocked row is converted into a fix, reviewer-approved waiver, evidence note, or
  explicit cancellation blocker.
- No evidence packet contains secrets, raw provider payloads, unredacted recipient data, or
  user-level metrics.
- DashThis remains active.
