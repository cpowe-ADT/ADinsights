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

| Metric | Default threshold | Notes |
| ------ | ----------------- | ----- |
| Spend | Drift <= 1.0% | Confirm currency and tax/fee handling. |
| Impressions | Drift <= 2.0% | Check platform/date filters first. |
| Clicks | Drift <= 2.0% | Check link clicks vs clicks semantics. |
| Conversions | Drift <= 2.0% | Subject to attribution lag and conversion-window differences. |
| CTR/CPC/CPM/CPA/ROAS | Derived from accepted raw metric totals | Recalculate after raw metrics pass. |

## Meta Ads Totals

| Metric | Meta source total | ADinsights total | Drift | Pass/fail | Notes |
| ------ | ----------------- | ---------------- | ----- | --------- | ----- |
| Spend | TBD | TBD | TBD | TBD | TBD |
| Impressions | TBD | TBD | TBD | TBD | TBD |
| Clicks | TBD | TBD | TBD | TBD | TBD |
| Conversions | TBD | TBD | TBD | TBD | TBD |
| Reach | TBD | TBD | TBD | TBD | Only required if the DashThis report uses it. |

## Organic Facebook/Page Totals

| Metric | Source total | ADinsights total | Drift | Pass/fail | Notes |
| ------ | ------------ | ---------------- | ----- | --------- | ----- |
| Page reach | TBD | TBD | TBD | TBD | Confirm metric naming and date semantics. |
| Page impressions/views | TBD | TBD | TBD | TBD | Confirm whether DashThis uses views or impressions. |
| Page engagements/interactions | TBD | TBD | TBD | TBD | Confirm action family. |
| Link clicks/actions | TBD | TBD | TBD | TBD | Confirm click/action semantics. |
| Follows/fans | TBD | TBD | TBD | TBD | Confirm daily delta vs period-end fan count. |

## Content Ops Totals

| Metric | Source total | ADinsights total | Drift | Pass/fail | Notes |
| ------ | ------------ | ---------------- | ----- | --------- | ----- |
| Published posts | TBD | TBD | TBD | TBD | Should match internal aggregate counts unless manually reconciled. |
| Scheduled posts | TBD | TBD | TBD | TBD | Confirm schedule timezone. |
| Approved items | TBD | TBD | TBD | TBD | Confirm approval state inclusion. |
| Content items created | TBD | TBD | TBD | TBD | Confirm item type scope. |

## Google Ads Totals

| Metric | Google Ads source total | ADinsights total | Drift | Pass/fail | Notes |
| ------ | ----------------------- | ---------------- | ----- | --------- | ----- |
| Spend | TBD | TBD | TBD | TBD | Convert cost micros to currency. |
| Impressions | TBD | TBD | TBD | TBD | TBD |
| Clicks | TBD | TBD | TBD | TBD | TBD |
| Conversions | TBD | TBD | TBD | TBD | Confirm conversion action scope. |

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

## Comparison Decision

- Raw totals pass:
- Derived metrics pass:
- Known acceptable differences:
- Blocking differences:
- Next action:
