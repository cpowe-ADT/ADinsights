# Data Quality Checklist (v0.1)

Purpose: ensure warehouse outputs stay accurate and safe for tenant reporting.

## Ingestion (Airbyte)

- [ ] Syncs succeed within SLA windows.
- [ ] Cost micros converted to currency (Google Ads).
- [ ] Lookback windows capture late conversions (Meta Insights).
- [ ] No empty syncs without explanation (alert if rows == 0).

## Modeling (dbt)

- [ ] `dbt test` passes with no warnings.
- [ ] Staging models have freshness checks.
- [ ] SCD2 snapshots populate `dbt_valid_from`/`dbt_valid_to`.
- [ ] Tenant isolation present in unique keys and joins.

## Metrics Outputs

- [ ] `vw_dashboard_aggregate_snapshot` aligns with API schema.
- [ ] Currency normalized across aggregates.
- [ ] Null metrics coerced safely (`safe_divide`, coalesce guards).

## API Validation

- [ ] `/api/metrics/combined/` returns data for demo and live tenants.
- [ ] Snapshot timestamp reflects warehouse freshness.
- [ ] Aggregates never expose user-level data (PII policy).
