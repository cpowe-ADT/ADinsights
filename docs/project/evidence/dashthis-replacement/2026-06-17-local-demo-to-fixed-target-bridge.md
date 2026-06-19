# Local Demo To Fixed-Target Bridge

Date: 2026-06-17
Timezone: America/Jamaica
Status: operator bridge; not cancellation-review evidence.

## Purpose

Translate the current local SLB report demo into the exact next steps needed for G1 fixed-target
intake and later G2-G11 evidence capture.

The local report proves the reporting path can render and export. It does not prove the selected
runtime target, DashThis parity, retained history, or cancellation readiness.

## Current Local Demo

| Field | Value |
| --- | --- |
| Local report ID | `a40abad9-9f1d-4e75-92b0-3e0feaed27b5` |
| Local route | `/reports/a40abad9-9f1d-4e75-92b0-3e0feaed27b5` |
| Report name | `SLB Monthly Social Report - Local Demo` |
| Template key | `slb_monthly_social_report` |
| Schema version | `report.v1` |
| Preview pages | 8 |
| Preview hash | `e795fb08d22ec0ee02015c771f7cef15d19cf8188140f0baaaadc90dd07fa6ff` |
| Cancellation evidence? | No |

Local proof artifact:

`docs/project/evidence/dashthis-replacement/2026-06-17-local-browser-render-export-proof.md`

## What The Local Demo Proves

- The frontend report route can render a governed `report.v1` SLB scaffold.
- `POST /api/reports/<id>/preview/` returns ordered page/widget payloads.
- `GET /api/reports/<id>/diagnostics/` returns support-safe dataset status.
- CSV, PDF, and PNG export jobs can complete locally and download non-empty artifacts.
- Coverage warnings are visible instead of hidden.

## What The Local Demo Does Not Prove

- Raj/Mira have not cleared G0.
- The local report is not the approved G1 fixed target.
- The local report has no DashThis/source comparison values.
- Organic Facebook/Page and Content Ops are `missing_history`.
- Paid Meta Ads is `source_disconnected` for the requested May range.
- Meta credentials currently require reauth before fresh Facebook/Meta sync can be claimed.
- The UI is visually rough and not client-ready.
- No 24-48 hour hardening window has started.

DashThis cancellation remains `NO-GO`.

## Local Source Repair Notes

On 2026-06-17, the local Airbyte destination for `Meta Metrics Connection Postgres` was found to
point at `host.docker.internal:5435`, while the running ADinsights Postgres service was reachable
from the Airbyte container at `host.docker.internal:5432`. The local Airbyte destination was updated
in the Airbyte workspace to keep the same destination, database, schema, user, and password while
changing only the port from `5435` to `5432`.

The Airbyte destination check endpoint then returned `status: succeeded`. This repairs the local
destination connectivity issue only. It does not repair the Meta credential state, does not run a
provider sync, and does not create fixed-target SLB evidence. The remaining local source actions are:

- Reconnect Meta OAuth credentials.
- Rerun Meta sync after reauth.
- Backfill Facebook Page Insights rows.
- Backfill Facebook post insight rows.
- Generate or backfill Content Ops aggregate snapshots.
- Regenerate preview, diagnostics, history probe, evidence bundle, exports, and parity artifacts
  from the approved G1 target.

Repeatable local check:

```bash
python3 scripts/check_local_airbyte_destination.py \
  --destination-id 296e6bb4-c464-4c91-a893-5d2e9af439f1 \
  --run-airbyte-check \
  --format json
```

Expected local result:

- `valid: true`
- `config.host: host.docker.internal`
- `config.port: 5432`
- `airbyte_check.status: succeeded`

## Conversion Steps

Use this order to convert the working local demo into cancellation-review evidence.

| Step | Action | Evidence destination | Owner route |
| --- | --- | --- | --- |
| 1 | Fill the G0 Raj/Mira decision JSON and validate it. | G0 review packet and status manifest | Raj, Mira |
| 2 | Choose the real runtime target: environment, tenant/client, report ID, date range, and source scopes. | G1 runtime intake checklist and JSON | Operator, Hannah, Raj |
| 3 | Generate `slb_report_target_intake` output for the chosen report. | G1 target-intake output | Operator |
| 4 | Validate G0/G1 agreement before collecting evidence. | G0/G1 handoff validator output | Operator, Raj, Mira |
| 5 | Run preview, diagnostics, history probe, evidence bundle, parity, exports, and dry-run only against that same target. | G2-G9 evidence run | Sofia, Andre, Lina, Joel, Omar, Hannah |
| 6 | Run adversarial review only after G2-G9 evidence exists. | G10 adversarial packet | Raj, Mira, Omar, Hannah, Nina |
| 7 | Start hardening only after G10 has no unresolved blockers. | G11 hardening packet | Raj, Mira, Omar |
| 8 | Write keep/cancel recommendation only after G0-G11 pass or are explicitly waived. | G12 recommendation | Raj, Mira, business owner |

## Commands For The Real Target

Replace placeholders with the approved G1 target values.

```bash
python3 scripts/validate_slb_g0_raj_mira_review.py \
  --review-file <filled-g0-raj-mira-review-decision.json>
```

```bash
backend/.venv/bin/python backend/manage.py slb_report_target_intake \
  --report-id <approved-slb-report-id>
```

```bash
python3 scripts/validate_slb_g1_runtime_target_intake.py \
  --intake-file <filled-g1-runtime-target-intake.json>
```

```bash
python3 scripts/validate_slb_g0_g1_handoff.py \
  --g0-review-file <filled-g0-raj-mira-review-decision.json> \
  --g1-intake-file <filled-g1-runtime-target-intake.json>
```

```bash
backend/.venv/bin/python backend/manage.py slb_report_evidence_bundle \
  --report-id <approved-slb-report-id> \
  --start-date <YYYY-MM-DD> \
  --end-date <YYYY-MM-DD> \
  --output-json <safe-output-path>
```

## Acceptance Rule

Do not copy the local demo report ID into G1 unless the operator explicitly chooses the local
runtime as the fixed evidence environment and Raj/Mira allow that path.

If the approved target differs from the local demo, all preview/export/diagnostics/parity evidence
must be regenerated from the approved target. Reusing local-demo artifacts would be invalid for
G2-G12.
