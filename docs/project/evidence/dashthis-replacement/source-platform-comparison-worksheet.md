# Source Platform Comparison Worksheet

Use this worksheet for Phase 6 parity checks and for any Phase 0 source-total intake. Keep only
aggregated values here. Do not paste credentials, source-platform export files, user-level rows, or
unredacted customer-sensitive screenshots.

For the SLB cancellation-readiness chain, use the SLB-specific G6 packet as the primary worksheet:

`docs/project/evidence/dashthis-replacement/2026-06-16-g6-parity-worksheet-proof.md`

## Comparison Header

- Tenant/client:
- Proof date range:
- Timezone used by source platform:
- Timezone used by ADinsights:
- Currency:
- Meta ad accounts:
- Google Ads customer IDs:
- ADinsights dashboard/report:
- Source evidence reference:
- ADinsights evidence reference:

## Tolerance Defaults

| Metric               | Default threshold                       | Notes                                                         |
| -------------------- | --------------------------------------- | ------------------------------------------------------------- |
| Spend                | Drift <= 1.0%                           | Confirm currency and tax/fee handling.                        |
| Impressions          | Drift <= 2.0%                           | Check platform/date filters first.                            |
| Clicks               | Drift <= 2.0%                           | Check link clicks vs clicks semantics.                        |
| Conversions          | Drift <= 2.0%                           | Subject to attribution lag and conversion-window differences. |
| CTR/CPC/CPM/CPA/ROAS | Derived from accepted raw metric totals | Recalculate after raw metrics pass.                           |

## Meta Ads Totals

| Metric      | Meta source total | ADinsights total | Drift | Pass/fail | Notes                                         |
| ----------- | ----------------- | ---------------- | ----- | --------- | --------------------------------------------- |
| Spend       | TBD               | TBD              | TBD   | TBD       | TBD                                           |
| Impressions | TBD               | TBD              | TBD   | TBD       | TBD                                           |
| Clicks      | TBD               | TBD              | TBD   | TBD       | TBD                                           |
| Conversions | TBD               | TBD              | TBD   | TBD       | TBD                                           |
| Reach       | TBD               | TBD              | TBD   | TBD       | Only required if the DashThis report uses it. |

## Organic Facebook/Page Totals

| Metric                        | Source total | ADinsights total | Drift | Pass/fail | Notes                                               |
| ----------------------------- | ------------ | ---------------- | ----- | --------- | --------------------------------------------------- |
| Page reach                    | TBD          | TBD              | TBD   | TBD       | Confirm metric naming and date semantics.           |
| Page impressions/views        | TBD          | TBD              | TBD   | TBD       | Confirm whether DashThis uses views or impressions. |
| Page engagements/interactions | TBD          | TBD              | TBD   | TBD       | Confirm action family.                              |
| Link clicks/actions           | TBD          | TBD              | TBD   | TBD       | Confirm click/action semantics.                     |
| Follows/fans                  | TBD          | TBD              | TBD   | TBD       | Confirm daily delta vs period-end fan count.        |

## Content Ops Totals

| Metric                | Source total | ADinsights total | Drift | Pass/fail | Notes                                                              |
| --------------------- | ------------ | ---------------- | ----- | --------- | ------------------------------------------------------------------ |
| Published posts       | TBD          | TBD              | TBD   | TBD       | Should match internal aggregate counts unless manually reconciled. |
| Scheduled posts       | TBD          | TBD              | TBD   | TBD       | Confirm schedule timezone.                                         |
| Approved items        | TBD          | TBD              | TBD   | TBD       | Confirm approval state inclusion.                                  |
| Content items created | TBD          | TBD              | TBD   | TBD       | Confirm item type scope.                                           |

## Google Ads Totals

