# G11 Hardening Window: 24-48 Hour SLB Reporting Observation

Date: 2026-06-16
Timezone: America/Jamaica
Status: pre-hardening runbook prepared; G11 remains `not_started` until G10 passes.

## Purpose

Record a 24-48 hour hardening window after the SLB reporting path appears cancellation-ready. The
window proves ADinsights can keep rendering, diagnosing, exporting, and dry-running the fixed SLB
report without new blockers before any final DashThis cancellation recommendation.

Feature completion does not start the hardening clock. The clock starts only after G0-G10 are
evidence-complete for the same fixed G1 report/date range.

## Current Pre-Hardening Decision

Do not start the G11 clock.

Current blockers:

- G0 Raj/Mira architecture/scope review is still `review_pending`.
- G1 fixed SLB runtime target is still `blocked_external`.
- G2-G9 fixed-target evidence is incomplete.
- G10 has only a pre-adversarial implementation review; it has not run against the fixed evidence
  chain.
- DashThis/source parity values are not attached.

This packet is therefore a runbook and readiness checklist only. It is not hardening evidence.

Machine-readable template:

`docs/project/evidence/dashthis-replacement/2026-06-16-g11-hardening-window.template.json`

Validate the filled window before G12:

```bash
python3 scripts/validate_slb_g11_hardening_window.py \
  --window-file <filled-g11-hardening-window.json> \
  --g10-review-file <filled-g10-adversarial-review.json>
```

The validator checks the same fixed target as G10, 24-48 hour duration, required checkpoints,
preview/diagnostics/export/dry-run pass states, CSV/PDF/PNG non-empty artifact and hash proof,
DashThis active status, no reset conditions, Raj/Mira acceptance, and sensitive-value hygiene.

## Start Conditions

Do not start G11 until all are true:

- G0 Raj/Mira review is cleared or explicitly approved to enter hardening.
- G1 fixed SLB report/date range is locked.
- G2/G3 coverage and retained-history proof is complete.
- G4/G5 render/export reproducibility proof is complete for CSV/PDF/PNG.
- G6 parity worksheet is complete or any exceptions are explicitly accepted.
- G7/G8 scheduled dry-run and diagnostics proof is complete.
- G9 safety controls proof is complete.
- G10 adversarial review has no unresolved blocker or high-risk unaccepted issue.
- DashThis remains active during the observation window.

## Window Metadata

| Field                         | Value                        |
| ----------------------------- | ---------------------------- |
| Environment                   | Pending                      |
| Tenant/client safe identifier | Pending                      |
| SLB `ReportDefinition.id`     | Pending                      |
| Template key                  | Pending                      |
| Proof date range              | Pending                      |
| Window length                 | Pending: 24h or 48h          |
| Window start timestamp        | Pending                      |
| Window end timestamp          | Pending                      |
| Observer/operator             | Pending                      |
| Raj/Mira approval to start    | Pending                      |
| DashThis status during window | Active; pending confirmation |

## Pre-Window Readiness Checklist

Fill this table immediately before starting the 24-48 hour clock. Any `No` answer means G11 cannot
start.

| Gate                  | Required evidence                                                                                                                  | Status  | Link/notes                                                |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | ------- | --------------------------------------------------------- |
| G0 cleared            | Raj/Mira classify or approve the architecture/scope `GATE_BLOCK`.                                                                  | Pending | `2026-06-16-g0-raj-mira-review-packet.md`                 |
| G1 locked             | Fixed environment, tenant/client, report ID, template key, date range, source scope, delivery assumptions, DashThis active status. | Pending | `2026-06-16-g1-runtime-target-intake-checklist.md`        |
| G2/G3 passed          | Stored coverage and monthly/90-day retained-history proof for paid Meta Ads, organic Facebook/Page, and Content Ops.               | Pending | `2026-06-16-g2-g3-coverage-retained-history-proof.md`     |
| G4/G5 passed          | Saved dashboard/report rendering and CSV/PDF/PNG export reproducibility proof.                                                     | Pending | `2026-06-16-g4-g5-render-export-reproducibility-proof.md` |
| G6 passed or accepted | Parity worksheet completed with DashThis/source values, deltas, tolerances, pass/fail, and explanations.                           | Pending | `2026-06-16-g6-parity-worksheet-proof.md`                 |
| G7/G8 passed          | Scheduled dry-run and diagnostics/support proof complete without real client delivery or sensitive data.                           | Pending | `2026-06-16-g7-g8-delivery-diagnostics-proof.md`          |
| G9 passed             | Fixed-target permission, tenant-isolation, audit, quota, aggregate-only, and evidence-file hygiene proof complete.                 | Pending | `2026-06-16-g9-safety-controls-proof.md`                  |
| G10 passed            | Adversarial review has no unresolved blocker/high-risk issue.                                                                      | Pending | `2026-06-16-g10-adversarial-review.md`                    |
| DashThis active       | DashThis remains active and available as rollback/fallback during the window.                                                      | Pending | Operator confirmation                                     |
| Observer assigned     | Operator and reviewer route named for checkpoint execution and escalation.                                                         | Pending | Raj/Omar/Hannah                                           |

## Checkpoint Command Pack

Use these commands as the default checkpoint flow after filling placeholders. Do not paste real
OAuth tokens, private emails, provider payloads, or raw artifact contents into evidence files.

Set shell variables for the fixed target:

```bash
export ADI_BACKEND_URL="<backend-url>"
export ADI_OPERATOR_TOKEN="<operator-token>"
export ADI_REPORT_ID="<report-id>"
export ADI_START_DATE="YYYY-MM-DD"
export ADI_END_DATE="YYYY-MM-DD"
export ADI_EVIDENCE_TMP="/tmp/adinsights-slb-hardening"
mkdir -p "$ADI_EVIDENCE_TMP"
```

Preview:

```bash
curl -sS -X POST "$ADI_BACKEND_URL/api/reports/$ADI_REPORT_ID/preview/" \
  -H "Authorization: Bearer $ADI_OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"date_range\":\"custom\",\"start_date\":\"$ADI_START_DATE\",\"end_date\":\"$ADI_END_DATE\"}" \
  > /tmp/adinsights-slb-preview.json
```

Diagnostics:

```bash
curl -sS "$ADI_BACKEND_URL/api/reports/$ADI_REPORT_ID/diagnostics/" \
  -H "Authorization: Bearer $ADI_OPERATOR_TOKEN" \
  > /tmp/adinsights-slb-diagnostics.json
```

Exports:

```bash
for format in csv pdf png; do
  curl -sS -X POST "$ADI_BACKEND_URL/api/reports/$ADI_REPORT_ID/exports/" \
    -H "Authorization: Bearer $ADI_OPERATOR_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"export_format\":\"$format\"}" \
    > "/tmp/adinsights-slb-export-$format.json"
done
```

Scheduled dry-run:

```bash
curl -sS -X POST "$ADI_BACKEND_URL/api/reports/$ADI_REPORT_ID/scheduled-dry-run/" \
  -H "Authorization: Bearer $ADI_OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"export_format":"pdf"}' \
  > /tmp/adinsights-slb-dry-run.json
```

Parity evidence:

```bash
backend/.venv/bin/python backend/manage.py slb_report_parity_evidence \
  --report-id "$ADI_REPORT_ID" \
  --start-date "$ADI_START_DATE" \
  --end-date "$ADI_END_DATE" \
  --format json \
  > "$ADI_EVIDENCE_TMP/parity.json"
```

Offline evidence validation:

```bash
backend/.venv/bin/python backend/manage.py slb_report_evidence_validate \
  --evidence-bundle "$ADI_EVIDENCE_TMP/evidence-bundle.json" \
  --parity-comparison "$ADI_EVIDENCE_TMP/parity-comparison.json" \
  --expected-start-date "$ADI_START_DATE" \
  --expected-end-date "$ADI_END_DATE" \
  --format markdown \
  > /tmp/adinsights-slb-evidence-validation.md
```

The validation result must be `pass` before the hardening clock starts and at the final checkpoint.
If it returns `blocked`, reset the hardening clock and route the blocker to the owning G# packet.

Redaction scan before copying summaries into docs:

```bash
rg -n -i "(bearer\s+[a-z0-9._~+/=-]{20,}|access_token|refresh_token|client_secret|page_token|private key|xox|AKIA|AIza|ya29|EAAG|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})" \
  /tmp/adinsights-slb-preview.json \
  /tmp/adinsights-slb-diagnostics.json \
  /tmp/adinsights-slb-export-*.json \
  /tmp/adinsights-slb-dry-run.json \
  "$ADI_EVIDENCE_TMP/parity.json" \
  "$ADI_EVIDENCE_TMP/evidence-bundle.json" \
  "$ADI_EVIDENCE_TMP/parity-comparison.json" \
  /tmp/adinsights-slb-evidence-validation.md
```

Only copy summarized fields into evidence docs: status codes, preview hashes, coverage summaries,
blocking reasons, export job IDs, artifact byte counts, and sanitized delivery status.

## Monitoring Schedule

Use America/Jamaica timestamps. A 24-hour window needs at least start, midpoint, and end checks. A
48-hour window needs at least start, daily midpoint, and end checks.

| Checkpoint | Target time    | Required checks                                                                                       | Actual timestamp | Result  | Notes   |
| ---------- | -------------- | ----------------------------------------------------------------------------------------------------- | ---------------- | ------- | ------- |
| Start      | T+0            | Preview, diagnostics, CSV/PDF/PNG export, scheduled dry-run, evidence packet status, gate snapshot    | Pending          | Pending | Pending |
| Midpoint 1 | T+12h or T+24h | Preview hash, diagnostics, latest sync/freshness, export history, blocked states                      | Pending          | Pending | Pending |
| Midpoint 2 | T+36h if 48h   | Preview hash, diagnostics, latest sync/freshness, export history, blocked states                      | Pending          | Pending | Pending |
| End        | T+24h or T+48h | Full preview, diagnostics, CSV/PDF/PNG export or snapshot re-download proof, dry-run, gates/preflight | Pending          | Pending | Pending |

## Checkpoint Result Template

Use one block per checkpoint.

| Field                            | Value                                 |
| -------------------------------- | ------------------------------------- |
| Checkpoint                       | Start / Midpoint 1 / Midpoint 2 / End |
| Timestamp America/Jamaica        | Pending                               |
| Preview HTTP status              | Pending                               |
| Preview hash                     | Pending                               |
| Export ready                     | Pending                               |
| Coverage statuses by dataset     | Pending                               |
| Blocking reasons                 | Pending                               |
| Diagnostics status summary       | Pending                               |
| CSV export job ID and byte count | Pending                               |
| PDF export job ID and byte count | Pending                               |
| PNG export job ID and byte count | Pending                               |
| Scheduled dry-run job ID/status  | Pending                               |
| No-client-email proof            | Pending                               |
| Redaction scan result            | Pending                               |
| Gate/preflight result            | Pending                               |
| Evidence validation result       | Pending                               |
| Reviewer note                    | Pending                               |

## Evidence To Capture At Each Checkpoint

