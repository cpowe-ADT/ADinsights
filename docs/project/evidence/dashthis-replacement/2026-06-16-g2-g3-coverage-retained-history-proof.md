# G2/G3 Stored Coverage And Retained-History Proof Packet

Date: 2026-06-16
Timezone: America/Jamaica
Goal IDs: G2, G3
Status: evidence protocol prepared; blocked on G1 fixed target/runtime values.

## Purpose

Prove that the SLB monthly report can render from stored aggregate ADinsights data for the fixed G1
report/date range, and separately prove whether the same datasets have enough retained history for
monthly and 90-day reporting.

This packet does not close G2 or G3. It defines the exact evidence to collect once G1 records the
target environment, tenant/client, report ID, date range, account/Page scope, and Instagram deferral.

## Guardrails

- Use stored aggregate ADinsights data only.
- Do not call Meta/Facebook/Google/DashThis provider APIs at report preview/export time.
- Do not expose user-level metrics, raw provider payloads, OAuth tokens, recipient email lists, ad
  account IDs, Page IDs, or secrets in this evidence packet.
- Keep Instagram deferred for v1 unless a separate reviewed readiness packet proves source rows,
  scopes, catalog entries, and approval.
- Treat demo, upload-only, wrong-tenant, or default snapshots as blockers for DashThis cancellation
  unless explicitly labeled as fallback evidence and approved by Raj/Mira.

## Inputs Required From G1

| Input | Required before collection | Notes |
| --- | --- | --- |
| Target environment | Yes | Prevents mixing local/staging/production proof. |
| Safe tenant/client identifier | Yes | Use redacted or internal-safe labels. |
| `ReportDefinition.id` | Yes | Required for preview, diagnostics, export, and parity commands. |
| `template_key` | Yes | Expected: `slb_monthly_social_report`. |
| Primary monthly date range | Yes | Recommended default: 2026-05-01 through 2026-05-31. |
| 90-day retained-history range | Yes | Recommended default if May 2026 is confirmed: 2026-03-03 through 2026-05-31. |
| Account/Page scope | Yes | Record safely; do not paste raw account/Page IDs if sensitive. |
| Source comparison owner | Yes for G6 | G2/G3 can collect ADinsights coverage first, but parity cannot pass without comparison values. |

## Datasets To Prove

| Dataset | Required for v1 | Stored-data source expected | G2 coverage proof | G3 retention proof | Reviewer route |
| --- | --- | --- | --- | --- | --- |
| `paid_meta_ads` | Yes | `TenantMetricsSnapshot` warehouse aggregate metrics, with upload fallback only if explicitly labeled | Coverage status, source label, row count, requested/covered dates, freshness, snapshot timestamp | Monthly and 90-day retained range from coverage/diagnostics; route to dbt if not provable | Sofia, Andre; Priya/Martin if warehouse retention gap |
| `organic_facebook_page` | Yes | Stored `MetaInsightPoint` and `MetaPostInsightPoint` rows | Coverage status, source label, row count, requested/covered dates, page scope, freshness | Monthly and 90-day retained range from diagnostics; route to Meta/Page ops if source rows absent | Sofia, Andre, Omar; Maya/Leo only if sync/backfill behavior changes |
| `content_ops` | Yes | Stored Content Ops aggregate records/snapshots and published-post counts | Coverage status, source label, row count, requested/covered dates, freshness | Monthly and 90-day retained range from diagnostics | Sofia, Andre, Omar |
| `organic_instagram` | No in v1 | Deferred | Must remain absent from pass claims | Must remain absent from pass claims | Raj/Mira required before adding |

## Evidence Collection Commands

Use the confirmed G1 values. Store outputs as summarized/redacted evidence, not raw secrets.

### 0. Monthly And 90-Day History Probe

Run the retained-history probe before copying values into the monthly and 90-day tables:

