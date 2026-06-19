# G0/G1 Review And Fixed-Target Intake Handoff

Date: 2026-06-16
Timezone: America/Jamaica
Status: action handoff; G0 remains `review_pending` and G1 remains `blocked_external`.

## Purpose

Give Raj, Mira, and the operator one short handoff to clear the architecture/scope gate and lock
the fixed SLB proof target. This is the bridge from planning evidence to runtime evidence capture.

This packet does not approve DashThis cancellation. It only answers whether the team may proceed
from G0/G1 into G2-G11 evidence capture.

## Immediate Human Actions

The next progress requires four external answers. Do not start fixed-target cancellation evidence
until at least actions 1 and 2 are complete.

| # | Owner | Action | Required response format | Blocks |
| --- | --- | --- | --- | --- |
| 1 | Raj + Mira | Classify the current architecture/scope `GATE_BLOCK` and decide whether G1-G11 evidence capture may proceed. | Fill the G0 Decision Record below with approve / approve-with-conditions / block, reviewer route, and required changes. | G0, all later goals |
| 2 | Operator + Hannah | Fill the fixed SLB runtime target. | Complete the G1 Fixed Target Intake table with environment, backend/frontend URLs, safe tenant/client, runtime report ID, scopes, date range, delivery assumptions, and DashThis active confirmation. | G1-G11 |
| 3 | DashThis/source comparison owner + Andre | Provide safe comparison values for the fixed SLB range. | Fill or attach redacted values for every required non-Instagram metric with source, tolerance, and explanation. | G6, G10-G12 |
| 4 | Carlos/Mei or runtime owner + Raj/Mira | Resolve the Airbyte production-readiness prerequisite. | Record target-runtime `AIRBYTE_TEMPLATE_META_METRICS_CONNECTION_ID` evidence path or approved alternative bootstrap path. Do not paste tokens. | G11-G12 |

Minimum acceptable response:

```text
G0 decision:
- Raj:
- Mira:
- Proceed to G1-G11 evidence capture: yes/no/conditional
- Conditions:
- Required reviewers:

G1 target:
- Environment:
- Backend URL:
- Frontend URL:
- Safe tenant/client:
- ReportDefinition.id:
- Date range:
- Paid Meta account scope:
- Organic Facebook Page scope:
- Content Ops scope:
- DashThis/source comparison owner:
- Delivery assumption:
- DashThis remains active: yes/no

External prerequisite:
- Airbyte Meta metrics template connection evidence path or approved alternative:
```

## Send This Review Request

```text
Raj/Mira review requested for ADinsights SLB DashThis cancellation-readiness.

Scope:
- Target is SLB Monthly Social Report without Instagram in v1.
- ADinsights reporting must use stored aggregate data only.
- No live Meta/Facebook/provider calls at report preview/export time.
- DashThis remains active; this is not a cancellation request.

Implemented/reporting-ops surfaces already documented:
- dashboard.v1 validation/rendering
- report.v1 validation/rendering
- reporting catalog endpoint
- widget preview endpoint
- report preview endpoint
- export coverage metadata and report snapshots
- diagnostics endpoint
- scheduled dry-run evidence
- SLB parity evidence command
- report privileges, audit events, and quotas

Decision requested:
1. Classify the current preflight GATE_BLOCK as architecture/scope review, test failure, or runtime blocker.
2. Decide whether G1-G11 fixed-range evidence capture may proceed.
3. Confirm whether ReportExportJob.metadata.report_snapshot is acceptable as the v1 snapshot store for this proof.
4. Confirm required reviewers for coverage, parity, frontend report rendering, diagnostics, safety, and hardening.
5. Confirm DashThis cancellation remains no-go until G0-G11 pass and G12 recommends cancellation.

Primary docs:
- docs/project/evidence/dashthis-replacement/2026-06-16-g0-raj-mira-review-packet.md
- docs/project/evidence/dashthis-replacement/2026-06-16-g1-fixed-slb-proof-target.md
- docs/project/evidence/dashthis-replacement/2026-06-16-slb-cancellation-readiness-goals.md
- docs/project/evidence/dashthis-replacement/2026-06-16-slb-reporting-render-export-parity-evidence.md
```

## G0 Decision Record

Fill this table after Raj/Mira review. Do not infer approval from silence.

| Field | Decision |
| --- | --- |
| Review date/time | Pending |
| Raj decision | Pending |
| Mira decision | Pending |
| Scope classification | Pending: architecture scope / test failure / runtime blocker / approved |
| Architecture classification | Pending |
| Can G1-G11 proceed? | Pending |
| Snapshot-store decision | Pending |
| Required follow-up reviewers | Pending |
| Required implementation changes before evidence capture | Pending |
| Explicit DashThis cancellation status | No-go; pending reviewer confirmation |

G0 can move to `passed` only if the decision explicitly allows G1-G11 evidence capture or records
an approved path for doing so. If implementation changes are required first, keep G0
`review_pending` or move it to `failed_or_blocked` with the required work item.

## Current Preflight Snapshot

Latest command:

```bash
make adinsights-preflight PROMPT="Assess SLB DashThis cancellation-readiness G0 G1 review and fixed-target intake"
```

Result captured 2026-06-16:

| Field | Value |
| --- | --- |
| Router action | `clarify` |
| Scope status | `ESCALATE_ARCH_RISK` |
| Contract status | `WARN_POSSIBLE_CONTRACT_CHANGE` |
| Release status | `GATE_BLOCK` |
| Contract executed | `True` |
| Output directory | `/var/folders/4k/xdt2s05j1tl9zpyxhwtt8pk80000gn/T/adinsights-preflight-output-tjwl5mjo` |

Blocking issue:

- Scope control gate blocked by architecture-level scope risk.

Warnings:

