# G7/G8 Scheduled Delivery And Diagnostics Proof Packet

Date: 2026-06-16
Timezone: America/Jamaica
Goal IDs: G7, G8
Status: evidence protocol prepared; blocked on G1 fixed target/runtime values and G2-G6 proof.

## Purpose

Prove that ADinsights can run a scheduled SLB report delivery dry-run without sending client email,
and that support can diagnose coverage, retained history, export state, and blocking reasons without
reading logs or exposing sensitive data.

This packet does not close G7 or G8. It defines the evidence to collect after the fixed SLB report,
coverage/retention, render/export, and parity proof inputs are established.

## Guardrails

- Dry-run only. Do not send real client email for G7 evidence.
- Use stored aggregate ADinsights data only. No live provider calls at report render/export time.
- Do not expose secrets, provider tokens, raw provider payloads, unredacted recipient lists, ad
  account IDs, Page IDs, or user-level metrics.
- Any real delivery configuration or SES/domain/runtime change requires Raj plus Carlos/Mei, and
  Nina if delivery secrets or sensitive artifacts are involved.

## Inputs Required Before Collection

| Input | Required source | Status |
| --- | --- | --- |
| Target environment/backend URL | G1 fixed target | Pending |
| SLB report ID and template key | G1 fixed target | Pending |
| Fixed report date range | G1 fixed target | Pending |
| Coverage and retained-history proof | G2/G3 | Pending |
| Render/export proof | G4/G5 | Pending |
| Parity worksheet status | G6 | Pending |
| Safe dry-run recipient assumption | Operator/runtime setup | Pending |

## G7 Scheduled Delivery Dry-Run Proof

Endpoint:

- `POST /api/reports/<report-id>/scheduled-dry-run/`

Command:

```bash
curl -fsS \
  -H "Authorization: Bearer <operator-token>" \
  -H "Content-Type: application/json" \
  -X POST \
  "<backend-url>/api/reports/<report-id>/scheduled-dry-run/" \
  -d '{"export_format":"pdf"}'
```

Expected successful dry-run behavior:

- Creates a `ReportExportJob`.
- Uses `metadata.delivery_status.mode == "dry_run"`.
- Initially records `metadata.delivery_status.status == "queued"`.
- After export task completion, records `metadata.delivery_status.status == "rendered"`.
- Records `preview_hash`, `coverage_summary`, and `blocking_reasons`.
- Does not send client email.
- Sanitizes failures.

Expected blocked dry-run behavior:

- Creates a failed `ReportExportJob`.
- Uses `metadata.delivery_status.mode == "dry_run"`.
- Records `metadata.delivery_status.status == "blocked_by_coverage"`.
- Records `blocking_reasons`.
- Does not send client email.

Evidence to capture:

| Evidence item | Required value |
| --- | --- |
| Report ID | Same as G1-G6 |
| Export job ID | Dry-run job ID |
| Export format | Usually `pdf` unless Raj approves another proof format |
| Job status | `completed` or intentionally `failed` with `blocked_by_coverage` |
| `metadata.delivery_status.mode` | `dry_run` |
| `metadata.delivery_status.status` | `rendered` or `blocked_by_coverage` |
| `metadata.preview_hash` | Matches report preview/export snapshot when data has not changed |
| `metadata.coverage_summary` | Same status families as G2/G3 |
| `metadata.blocking_reasons` | Empty for rendered proof; explicit for blocked proof |
| `last_scheduled_at` | Updated by dry-run path |
| Email sent? | Must be `no` for G7 |
| Sanitized failure? | Must be `yes` if failed |

## G8 Diagnostics/Support Proof

Endpoint:

- `GET /api/reports/<report-id>/diagnostics/`

Command:

```bash
curl -fsS \
  -H "Authorization: Bearer <operator-token>" \
  "<backend-url>/api/reports/<report-id>/diagnostics/"
```

Required diagnostic fields:

| Field | Required proof |
| --- | --- |
| `report.id` | Same as G1-G7 |
| `report.schema_version` | `report.v1` |
| `report.template_key` | `slb_monthly_social_report` |
| `date_range` | Matches G1 |
| `datasets[*].dataset` | Includes `paid_meta_ads`, `organic_facebook_page`, and `content_ops` when available |
| `datasets[*].coverage_status` | One of the governed coverage states |
| `datasets[*].freshness_status` | Support-readable state |
| `datasets[*].retained_range` | Start/end dates or explicit missing range |
| `datasets[*].row_count` | Aggregate row count only |
| `datasets[*].source_label` | Safe source label, no raw account/Page IDs |
| `datasets[*].recommended_next_action` | Actionable support instruction |
| `blocking_reasons` | Clear reasons if not export-ready |
| `export_history[*]` | Recent safe export status, format, preview hash, delivery status |
| `preview_error` | Validation errors only; no secrets/raw payloads |

