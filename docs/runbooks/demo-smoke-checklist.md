# Demo Smoke Checklist

Use this checklist to validate the demo experience end-to-end after generating demo data.

## Data + services

- [ ] Demo seed CSVs exist under `dbt/seeds/demo/`.
- [ ] `make dbt-seed-demo` completes without errors.
- [ ] Backend running with `ENABLE_DEMO_ADAPTER=1`.
- [ ] Frontend running with `VITE_MOCK_MODE=false`.
- [ ] `/api/metrics/combined/` returns `snapshot_generated_at`.

## UI smoke

- [ ] Toggle to "Use demo data" and select a demo tenant.
- [ ] Campaign KPIs render non-zero totals; at least one metric shows zero spend.
- [ ] Daily trend chart renders with multiple dates.
- [ ] Parish map renders and tooltips show parish names.
- [ ] Campaign table renders rows and CSV export downloads.
- [ ] Creatives dashboard renders rows and creative detail opens.
- [ ] Budget pacing list renders with projected spend.
- [ ] Snapshot banner shows "Updated X ago" and shows STALE for the stale demo tenant.
- [ ] Empty/error states explain next steps when filters hide data.

## Notes

- Use the "stale" demo tenant to validate freshness banners.
- If any step fails, re-run demo data generation and restart backend/frontend.