- Contract integrity requires follow-up before release.
- Security/PII gate requires verification due to sensitive signals.

Operator interpretation:

- Do not treat this as DashThis cancellation readiness.
- Treat this as the current reason G0 still needs Raj/Mira classification before fixed-range
  evidence can be used for cancellation review.
- If Raj/Mira allow G1-G11 evidence capture despite the architecture gate, record that explicitly
  in the G0 decision table above.

Persisted packet set:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake/README.md`
- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake/router-packet.json`
- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake/scope-packet.json`
- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake/contract-packet.json`
- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake/release-packet.json`

Checked persisted packet set:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake-with-checks/README.md`
- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake-with-checks/router-packet.json`
- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake-with-checks/scope-packet.json`
- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake-with-checks/contract-packet.json`
- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake-with-checks/release-packet.json`

Checked run summary:

- `data_contract_gate` passed.
- `observability_prereqs` passed.
- `production_readiness` failed because `AIRBYTE_TEMPLATE_META_METRICS_CONNECTION_ID` is required
  to bootstrap connections.

## G1 Fixed Target Intake

Detailed operator checklist:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g1-runtime-target-intake-checklist.md`

Machine-readable G1 intake template:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g1-runtime-target-intake.template.json`

Validate the filled G1 intake JSON before using it for G2-G11 evidence:

```bash
python3 scripts/validate_slb_g1_runtime_target_intake.py \
  --intake-file <filled-g1-runtime-target-intake.json>
```

Fill this table before running coverage, parity, export, delivery, diagnostics, safety, adversarial,
or hardening evidence. Every later packet must use the same values.

| Required value | Selected value | Evidence/source | Notes |
| --- | --- | --- | --- |
| Target environment | Pending | Pending | Local/staging/prod-like; do not mix. |
| Backend URL | Pending | Pending | Redact if needed. |
| Frontend URL | Pending | Pending | Redact if needed. |
| Safe tenant identifier | Pending | Pending | Use safe/redacted ID, not secrets. |
| Safe client identifier | Pending | Pending | Expected: SLB / Students' Loan Bureau. |
| `ReportDefinition.id` | Pending | Pending | Must be real runtime report ID. |
| `template_key` | Pending | Pending | Expected: `slb_monthly_social_report`. |
| Primary report date range | Recommended: 2026-05-01 through 2026-05-31 | Gmail-derived report inventory | Operator confirmation pending. |
| Optional baseline range | Recommended: 2026-03-01 through 2026-04-30 | Gmail-derived report inventory | Optional trend/parity baseline. |
| Paid Meta account scope | Pending | Pending | Safe/redacted account label or ID. |
| Organic Facebook Page scope | Pending | Pending | Safe/redacted Page label or ID. |
| Content Ops workspace/client scope | Pending | Pending | Safe/redacted workspace/client label. |
| DashThis/source comparison owner | Pending | Pending | Person who can supply comparison values. |
| Recipient/delivery assumption | Pending | Pending | Redact private recipient details. |
| Instagram decision | Deferred in v1 | Goal guardrail | Requires source rows/scopes/catalog/reviewer approval to change. |
| DashThis status during proof | Active | Goal guardrail | Must remain active until G12. |

G1 can move to `passed` only after all required runtime values are filled and Raj/Mira either clear
G0 or explicitly allow fixed-range evidence capture while G0 remains under review.

## First Commands After G0/G1 Are Filled

Use the confirmed G1 values. Store summarized/redacted outputs in the relevant evidence packets.

```bash
backend/.venv/bin/python backend/manage.py slb_report_parity_evidence \
  --report-id <slb-report-id> \
  --start-date <YYYY-MM-DD> \
  --end-date <YYYY-MM-DD> \
  --format markdown
```

Redacted target intake command:

```bash
backend/.venv/bin/python backend/manage.py slb_report_target_intake \
  --report-id <slb-report-id>
```

Then capture:

```text
POST /api/reports/<report-id>/preview/
GET /api/reports/<report-id>/diagnostics/
POST /api/reports/<report-id>/exports/ for csv, pdf, png
POST /api/reports/<report-id>/scheduled-dry-run/
GET /api/reports/<report-id>/exports/
GET /api/exports/<job-id>/download/
```

Run gates for any code state used as evidence:

```bash
make backend-lint
make backend-test
make frontend-guardrails
make frontend-lint
make frontend-test
make frontend-build
scripts/dev-healthcheck.sh
make adinsights-preflight PROMPT="Assess SLB DashThis cancellation-readiness fixed-target evidence"
```

## Evidence Packet Routing After Intake

Before updating individual packets, create one run sheet in:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g2-g9-evidence-execution-checklist.md`

The checklist now includes a single-run evidence sheet, recommended temporary output names, and a
completion matrix that must be filled before G10 starts.

| Next goal | Packet to update |
| --- | --- |
| G2/G3 coverage and history | `2026-06-16-g2-g3-coverage-retained-history-proof.md` |
| G4/G5 rendering and exports | `2026-06-16-g4-g5-render-export-reproducibility-proof.md` |
| G6 parity worksheet | `2026-06-16-g6-parity-worksheet-proof.md` and `source-platform-comparison-worksheet.md` |
| G7/G8 delivery and diagnostics | `2026-06-16-g7-g8-delivery-diagnostics-proof.md` |
| G9 safety controls | `2026-06-16-g9-safety-controls-proof.md` |
| G10 adversarial review | `2026-06-16-g10-adversarial-review.md` |
| G11 hardening window | `2026-06-16-g11-hardening-window.md` |
| G12 recommendation | `2026-06-16-g12-final-cancellation-recommendation.md` |

## Current Decision

- G0: `review_pending`.
- G1: `blocked_external`.
- DashThis cancellation: no-go; keep active.