| Evidence          | Required fields                                                                                               |
| ----------------- | ------------------------------------------------------------------------------------------------------------- |
| Report preview    | HTTP status, `preview_hash`, `export_ready`, coverage summary, blocking reasons.                              |
| Diagnostics       | Dataset statuses, retained range, row counts, source labels, recommended next action, export history summary. |
| Export proof      | Export job IDs, formats, statuses, non-empty artifact check, snapshot hash, generated timestamp.              |
| Scheduled dry-run | Dry-run job ID, `delivery_status.mode`, `delivery_status.status`, proof no client email was sent.             |
| Freshness/sync    | Dataset freshness state, last successful sync if available, source-disconnected state if applicable.          |
| Safety            | Audit event sample, quota status if tested, no secrets/user-level data in captured payloads.                  |
| UI proof          | Report Detail visible coverage notes, appendix/data notes, export readiness/blocked state.                    |
| Gate snapshot     | Relevant backend/frontend/preflight commands and any failures.                                                |

## Reset Conditions

Reset the hardening clock and return to the owning sub-goal if any of these occur:

- A required SLB section fails to render.
- CSV, PDF, or PNG export is empty, corrupt, missing, or unsafe to download.
- Preview/export/dry-run coverage metadata conflicts with diagnostics.
- Freshness, partial coverage, missing history, or disconnected source state is hidden or mislabeled.
- Any cross-tenant, permissions, audit, quota, artifact safety, secret, or user-level data issue appears.
- Parity values drift outside accepted tolerances without an approved explanation.
- `adinsights-preflight` surfaces a new blocker unrelated to already accepted Raj/Mira scope review.
- A reviewer records a blocker or high-risk issue.

Reset action: record the checkpoint, link the failing evidence, move the relevant G# to
`failed_or_blocked` or `evidence_pending`, fix or document the issue, rerun the affected proof, then
start a new G11 window only after G10 is clean again.

## Hardening Findings Log

| ID       | Timestamp | Checkpoint | Finding           | Severity | Owner   | Resolution | Status  |
| -------- | --------- | ---------- | ----------------- | -------- | ------- | ---------- | ------- |
| HARD-001 | Pending   | Pending    | Pending execution | Pending  | Pending | Pending    | Pending |

Severity values:

- `blocker` - cancellation review cannot proceed.
- `high` - window resets unless Raj/Mira explicitly accept the risk.
- `medium` - can proceed only with documented mitigation and reviewer approval.
- `low` - note or follow-up is acceptable.
- `info` - evidence-only observation.

## Required End-Of-Window Gate Snapshot

Attach final command output or evidence links:

```bash
make backend-lint
make backend-test
make frontend-guardrails
make frontend-lint
make frontend-test
make frontend-build
scripts/dev-healthcheck.sh
make adinsights-preflight PROMPT="Assess SLB DashThis cancellation hardening window readiness"
```

If release smoke is available for the target environment, attach:

```bash
backend/.venv/bin/python backend/manage.py backend_release_preflight
python3 backend/manage.py backend_release_smoke --strict-observability
```

## Reviewer Route

- Raj: approves start/end of hardening and cancellation-review entry.
- Mira: confirms no architecture, snapshot, or cross-stream consistency issue appeared.
- Omar: reviews freshness, diagnostics, sync state, and operational stability.
- Hannah: verifies evidence clarity and support handoff.
- Sofia/Andre: review API/metrics issues if preview/export/diagnostics/parity drift occurs.
- Lina/Joel: review UI issues if report rendering, responsive layout, or coverage notes drift.
- Nina: reviews any artifact, secrets, or evidence-safety issue.
- Carlos/Mei: review deployment/export runtime issues if the target environment is staging/prod-like.

## G11 Pass Rules

G11 can move to `passed` only when all are true:

- The full 24-48 hour window is recorded with start/end timestamps.
- Every scheduled checkpoint has evidence and a pass/fail result.
- No reset condition remains unresolved.
- Final preview, diagnostics, exports, scheduled dry-run, safety checks, and gate snapshot are
  attached for the same fixed G1 report/date range.
- DashThis remained active throughout the window.
- Raj, Mira, and Omar agree the hardening evidence is sufficient for G12 final recommendation.

Current decision: G11 is not started. DashThis cancellation remains no-go.
