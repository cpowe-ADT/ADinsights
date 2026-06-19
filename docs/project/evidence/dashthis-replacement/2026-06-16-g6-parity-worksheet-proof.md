# G6 SLB Parity Worksheet Proof Packet

Date: 2026-06-16
Timezone: America/Jamaica
Goal ID: G6
Status: evidence protocol prepared; blocked on G1 fixed target values, G2/G3 coverage proof, and
DashThis/source comparison values.

## Purpose

Complete a fixed-range parity worksheet that compares ADinsights aggregate values against
DashThis/source-platform values for the same SLB report, date range, tenant/client, account/Page
scope, timezone, and currency.

This packet does not close G6. It defines the worksheet, calculations, tolerances, source evidence,
and review route required before DashThis cancellation can be considered.

## Required Preconditions

| Precondition | Required source | Status |
| --- | --- | --- |
| G0 Raj/Mira review route | `2026-06-16-g0-raj-mira-review-packet.md` | Pending human review |
| Fixed SLB target/date range | `2026-06-16-g1-fixed-slb-proof-target.md` | Pending operator/runtime values |
| Stored coverage and retained history | `2026-06-16-g2-g3-coverage-retained-history-proof.md` | Pending runtime proof |
| Report render/export evidence | `2026-06-16-g4-g5-render-export-reproducibility-proof.md` | Pending runtime proof |
| DashThis/source values owner | Operator/business owner | Pending |
| Instagram defer confirmation | G1 | Pending |

G6 can start producing ADinsights-side rows before all preconditions are passed, but it cannot pass
until the fixed report/date range and comparison values are recorded.

## Data Source Rules

- ADinsights values must come from `backend/manage.py slb_report_parity_evidence` for the fixed G1
  report/date range.
- DashThis/source values must be aggregated values copied from DashThis exports, DashThis
  screenshots, Meta Ads Manager, Facebook/Page source reporting, or approved internal Content Ops
  count evidence.
- Do not commit raw source-platform exports, unredacted screenshots, credentials, tokens, ad account
  IDs, Page IDs, recipient emails, or user-level rows.
- Comparison screenshots or exports may be referenced by safe evidence path, owner, timestamp, and
  redacted summary.
- If DashThis and source-platform values disagree, record both and route the discrepancy to Andre
  and Raj before treating either as the source of truth.

## ADinsights Evidence Command

Run with the confirmed G1 report and fixed date range:

```bash
backend/.venv/bin/python backend/manage.py slb_report_parity_evidence \
  --report-id <report-id> \
  --start-date YYYY-MM-DD \
  --end-date YYYY-MM-DD \
  --format markdown
```

Capture:

- `report_id`
- `tenant_id` only if safe/redacted for evidence
- `date_range.start_date`
- `date_range.end_date`
- `preview_hash`
- `export_ready`
- `coverage_summary`
- aggregate-only rows
- audit event `report_parity_evidence_generated`

The command output includes manual columns for DashThis/source values, deltas, tolerances, result,
and explanation. Those columns must be filled before G6 can pass.
Rows without DashThis/source comparison values start with
`result="blocked_missing_dashthis_value"` so the worksheet begins in an explicit blocked state
until comparison values are filled.

## Comparison Values Command

After the evidence bundle and redacted DashThis/source values exist, run the comparator instead of
hand-calculating deltas:

```bash
backend/.venv/bin/python backend/manage.py slb_report_parity_compare \
  --evidence-bundle "$ADI_EVIDENCE_TMP/evidence-bundle.json" \
  --comparison-values "$ADI_EVIDENCE_TMP/comparison-values.json" \
  --format markdown
```

Comparison values input shape:

```json
{
  "schema_version": "slb_comparison_values.v1",
  "source_reference": "redacted DashThis/source evidence reference",
  "rows": [
    {
      "dataset": "paid_meta_ads",
      "widget_id": "paid_summary",
      "metric": "spend",
      "label": "Spend",
      "dashthis_value": 1000,
      "accepted_tolerance_percent": 1.0,
      "explanation": "DashThis May 2026 redacted export."
    }
  ]
}
```

Supported comparison value aliases:

- `dashthis_value`
- `source_value`
- `comparison_value`

Supported tolerance fields:

- `accepted_tolerance_percent`
- `accepted_tolerance_absolute`

Rows without a comparison value remain `blocked_missing_dashthis_value`. Rows with a value but no
approved tolerance become `blocked_metric_semantics`. Source references containing email/token/secret
signals are emitted as `redacted` by the comparator.

Allowed parity results are:

- `pass`
- `fail`
- `blocked_missing_dashthis_value`
- `blocked_missing_source_value`
- `blocked_metric_semantics`

The offline evidence validator rejects unsupported labels such as `waived`, `pending`, or
`manual_ok`, and requires at least one passing row before G6 can advance.
Every `pass` row must include metric identity (`dataset`, `widget_id`, `metric`, `label`), the
ADinsights value, the source/DashThis value, an absolute delta, at least one accepted tolerance, and
an explanation.

