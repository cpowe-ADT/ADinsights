# Data Lineage Map (v0.1)

Purpose: describe the high-level flow of data from ingestion to UI.

## Flow

1. **Airbyte** ingests raw platform data into the warehouse.
2. **dbt** models staging and marts, applying SCD2 and metrics logic.
3. **Backend** aggregates and serves `/api/metrics/combined/`.
4. **Frontend** consumes API and renders dashboards, tables, and maps.

## Notes

- Tenant isolation enforced at each layer.
- Aggregated metrics only (PII policy).
