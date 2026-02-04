# Demo data runbook

## Purpose

Generate deterministic demo data for dashboards without connecting to ad APIs.

## Prereqs

- Python 3.11+
- Faker installed (included in backend dependencies).
- dbt CLI configured for this repo.

## Quick start

1) Generate demo seed CSVs (deterministic).

```bash
python scripts/generate_demo_data.py --out dbt/seeds/demo --days 90 --seed 42
```

2) Load the seed tables into the warehouse.

```bash
make dbt-seed-demo
```

3) Enable the demo adapter and start the backend.

```bash
export ENABLE_DEMO_ADAPTER=1
```

4) In the UI, use the "Use demo data" toggle and pick a demo tenant.

## Optional synth path

To write to `dbt/seeds/synth_adinsights` instead of the default demo seed path:

```bash
python scripts/generate_synth_adinsights_data.py --days 90 --seed 42
```

## Validation

Run a quick smoke check to regenerate data and seed dbt.

```bash
make demo-smoke
```

## Troubleshooting

- Demo toggle shows "unavailable": confirm `ENABLE_DEMO_ADAPTER=1` and restart the backend.
- Demo data missing: rerun the generator and `make dbt-seed-demo`.
- Demo tenants list is empty: verify `DEMO_SEED_DIR` (defaults to `dbt/seeds/demo`) and that CSVs exist.
- Want fresh timestamps: pass a newer anchor date.

```bash
python scripts/generate_demo_data.py --end-date 2024-12-31
```

## Notes

- The demo generator uses a fixed RNG seed and a fixed default end date for deterministic outputs.
- One tenant is seeded with a deliberately older snapshot timestamp to exercise stale banners.