Support scenarios to document:

| Scenario | Expected diagnostic explanation |
| --- | --- |
| Fresh stored data | No action required or normal export-ready state. |
| Stale data | Check last successful sync and rerun stored-data sync if needed. |
| Partial history | Review retained history before approving export/delivery. |
| Source disconnected with history | Reconnect source; retained history can support limited reporting only with visible notes. |
| Missing history | Confirm backfill/upload fallback before claiming DashThis parity. |
| Not previously synced | Complete first sync before using this section in parity evidence. |
| Permission missing | Review source permissions and account/Page access. |
| Unsupported metric | Remove metric or add to governed catalog after review. |

## Redaction Checklist

Before attaching diagnostics or dry-run evidence, confirm:

- No OAuth tokens or provider credentials.
- No raw provider JSON payloads.
- No user-level metrics, comments, profiles, or engagement rows.
- No unredacted recipient lists.
- No raw ad account IDs or Page IDs unless explicitly approved for internal evidence.
- No filesystem paths outside safe artifact/evidence paths.
- Failure messages are sanitized and limited to safe error classes/reasons.

## Pass Rules

G7 can pass only when:

- A dry-run job exists for the fixed G1 report/date range.
- It records `delivery_status.mode == "dry_run"`.
- It either renders successfully or blocks clearly by coverage.
- It proves no client email was sent.
- It records safe preview/coverage/delivery metadata.
- Reviewer route is complete.

G8 can pass only when:

- Diagnostics are captured for the fixed G1 report/date range.
- Support can explain each dataset state without logs.
- Diagnostics include retained range, row count, source label, export history, blocking reasons, and
  recommended next action.
- Diagnostics contain no secrets, raw provider payloads, user-level metrics, or sensitive identifiers.
- Omar/Hannah approve support clarity and Sofia approves tenant-safe aggregate-only payloads.

## Current Implementation Evidence

Local backend regression coverage now verifies a scheduled report dry-run can render an artifact
without sending client email:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_scheduled_report_dry_run_completion_marks_rendered_without_email
```

Result: `1 passed`.

The regression creates an SLB `report.v1` scheduled dry-run, runs the export task synchronously,
verifies a non-empty artifact, and asserts `metadata.delivery_status` transitions from queued to:

```json
{
  "mode": "dry_run",
  "status": "rendered",
  "sanitized": true
}
```

It also monkeypatches the email sender to fail if called and verifies dry-run metadata does not
include recipient email values or `delivery_emails`.

Local backend regression coverage now verifies coverage-blocked scheduled dry-runs create sanitized
failed evidence jobs without enqueueing export rendering:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_scheduled_report_dry_run_blocks_by_coverage_without_enqueueing_export
```

Result: `1 passed`.

The regression marks an SLB widget as `require_full_coverage`, confirms the dry-run job is
`failed`, records `metadata.delivery_status.status == "blocked_by_coverage"`, preserves blocking
reasons, leaves `artifact_path` empty, updates `last_scheduled_at`, and verifies recipient email
values are absent from metadata.

Local backend regression coverage now verifies diagnostics do not treat manually authored
`report_section` widgets or zero-count placeholders as retained dataset history:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_report_preview_returns_ordered_report_v1_pages \
  backend/tests/test_phase2_api.py::test_report_diagnostics_returns_aggregate_dataset_status
```

Result: `2 passed`.

For an SLB `report.v1`, diagnostics now report `coverage_status == "missing_history"`,
`row_count == 0`, and `retained_range == {"start_date": null, "end_date": null}` for empty
`content_ops` coverage. The same regression seeds stored warehouse coverage and verifies
`paid_meta_ads.last_successful_sync_at` is populated from the stored snapshot timestamp instead of
being hard-coded to `null`. The broader reporting slice and canonical backend gate also passed:

```bash
backend/.venv/bin/pytest -q backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py
make backend-lint && make backend-test
```

These checks strengthen G7/G8 implementation evidence. They do not close fixed-target diagnostics
proof or scheduled delivery dry-run proof for the G1 report/date range.

## Reviewer Route

- Omar: stale/disconnected/missing-history support states and operational diagnosis.
- Hannah: support clarity, evidence readability, runbook/actionability.
- Sofia: backend diagnostics payload, tenant scoping, aggregate-only behavior.
- Raj/Mira: required if dry-run or diagnostics behavior changes cancellation gates or architecture.
- Carlos/Mei: required only if real delivery runtime, artifact storage, or deployment behavior changes.
- Nina: required if recipient handling, artifacts, or diagnostics evidence may expose sensitive data.

## Current Decision

G7 and G8 are not passed. The runtime paths exist, but fixed-range dry-run and diagnostics evidence
still needs to be captured for the G1 SLB report after G2-G6 evidence is available.

DashThis cancellation remains no-go.