```bash
backend/.venv/bin/python backend/manage.py slb_report_history_probe \
  --report-id <report-id> \
  --primary-start-date <YYYY-MM-DD> \
  --primary-end-date <YYYY-MM-DD> \
  --history-start-date <YYYY-MM-DD> \
  --history-end-date <YYYY-MM-DD>
```

Capture:

- `schema_version == "slb_history_probe.v1"`
- `probes.primary_month.date_range`
- `probes.retained_90_day.date_range`
- primary and retained-history `preview_hash`
- dataset matrix rows for `paid_meta_ads`, `organic_facebook_page`, and `content_ops`
- primary and history status, row count, retained range, and decision per dataset
- audit event `report_history_probe_generated`

The command is an evidence collector only. A `blocked_retained_history` or
`blocked_no_aggregate_rows` decision remains a cancellation blocker until reviewed and resolved.

### 1. Report Preview Coverage

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

Capture:

- `report.id`
- `report.template_key`
- `date_range`
- `preview_hash`
- `export_ready`
- `coverage_summary.by_status`
- `coverage_summary.datasets[*].dataset`
- `coverage_summary.datasets[*].statuses`
- `coverage_summary.datasets[*].row_count`
- `coverage_summary.datasets[*].covered_start_date`
- `coverage_summary.datasets[*].covered_end_date`
- `coverage_summary.datasets[*].source_label`
- `coverage_summary.datasets[*].notes`
- `blocking_reasons`
- `warnings`

### 2. Support Diagnostics

```bash
curl -fsS \
  -H "Authorization: Bearer <operator-token>" \
  "<backend-url>/api/reports/<report-id>/diagnostics/"
```

Capture:

- `datasets[*].dataset`
- `datasets[*].coverage_status`
- `datasets[*].freshness_status`
- `datasets[*].retained_range.start_date`
- `datasets[*].retained_range.end_date`
- `datasets[*].row_count`
- `datasets[*].source_label`
- `datasets[*].last_successful_sync_at`
- `datasets[*].recommended_next_action`
- `export_ready`
- `preview_hash`
- `preview_error`

### 3. ADinsights-Side Parity Rows

This command is primarily for G6, but its coverage summary helps cross-check G2/G3.

```bash
backend/.venv/bin/python backend/manage.py slb_report_parity_evidence \
  --report-id <report-id> \
  --start-date YYYY-MM-DD \
  --end-date YYYY-MM-DD \
  --format markdown
```

Capture:

- `preview_hash`
- `export_ready`
- aggregate-only rows for paid Meta Ads, organic Facebook/Page, and Content Ops
- coverage status per row

Do not mark G6 passed until DashThis/source values, deltas, tolerances, pass/fail, and explanations
are added.

## Monthly Proof Table

Fill this table for the confirmed G1 monthly range.

| Dataset | Requested range | Covered range | Row count | Coverage status | Freshness status | Source label | Result | Notes/reviewer |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- |
| `paid_meta_ads` | TBD | TBD | TBD | TBD | TBD | TBD | Pending | Sofia/Andre |
| `organic_facebook_page` | TBD | TBD | TBD | TBD | TBD | TBD | Pending | Sofia/Andre/Omar |
| `content_ops` | TBD | TBD | TBD | TBD | TBD | TBD | Pending | Sofia/Andre/Omar |

Result values:

- `pass`: requested range is fully covered by stored aggregate data, with no unreviewed fallback.
- `pass_with_warning`: report can render from retained history, but stale/disconnected/partial state
  must be visible in report preview and export metadata.
- `blocked`: missing history, not previously synced, permission missing, unsupported metric, or
  wrong source/tenant/account/page.

## 90-Day Retained-History Proof Table

Fill this table for the confirmed 90-day range. If May 2026 is confirmed, use 2026-03-03 through
2026-05-31 unless Raj/Mira approve a different retained-history window.

| Dataset | Requested range | Covered range | Row count | Coverage status | History status | Source label | Result | Retention owner |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- |
| `paid_meta_ads` | TBD | TBD | TBD | TBD | TBD | TBD | Pending | Andre; Priya/Martin if warehouse gap |
| `organic_facebook_page` | TBD | TBD | TBD | TBD | TBD | TBD | Pending | Andre/Omar |
| `content_ops` | TBD | TBD | TBD | TBD | TBD | TBD | Pending | Andre/Omar |

