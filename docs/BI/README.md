# BI Configuration Exports

This folder stores version-controlled BI assets used for deployment and
runbook references. The exports are redacted and safe to commit.

## Superset

Superset exports live in `docs/BI/superset/`:

- `datasets/` for dataset definitions backing pacing and performance views.
- `dashboards/` for curated dashboard layouts.
- `subscriptions/` for alert and report schedules.

Import via the Superset UI (Settings → Import/Export) or the Superset CLI.
When updating exports, keep `bi/superset/` in sync for local BI workflows.

## Metabase

No Metabase exports are tracked yet. Add them under `docs/BI/metabase/` once
they are available, and update this README with import steps.
