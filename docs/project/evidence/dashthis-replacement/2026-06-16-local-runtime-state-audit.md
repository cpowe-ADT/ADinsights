# Local Runtime State Audit For SLB Cancellation Readiness

Date: 2026-06-16
Timezone: America/Jamaica
Status: local read-only audit; not cancellation-review evidence.

## Purpose

Check whether the local backend SQLite runtime can supply a concrete G1 SLB proof target or start
fixed-range G2/G3 evidence collection.

This audit is local-only. It does not prove staging or production readiness, and it does not close
G1. It records why the current local database cannot be used as the SLB cancellation-review proof
target.

## Command

Read-only Django shell query:

```bash
backend/.venv/bin/python backend/manage.py shell
```

The query inspected:

- configured database path
- Content Ops table presence
- `ReportDefinition` count and SLB template matches
- `ReportExportJob` count
- `DashboardDefinition` count and `dashboard.v1` matches
- `TenantMetricsSnapshot` counts by source and latest snapshot timestamp

No runtime code was changed.

## Findings

| Check                                   | Result                                                         | Cancellation-readiness implication                                                               |
| --------------------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Configured database                     | `/Users/thristannewman/ADinsights/backend/db.sqlite3`          | Local SQLite only; not staging/production proof.                                                 |
| Content Ops tables                      | Missing `content_ops_contentworkspace`                         | Local DB cannot prove G7/G8 Content Ops diagnostics or G2/G3 `content_ops` coverage.             |
| Total report definitions                | `1`                                                            | Local runtime has only one report record.                                                        |
| SLB `slb_monthly_social_report` reports | `0`                                                            | No local `report.v1` SLB proof target exists.                                                    |
| Existing report                         | Inactive legacy report, no `template_key`, no `schema_version` | Cannot be used for G1 SLB proof.                                                                 |
| Export jobs                             | `0`                                                            | No local export/snapshot evidence exists for G5.                                                 |
| Saved dashboards                        | `3`                                                            | Only legacy dashboards are present.                                                              |
| Saved `dashboard.v1` dashboards         | `0`                                                            | No local saved governed dashboard proof target exists for G4.                                    |
| Tenant metrics snapshots                | `5`                                                            | Stored snapshots exist, but they are not enough for SLB fixed-range proof.                       |
| Latest warehouse snapshot               | `2026-04-05T05:36:35.149541+00:00`                             | Stale for the recommended May 2026 proof range and current date.                                 |
| Demo/fake snapshots                     | Present                                                        | Cannot be used for DashThis cancellation proof unless explicitly labeled as non-parity fallback. |

## Migration And Template Path Check

Additional read-only check:

```bash
backend/.venv/bin/python backend/manage.py showmigrations analytics content_ops --plan
```

Result:

- Analytics migrations through `analytics.0008_dailyfxrate` are applied locally.
- Content Ops migrations are present but not applied locally:
  - `content_ops.0001_initial`
  - `content_ops.0002_contentexportartifact`
- The SLB report template builder exists at `backend/analytics/reporting_templates.py`.
- The SLB template creation API exists at `POST /api/reports/slb-monthly-template/`.
- The expected template key is `slb_monthly_social_report`.

Interpretation:

- Missing Content Ops tables are a local database setup gap, not evidence that the model or
  migrations are absent from the repo.
- Creating a local SLB report after applying migrations could support local workflow validation, but
  it would still be local-only evidence unless connected to the approved G1 tenant/client/date range
  and stored aggregate data.

## Redacted Runtime Summary

Safe tenant prefix observed: `ee1c8c78`.

Existing report summary:

```text
report_count=1
slb_report_count=0
existing_report_schema=None
existing_report_template=None
existing_report_active=False
export_count=0
dashboard_count=3
dashboard_v1_count=0
```

Snapshot summary:

```text
demo snapshots: count=1 latest=2026-02-27T00:00:00+00:00
fake snapshots: count=1 latest=2026-04-04T16:41:39.581684+00:00
warehouse snapshots: count=3 latest=2026-04-05T05:36:35.149541+00:00
```

## Decision

Local runtime cannot close G1, G2, G3, G4, or G5.

Before fixed-range evidence can start, the operator needs either:

- a target staging/production-like runtime with a real SLB `report.v1` report, stored aggregate
  data, Content Ops tables, and export paths, or
- a local setup step that creates a non-cancellation dry-run SLB report target and applies the
  required Content Ops migrations, explicitly labeled as local-only validation.

Recommended default: use staging/production-like runtime for cancellation evidence. Use local setup
only for implementation smoke testing, not G1-G12 pass claims.

## Local-Only Setup Option

If a future session needs local smoke validation, the safe sequence is:

```bash
backend/.venv/bin/python backend/manage.py migrate content_ops
```

Then create an SLB template report through the application API or a controlled Django shell using
`build_slb_monthly_report_layout(date_range="custom", start_date="2026-05-01", end_date="2026-05-31")`.

Do not mark G1 passed from this local-only target unless Raj/Mira explicitly redefine the proof as
local validation. Do not use demo/fake snapshots for DashThis parity claims.

DashThis cancellation remains no-go.

## Follow-Up

Update these when a real runtime target exists:

- `2026-06-16-g1-runtime-target-intake-checklist.md`
- `2026-06-16-g2-g9-evidence-execution-checklist.md`
- `2026-06-16-slb-cancellation-readiness-blocker-register.md`

Local-only smoke validation was later captured in:

`docs/project/evidence/dashthis-replacement/2026-06-16-local-slb-smoke-validation.md`
