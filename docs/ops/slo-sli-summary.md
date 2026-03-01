# SLO/SLI Summary (v0.1)

Purpose: quick reference for availability, freshness, and task reliability goals.
Detailed metrics live in `docs/ops/slo-sli.md`.

## Core SLOs

- API availability: 99.9% monthly.
- Snapshot freshness: < 60 minutes for active tenants.
- Airbyte sync success rate: ≥ 99% weekly.
- dbt run success rate: ≥ 99% weekly.

## Key SLIs

- API 5xx rate.
- Snapshot age in minutes.
- Sync job success/failure counts.
- dbt run duration and failure counts.

## Ownership

Ops: Omar (primary), Hannah (backup).