## Pass/Block Rules

G2 stored data coverage can pass only when:

- `paid_meta_ads`, `organic_facebook_page`, and `content_ops` appear in `coverage_summary.datasets`.
- Each dataset has non-zero stored aggregate rows for the confirmed monthly range.
- `covered_start_date` and `covered_end_date` fully cover the requested monthly range, or any gap is
  explicitly classified and approved as `pass_with_warning`.
- `source_label` identifies stored ADinsights data, not live provider calls.
- `blocking_reasons` are empty for cancellation-proof widgets, or each blocker is logged as a
  cancellation blocker.
- Diagnostics and preview hashes agree for the same report/date range.
- Evidence contains no secrets, raw provider payloads, or user-level metrics.

G3 retained-history proof can pass only when:

- Monthly and 90-day ranges are evaluated separately.
- Each active v1 dataset is classified as `fresh`, `stale`, `partial`, `source_disconnected`,
  `missing_history`, `not_previously_synced`, `permission_missing`, or `unsupported_metric`.
- Missing or partial history is not silently treated as full DashThis parity.
- Any warehouse/mart retention gap is routed to Priya/Martin instead of being fixed ad hoc in this
  evidence step.
- Any source disconnect/backfill/sync behavior change is routed to Maya/Leo and Raj/Mira before
  runtime implementation.

## Current Implementation Evidence

Local backend regression coverage now verifies that `report.v1` narrative sections do not inflate
dataset-level coverage or retained-history proof:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_report_preview_returns_ordered_report_v1_pages \
  backend/tests/test_phase2_api.py::test_report_diagnostics_returns_aggregate_dataset_status
```

Result: `2 passed`.

The regression asserts that a default SLB report with no stored Content Ops aggregate rows reports
`content_ops` as `missing_history`, with `row_count == 0` and no retained start/end range, even
though the report also includes manually authored cover, recommendations, and appendix sections.
The broader reporting slice and canonical backend gate also passed:

```bash
backend/.venv/bin/pytest -q backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py
make backend-lint && make backend-test
```

This strengthens implementation readiness for G2/G3 coverage semantics. It does not close fixed
runtime coverage or 90-day retained-history proof.

Local backend regression coverage now also verifies the monthly and 90-day retained-history probe:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_slb_report_history_probe_command_outputs_monthly_and_90_day_matrix
```

Result: `1 passed`.

The regression asserts that `slb_report_history_probe` emits `slb_history_probe.v1`, includes
separate primary-month and retained-90-day custom date ranges, builds a matrix for
`paid_meta_ads`, `organic_facebook_page`, and `content_ops`, preserves stored paid aggregate row
counts where available, keeps missing organic/content history blocked, stores redacted audit
metadata only, excludes injected token values, and completes while live network/provider calls are
blocked.

This strengthens G2/G3 evidence collection quality. It does not close fixed-runtime coverage or
90-day retained-history proof until run against the approved G1 report/date ranges.

## Reviewer Route

- Sofia: backend report preview/diagnostics payload safety and tenant scoping.
- Andre: metric correctness, coverage status semantics, stored snapshot/page/content row checks.
- Omar: stale, disconnected, missing-history, and support recommended-next-action clarity.
- Hannah: evidence packet clarity and support-safe redaction.
- Priya/Martin: required only if 90-day/monthly history cannot be proven from current stored data or
  needs dbt/mart retention changes.
- Raj/Mira: required if proof exposes cross-stream architecture, retention, schema, or cancellation
  gate changes.

## Current Decision

G2 and G3 are not passed. The evidence collection protocol is ready, but fixed-runtime proof is
blocked until G1 supplies the confirmed target environment, report ID, tenant/client, date range,
account/Page scope, and Instagram deferral.

DashThis cancellation remains no-go.