The parity comparison output must preserve the same `report.id`, `report.template_key`, and
`preview_hash` as the evidence bundle. The offline evidence validator blocks G6 if the parity
worksheet report identity, date range, or preview hash differs from the fixed bundle used for G2-G5.
It also blocks if `row_count` or `result_summary` does not match the actual `rows` content.

## Calculation Rules

Use these formulas unless Andre/Raj approve an explicit exception:

```text
absolute_delta = adinsights_value - comparison_value
absolute_delta_magnitude = abs(adinsights_value - comparison_value)
percentage_delta = abs(adinsights_value - comparison_value) / max(abs(comparison_value), 1) * 100
```

Derived metrics must be recalculated from accepted raw totals instead of independently accepted:

```text
ctr = clicks / impressions
cpc = spend / clicks
cpm = spend / impressions * 1000
conversion_rate = conversions / clicks
cost_per_conversion = spend / conversions
```

Zero-source rule:

- If the comparison value is `0` and ADinsights is also `0`, result can pass.
- If the comparison value is `0` and ADinsights is non-zero, use absolute delta and explain the
  source/date/filter reason; do not pass by percentage math alone.

Rounding rule:

- Compare unrounded values when available.
- Display rounded values only after pass/fail is calculated.
- Record whether DashThis displayed rounded values only.

## Default Tolerances

These are starting defaults, not automatic approval. Andre/Raj can tighten or override them for the
fixed SLB proof.

| Metric family | Default tolerance | Notes |
| --- | --- | --- |
| Paid spend | `<= 1.0%` | Confirm currency, taxes, fees, refunds, and account filter. |
| Paid impressions/reach/clicks | `<= 2.0%` | Confirm campaign/date/platform filters. |
| Paid conversions | `<= 2.0%` or documented attribution-lag exception | Confirm conversion action and attribution window. |
| Paid CTR/CPC/CPM | Derived from accepted raw paid totals | Do not approve if raw totals fail. |
| Organic Page impressions/reach/engagement/actions | `<= 5.0%` pending Andre approval | Page Insights naming/date semantics may differ from DashThis. |
| Organic follows/fans | `<= 5.0%` pending Andre approval | Confirm whether value is daily delta, unique follows, or end-of-period fan count. |
| Top post rankings | Same top items and order, or documented tie/ranking reason | Compare IDs/titles safely; do not expose user-level engagement. |
| Content Ops counts | Exact match unless manually reconciled | Published/scheduled/approved counts should be deterministic internal totals. |

## Worksheet Header

Fill before any metric comparison:

| Field | Value |
| --- | --- |
| Proof target | SLB / Students' Loan Bureau |
| Report ID | TBD |
| Template key | `slb_monthly_social_report` |
| Date range | TBD |
| Timezone | America/Jamaica unless source evidence proves otherwise |
| Currency | TBD |
| ADinsights preview hash | TBD |
| ADinsights export snapshot hash | TBD |
| DashThis/source evidence owner | TBD |
| DashThis/source evidence path/reference | TBD |
| Instagram treatment | Deferred in v1 |
| Coverage proof reference | `2026-06-16-g2-g3-coverage-retained-history-proof.md` |
| Export proof reference | `2026-06-16-g4-g5-render-export-reproducibility-proof.md` |

## Paid Meta Ads Worksheet

| Metric | ADinsights value | DashThis/source value | Absolute delta | % delta | Tolerance | Result | Explanation |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| Spend | TBD | TBD | TBD | TBD | `<= 1.0%` | Pending | TBD |
| Impressions | TBD | TBD | TBD | TBD | `<= 2.0%` | Pending | TBD |
| Reach | TBD | TBD | TBD | TBD | `<= 2.0%` | Pending | TBD |
| Clicks | TBD | TBD | TBD | TBD | `<= 2.0%` | Pending | TBD |
| CTR | TBD | Derived from accepted raw totals | TBD | TBD | Derived | Pending | TBD |
| CPC | TBD | Derived from accepted raw totals | TBD | TBD | Derived | Pending | TBD |
| CPM | TBD | Derived from accepted raw totals | TBD | TBD | Derived | Pending | TBD |
| Conversions | TBD | TBD | TBD | TBD | `<= 2.0%` or exception | Pending | TBD |

## Organic Facebook/Page Worksheet

| Metric | ADinsights value | DashThis/source value | Absolute delta | % delta | Tolerance | Result | Explanation |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| Page reach | TBD | TBD | TBD | TBD | `<= 5.0%` pending approval | Pending | TBD |
| Page impressions/views | TBD | TBD | TBD | TBD | `<= 5.0%` pending approval | Pending | TBD |
| Page engagements/interactions | TBD | TBD | TBD | TBD | `<= 5.0%` pending approval | Pending | TBD |
| Page actions/link clicks | TBD | TBD | TBD | TBD | `<= 5.0%` pending approval | Pending | TBD |
| Follows/fans | TBD | TBD | TBD | TBD | `<= 5.0%` pending approval | Pending | TBD |

## Top Posts Worksheet

Use safe post labels. Do not paste user-level comments, profile data, or raw engagement payloads.

