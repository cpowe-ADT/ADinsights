# Aggregate Snapshot API Contract

The `/api/dashboards/aggregate-snapshot/` endpoint wraps the dbt aggregates that back the
multi-tenant dashboard experience. This document pairs with the machine-readable schema in
[`aggregate_snapshot.schema.json`](./aggregate_snapshot.schema.json) so backend services and
frontend normalisers stay aligned on the payload.

## Payload overview

| Section     | Purpose                                                                                    | Source                                    |
| ----------- | ------------------------------------------------------------------------------------------ | ----------------------------------------- |
| `summary`   | Tenant-level totals and rate metrics derived from campaign-level aggregates.               | `dbt/models/marts/agg_campaign_daily.sql` |
| `campaigns` | Row-level campaign rollups scoped by platform and ad account to maintain tenant isolation. | `dbt/models/marts/agg_campaign_daily.sql` |
| `parishes`  | Geographic aggregates used to populate the parish table and map widgets.                   | `dbt/models/marts/agg_parish_daily.sql`   |
| `filters`   | Distinct platform and ad account values exposed to downstream clients for filtering.       | `agg_campaign_daily` distinct dimensions  |

Top-level fields:

- `generatedAt` — ISO-8601 timestamp representing when the snapshot was assembled.
- `summary` — uses the same metric macros (`metric_ctr`, `metric_conversion_rate`, etc.) as other
  marts to ensure consistent rate calculations and rounding.
- `campaigns` — payload rows mirror the structure already consumed by
  `frontend/src/state/useDashboardStore.ts` so the dashboard store can normalise the response without
  additional mapping.
- `parishes` — extends the existing parish aggregates with `campaignCount` and `roas` so both
  the heatmap and summary cards can reuse the same contract.
- `filters` — distinct `sourcePlatforms` and `adAccountIds` derived from the latest campaign
  snapshot to keep tenant scoping explicit.

## Field reuse and naming

- Spend, impression, click, conversion, CTR, conversion rate, CPC, CPA, CPM, and ROAS values reuse the
  metric macros in `dbt/macros/metrics/` to avoid drift between marts and contract projections.
- `campaignCount` and `parishCount` are counts of distinct campaign identifiers grouped at the
  parish level and rolled up for the summary, enabling UI filter pills to display accurate totals.
- Geographic fields (`parishCode`, `parishName`, `regionName`) reuse the enrichment performed in
  `dim_campaign` so the contract stays aligned with the map lookups.
- Currency is currently fixed to the tenant’s reporting currency (JMD). Once multi-currency support is
  available, update the summary currency wiring and schema enum in tandem.

## Change management

Any change to the payload must:

1. Update the JSON schema to reflect the new structure or fields.
2. Extend the dbt contract test (`aggregate_snapshot_contract`) so CI fails before SQL or API code ships
   a breaking change.
3. Communicate the change in the dashboard runbooks under `docs/ops/` so on-call responders know how to
   validate the new fields when investigating incidents.
