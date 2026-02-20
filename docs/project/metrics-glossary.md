# Metrics Glossary (v0.1)

Purpose: align definitions across frontend, backend, dbt, and BI.

## Core Metrics

- **Spend**: total media cost in tenant currency.
- **Impressions**: total ad impressions.
- **Clicks**: total ad clicks.
- **Conversions**: total reported conversions.
- **ROAS**: conversions divided by spend (see attribution window notes in dbt).
- **CTR**: clicks / impressions.
- **CPC**: spend / clicks.
- **CPM**: spend / (impressions / 1000).

## Notes

- Always use aggregated metrics; never user-level data.
- Currency normalization is handled in dbt staging.