| Metric      | Google Ads source total | ADinsights total | Drift | Pass/fail | Notes                            |
| ----------- | ----------------------- | ---------------- | ----- | --------- | -------------------------------- |
| Spend       | TBD                     | TBD              | TBD   | TBD       | Convert cost micros to currency. |
| Impressions | TBD                     | TBD              | TBD   | TBD       | TBD                              |
| Clicks      | TBD                     | TBD              | TBD   | TBD       | TBD                              |
| Conversions | TBD                     | TBD              | TBD   | TBD       | Confirm conversion action scope. |

## Formula

Use this drift formula unless a source has a documented exception:

```text
drift_percent = abs(adinsights_total - source_total) / max(abs(source_total), 1) * 100
```

For SLB fixed-target parity, prefer the backend comparator after filling a redacted
`slb_comparison_values.v1` JSON file:

```bash
backend/.venv/bin/python backend/manage.py slb_report_parity_compare \
  --evidence-bundle "$ADI_EVIDENCE_TMP/evidence-bundle.json" \
  --comparison-values "$ADI_EVIDENCE_TMP/comparison-values.json" \
  --format markdown
```

The comparator calculates absolute delta, percent delta, tolerance outcome, and result state. It
does not replace reviewer approval or DashThis/source evidence.
Do not enter placeholders such as `NaN`, `Infinity`, `n/a`, or invented zeroes for missing values.
The comparator treats blank strings and placeholders such as `n/a`, `none`, `null`, `tbd`, and `-`
as missing source values; if a numeric fallback field exists on the same row, it uses that fallback,
otherwise the row remains `blocked_missing_source_value`. It treats non-finite values as
non-numeric, and the offline validator blocks any `pass` row with non-finite or non-numeric
ADinsights values, source values, deltas, or tolerances.

When no source export can be found, keep the affected `source_value` fields `null` and record a
redacted `source_search_provenance` array in the comparison-values JSON. The comparator carries that
provenance into `slb_parity_comparison.v1` output so G6 evidence can show which Gmail/Drive/local
searches were checked without exposing tokens, email addresses, or raw secrets.
The offline validator requires that provenance whenever parity rows are
`blocked_missing_source_value`; unresolved source rows without search proof stay blocked even if the
export artifacts are otherwise present. Comparator output also carries `unresolved_row_count`,
`unresolved_summary`, and `unresolved_rows`; validator output mirrors the same audit shape as
`unresolved_parity`. Use that inventory to separate rows that need approved source values from rows
that already have a source value but lack retained ADinsights report data
(`blocked_missing_adinsights_value`).
Every `blocked_missing_source_value` row must also have a matching row-level entry in
`missing_source_values` keyed to the same dataset, widget, and metric, with a concrete `reason`.
This prevents a broad "searched but not found" note from standing in for the per-metric source
accounting required by G6/SLB-004.
If the reviewed source artifact has real aggregate values that do not safely map to current parity
rows, put them in `unmatched_source_values` with a `reason_not_in_parity_rows`; keep unavailable
rows in `missing_source_values`. The comparator carries both arrays into the parity artifact after
sanitizing sensitive-looking text, and the validator mirrors them under `source_value_inventory`.
Those unmatched facts are audit evidence only; they do not count as parity passes.
Blank or placeholder unmatched entries are dropped because they are not source facts.
Every unresolved parity row also includes `recommended_next_action`. Treat that field as an
operator handoff hint, not an approval override: source-missing rows still need approved source
values, source-backed organic rows still need retained/imported ADinsights values and reviewer
semantic confirmation, and no row passes until the comparator calculates an accepted delta.
Comparator and validator output also includes `parity_completion_requirements`. Use this grouped
handoff before assigning the next repair task: it separates selected-account paid source-export
needs, tenant-owned SLB Page prerequisites for organic import, Content Ops source-total needs,
metric/tolerance review, and parity-delta investigation. `can_run_now=false` means the operator must
first satisfy the listed prerequisite, such as reconnecting the selected paid account or selecting
the correct tenant-owned SLB Page.

## Comparison Decision

- Raw totals pass:
- Derived metrics pass:
- Known acceptable differences:
- Blocking differences:
- Next action:
