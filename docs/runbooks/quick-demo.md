# Quick Demo Runbook

## Purpose

Spin up a fast, repeatable demo of ADinsights using deterministic demo data.

## Prereqs

- Python 3.11+
- Node 18+
- dbt CLI configured for this repo

## Quick start (recommended: backend demo adapter)

1) Generate deterministic demo seed CSVs.

```bash
python scripts/generate_demo_data.py --out dbt/seeds/demo --days 90 --seed 42
```

2) Seed the demo data into the warehouse.

```bash
make dbt-seed-demo
```

3) Start the backend with the demo adapter enabled.

```bash
export ENABLE_DEMO_ADAPTER=1
cd backend
python manage.py runserver 0.0.0.0:8000
```

4) Start the frontend in live API mode.

```bash
cd frontend
VITE_MOCK_MODE=false npm run dev
```

5) In the UI, open the dashboard and toggle "Use demo data". Pick a demo tenant.

## Alternative: frontend-only mock (no backend)

```bash
cd frontend
VITE_MOCK_MODE=true npm run dev
```

This uses the bundled mock payloads in `frontend/public/` for quick UI-only demos.

## What to click

- Home → Campaigns → verify KPIs, trend chart, parish map, and campaign table.
- Creatives → verify creative rows and detail page.
- Budget pacing → verify pacing list and currency formatting.
- Map detail → verify parish hover and tooltip formatting.
- Toggle demo/live and confirm the snapshot indicator updates.

## Troubleshooting

- Demo toggle unavailable: ensure `ENABLE_DEMO_ADAPTER=1` and restart the backend.
- No demo tenants listed: confirm demo CSVs exist under `dbt/seeds/demo/` and rerun `make dbt-seed-demo`.
- Snapshot banner missing: confirm `/api/metrics/combined/` returns `snapshot_generated_at`.

## See also

- `docs/runbooks/demo-data.md` — demo data generator details.
- `docs/runbooks/deployment.md` — full deployment runbook.