| Rank | ADinsights post label | DashThis/source post label | Matched? | AD metric | Source metric | Delta | Result | Explanation |
| ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- |
| 1 | TBD | TBD | TBD | TBD | TBD | TBD | Pending | TBD |
| 2 | TBD | TBD | TBD | TBD | TBD | TBD | Pending | TBD |
| 3 | TBD | TBD | TBD | TBD | TBD | TBD | Pending | TBD |
| 4 | TBD | TBD | TBD | TBD | TBD | TBD | Pending | TBD |
| 5 | TBD | TBD | TBD | TBD | TBD | TBD | Pending | TBD |

## Content Ops Worksheet

| Metric | ADinsights value | DashThis/source value | Absolute delta | % delta | Tolerance | Result | Explanation |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| Published posts | TBD | TBD | TBD | TBD | Exact or documented exception | Pending | TBD |
| Scheduled posts | TBD | TBD | TBD | TBD | Exact or documented exception | Pending | TBD |
| Approved items | TBD | TBD | TBD | TBD | Exact or documented exception | Pending | TBD |
| Content items created | TBD | TBD | TBD | TBD | Exact or documented exception | Pending | TBD |

## Result Values

Use one of these exact result values:

- `pass`
- `pass_with_documented_exception`
- `fail`
- `blocked_missing_dashthis_value`
- `blocked_missing_source_value`
- `blocked_coverage`
- `blocked_metric_semantics`
- `not_applicable_v1`

## G6 Pass Rules

G6 can pass only when:

- G1 fixed target values are recorded.
- G2/G3 coverage proof does not block the compared dataset.
- ADinsights-side rows are generated for the fixed range.
- DashThis/source values are filled for every required non-Instagram metric.
- Every row has absolute delta, percentage delta where applicable, tolerance, result, and
  explanation.
- Derived metrics are recalculated from accepted raw totals.
- Every `fail` or `blocked_*` row is either fixed, removed from cancellation scope by Raj/business
  owner, or recorded as a cancellation blocker.
- Andre approves metric semantics and tolerances.
- Raj/business owner approve the parity decision.
- No secrets, raw provider payloads, user-level metrics, or unredacted sensitive screenshots are
  committed.

## Current Implementation Evidence

Local backend regression coverage now verifies the ADinsights-side parity command produces
worksheet-compatible blocked rows before DashThis/source values are filled:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_slb_report_parity_evidence_command_outputs_manual_comparison_rows
```

Result: `1 passed`.

The regression asserts:

- Generated rows have `dashthis_value == null`.
- Generated rows use `result == "blocked_missing_dashthis_value"`.
- Manually authored `report_section` widgets such as cover, recommendations, and appendix data
  notes do not appear as parity rows.
- `report_parity_evidence_generated` audit metadata remains redacted and stores only date range,
  preview hash, row count, and `redacted`.

The broader reporting slice and canonical backend gate also passed:

```bash
backend/.venv/bin/pytest -q backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py
make backend-lint && make backend-test
```

This strengthens G6 implementation evidence for worksheet seed quality. It does not close fixed
target parity because DashThis/source values, deltas, tolerances, explanations, and reviewer
approvals are still missing.

Local backend regression coverage now also verifies the parity comparator computes G6 deltas and
keeps unresolved rows blocked:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/test_phase2_api.py::test_slb_report_parity_compare_command_computes_deltas_and_blocks_missing_values \
  backend/tests/test_phase2_api.py::test_slb_report_parity_compare_command_does_not_call_live_providers
```

Result: `2 passed`.

The regression asserts:

- `slb_report_parity_compare` produces `schema_version == "slb_parity_comparison.v1"`.
- Percent and absolute tolerances produce `pass` or `fail` consistently.
- Rows without comparison values stay `blocked_missing_dashthis_value`.
- Rows with comparison values but no approved tolerance become `blocked_metric_semantics`.
- Sensitive-looking source references are redacted.
- The comparator completes while live network/provider calls are blocked.

The broader reporting slice, `make backend-lint`, and `make backend-test` also passed after adding
the comparator. This strengthens G6 implementation evidence for worksheet calculation quality. It
still does not close fixed-target parity because real DashThis/source values, approved tolerances,
explanations, and reviewer approvals are still missing.

## Reviewer Route

- Andre: metric semantics, source mapping, tolerances, derived-metric recalculation, top-post match
  logic.
- Sofia: ADinsights parity command output, tenant scoping, aggregate-only rows, audit event.
- Raj: fixed-scope parity decision, DashThis cancellation gate, unresolved blockers.
- Business owner/operator: DashThis/source values and acceptance of tolerances/exceptions.
- Hannah: evidence clarity and support-safe redaction.
- Nina: required if screenshots/exports/artifacts may contain sensitive client data.
- Priya/Martin: required if parity mismatch points to warehouse/mart retention or aggregation gaps.

## Current Decision

G6 is not passed. The worksheet protocol is ready, but comparison values, deltas, tolerances,
pass/fail decisions, and reviewer approvals are still missing.

DashThis cancellation remains no-go.
