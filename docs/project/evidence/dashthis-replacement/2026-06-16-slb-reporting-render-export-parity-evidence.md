# SLB Reporting Render/Export Parity Evidence

Date: 2026-06-16
Status: implementation evidence packet; DashThis cancellation remains no-go until parity and hardening pass.

## Scope

This packet tracks the first end-to-end SLB reporting proof after the reporting vertical slice:

- Saved `dashboard.v1` dashboards render from governed widget preview payloads.
- SLB `report.v1` pages render in the frontend.
- `POST /api/reports/{id}/preview/` assembles report pages from stored aggregate data only.
- `report.v1` exports capture server-computed coverage metadata and a durable `report_snapshot`
  before queueing.
- `GET /api/reports/{id}/diagnostics/` exposes support-safe retained-history, freshness, blocking,
  and export-history details.
- Report diagnostics also expose the shared redacted `source_health` block used by
  `slb_report_history_probe`, including Meta credential status counts, Page connection counts,
  Meta Airbyte status/error categories, stored row counts, and recommended next actions without
  live provider calls or secrets.
- `POST /api/reports/{id}/scheduled-dry-run/` creates scheduled delivery evidence without sending
  client email.
- `backend/manage.py slb_report_parity_evidence` outputs ADinsights-side fixed-range comparison rows
  for manual DashThis/source-platform values.
- `backend/manage.py slb_report_evidence_bundle` outputs one sanitized fixed-range bundle with
  preview, diagnostics, rendering summary, export metadata summary, and parity rows for the same
  SLB report/date range.
- `backend/manage.py slb_report_parity_compare` merges the evidence-bundle parity rows with a
  redacted comparison-values JSON file and computes absolute delta, percent delta, tolerance result,
  and blocked states.
- `backend/manage.py slb_report_evidence_validate` validates offline fixed-target evidence artifacts
  for date-range consistency, required datasets, coverage blockers, report pages, exports, scheduled
  dry-run evidence, parity results, Instagram deferral, and sensitive-pattern hygiene.
- `backend/manage.py slb_report_target_intake` summarizes a candidate SLB `ReportDefinition` for G1
  intake with redacted schema/template/date-range/dataset/page/scope-presence guardrails.
- `backend/manage.py slb_report_history_probe` summarizes primary-month and retained-90-day coverage
  for required SLB datasets without raw rows or live provider calls.
- `scripts/dev-healthcheck.sh --airbyte-destination-id <id>` or
  `--airbyte-connection-id <id>` can run a local app reachability check plus redacted Airbyte
  destination validation against the expected local Postgres target without triggering a
  Meta/Facebook provider sync.
- Instagram remains deferred unless source rows, permissions, catalog entries, and reviewer approval are proven.

Use `2026-06-16-slb-cancellation-readiness-goals.md` as the goal/sub-goal control document for this
evidence packet.

## Current Reporting Ops Review Packet

Changed implementation surfaces:

- Backend: report snapshot/export metadata, diagnostics endpoint, scheduled dry-run service, parity
  evidence command, report action privileges, audit events, and lightweight quotas.
- Frontend: Report Detail now shows preview coverage, latest export snapshot hash, diagnostics,
  delivery readiness, and scheduled dry-run action.
- Docs: API contract changelog and this evidence packet record the additive contract changes.

G0 Raj/Mira review packet:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g0-raj-mira-review-packet.md`
- `docs/project/evidence/dashthis-replacement/2026-06-17-g0-raj-mira-agent-review-decision.json`

Current G0 status: passed for conditional fixed-target evidence capture. Raj/Mira both approved
with followups; DashThis cancellation remains no-go.

G0/G1 review and fixed-target intake handoff:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g0-g1-review-target-intake.md`

The handoff queue now starts at G1: operator fixed-target intake, DashThis/source comparison values,
and Airbyte template connection readiness.

G1 fixed proof-target packet:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g1-fixed-slb-proof-target.md`

G1 runtime target intake checklist:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g1-runtime-target-intake-checklist.md`

G1 machine-readable intake template:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g1-runtime-target-intake.template.json`

G1 intake validator:

```bash
python3 scripts/validate_slb_g1_runtime_target_intake.py \
  --intake-file <filled-g1-runtime-target-intake.json>
```

The G1 validator preserves G0 review semantics: Raj/Mira decisions must approve or conditionally
approve evidence capture, conditional/follow-up approvals require real condition notes, and
conditional approvals cannot be represented as clean G1 proceed flags.
It also loads the referenced `slb_report_target_intake` output and checks that the generated
`slb_target_intake.v1` summary agrees with the filled report ID, primary date range, template,
schema, required datasets/pages, source-scope presence, and no-Instagram/no-sensitive-pattern
guardrails.

G1 intake validator preflight:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g1-runtime-intake-validator/`

G1 clearance consistency preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g1-clearance-consistency/`

G1 target-intake output validation preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g1-target-output/`

Local runtime-state audit:

- `docs/project/evidence/dashthis-replacement/2026-06-16-local-runtime-state-audit.md`

Local SLB smoke validation:

- `docs/project/evidence/dashthis-replacement/2026-06-16-local-slb-smoke-validation.md`

Local browser render/export proof:

- `docs/project/evidence/dashthis-replacement/2026-06-17-local-browser-render-export-proof.md`

Local demo to fixed-target bridge:

- `docs/project/evidence/dashthis-replacement/2026-06-17-local-demo-to-fixed-target-bridge.md`

Local visual render proof:

- `docs/project/evidence/dashthis-replacement/2026-06-17-local-visual-render-proof.md`

This local browser/API proof confirms the current report route renders eight ordered `report.v1`
pages, preview/diagnostics expose paid `source_disconnected` and organic/content `missing_history`
states, and earlier local CSV/PDF/PNG exports downloaded non-empty local artifacts. As of the
2026-06-17 readiness tightening, the same missing-history state must block new `report.v1` exports
until required stored aggregate rows are backfilled or the fixed target is changed by reviewers.
This is intentionally local-only implementation evidence and does not advance DashThis
cancellation readiness.
The bridge records the conversion path from this local proof to G1 fixed-target intake and makes
explicit that local-demo artifacts must not be reused for G2-G12 unless Raj/Mira and the operator
choose that runtime as the approved evidence target.
The visual proof captures desktop and mobile screenshots under `output/playwright/`, confirming the
post-polish report view surfaces `missing_history` and `source_disconnected` states visibly.
Current frontend/backend behavior now surfaces those missing-history states as export-blocking
rather than export-ready-with-warnings.
The Report Detail diagnostics panel now surfaces support-safe source health and next actions, so
operators can distinguish Meta reauth, Page connection, Airbyte sync, stored Page/Post rows, and
Content Ops snapshot gaps without reading backend logs.

G2-G9 fixed-range evidence execution checklist:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g2-g9-evidence-execution-checklist.md`

The checklist now includes a single-run evidence sheet, recommended temporary output filenames, a
combined evidence bundle command, and a completion matrix that must be filled before G10
adversarial review starts.

SLB cancellation-readiness blocker register:

- `docs/project/evidence/dashthis-replacement/2026-06-16-slb-cancellation-readiness-blocker-register.md`

Machine-readable cancellation-readiness status:

- `docs/project/evidence/dashthis-replacement/2026-06-16-slb-cancellation-readiness-status.json`

Status manifest validator:

```bash
python3 scripts/validate_slb_cancellation_readiness_status.py
```

The validator checks for drift between the JSON manifest, G0-G12 goal table, and active blocker
register before a future session uses the packet for readiness handoff. It also rejects passed
sub-goals with unresolved linked blockers and cancellation-review readiness claims while G0-G11
blockers remain unresolved. It now also requires `next_execution.g1_intake_template` to point at an
existing template and `next_execution.g1_intake_validator` to call the governed G1 intake validator.
It also requires the G2-G9 fixed-range evidence run template and validator to remain wired into the
next execution handoff, plus the G10 adversarial review template and validator before any G11
hardening claim. It also validates the non-evidence G0/G1 example artifacts with the current G0,
G1, and combined handoff validators so future sessions do not copy stale example shapes. The
manifest also keeps the G12 approval/signoff preflight packet linked from `next_execution`, so the
final recommendation path cannot silently drop the explicit reviewer-approval gate.

Focused validator regression coverage:

```bash
cd backend
PYTHONPATH=.. ./.venv/bin/pytest -q ../scripts/tests/test_validate_slb_cancellation_readiness_status.py
```

Current next-step doctor:

```bash
python3 scripts/slb_cancellation_readiness_doctor.py
```

The focused test suite currently covers status-control cases including
G0/G1/G2-G9/G10/G11/G12 handoff link drift, G0/G1 external handoff link drift, combined G0/G1
handoff validator drift, G0/G1 valid-example drift, false pass claims, and false review-readiness
claims. It also rejects secret, raw-payload, email, and user-level identifier patterns in the
status manifest, goal doc, and blocker register before those docs are used for cancellation-review
handoff.

G0/G1 external handoff packet:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g0-g1-external-handoff.md`

G0/G1 valid examples:

- `docs/project/evidence/dashthis-replacement/examples/README.md`

G0 Raj/Mira review template:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g0-raj-mira-review-decision.template.json`

G0 Raj/Mira review validator:

```bash
python3 scripts/validate_slb_g0_raj_mira_review.py \
  --review-file <filled-g0-raj-mira-review-decision.json>
```

This validator is the local pre-G1 control. It fails if Raj/Mira have not explicitly classified the
cross-stream scope and architecture state, G1-G11 evidence capture is not approved or blocked in a
clear way, DashThis cancellation is not still `no_go`, the preflight block is misrepresented as a
runtime failure, reviewer routes are incomplete, or sensitive/user-level patterns appear.
It also rejects inconsistent clean approval, approval-with-followups, and blocked-before-G1
classifications so downstream fixed-target evidence cannot start from an ambiguous G0 state.
It now requires a stable `slb-g0-*` decision ID, timezone-aware decision timestamp, ordered decision
log timestamps, non-placeholder follow-up owner routes, and explicit before-G1 follow-up rows when
Raj/Mira block fixed-target evidence capture.
It also checks the referenced regular and checked preflight packet JSON files, so
`scope_status`, `contract_status`, and `release_status` in the filled G0 decision must match the
persisted `scope-packet.json`, `contract-packet.json`, and `release-packet.json` evidence.

G0/G1 combined handoff validator:

```bash
python3 scripts/validate_slb_g0_g1_handoff.py \
  --g0-review-file <filled-g0-raj-mira-review-decision.json> \
  --g1-intake-file <filled-g1-runtime-target-intake.json>
```

This validator is the local pre-G2 control. It fails if the filled G1 intake claims a G0 approval
path that does not match the filled Raj/Mira decision, if follow-up conditions are lost, or if the
shared no-Instagram, stored-aggregate-only, no-live-provider-call, dry-run, and DashThis-active
guardrails drift.
It also checks that G1 reviewer decisions preserve G0 reviewer decisions, target dates are valid and
ordered, comparison owner/location fields are filled, and the target-intake output evidence is
attached before G2-G11 collection starts.

G2-G9 fixed-range evidence run template:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g2-g9-fixed-range-evidence-run.template.json`

G2-G9 evidence run validator:

```bash
python3 scripts/validate_slb_g2_g9_evidence_run.py \
  --run-file <filled-g2-g9-evidence-run.json> \
  --intake-file <filled-g1-runtime-target-intake.json>
```

This validator is the local pre-G10 control. It fails if fixed G1 target values drift, required
sections are missing, parity rows remain failed/blocked, exports are empty or hash-mismatched,
scheduled delivery dry-run is unsafe/incomplete, safety proof is incomplete, or an architecture
`GATE_BLOCK` has not been accepted by G0.
It also fails if dataset covered dates are malformed or reversed, if fresh/stale/disconnected-with-
history coverage does not span the fixed target range, or if stale/partial/disconnected states lack
an explicit reviewer note.
The filled run must reference existing, non-empty evidence artifacts under
`docs/project/evidence/dashthis-replacement/`; JSON evidence must parse and text evidence is scanned
for sensitive or user-level patterns before G10 can start.

G10 adversarial review template:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g10-adversarial-review.template.json`

G10 adversarial review validator:

```bash
python3 scripts/validate_slb_g10_adversarial_review.py \
  --review-file <filled-g10-adversarial-review.json> \
  --g2-g9-run-file <filled-g2-g9-evidence-run.json>
```

This validator is the local pre-G11 control. It fails if G10 drifts from the G2-G9 run, any
adversarial check is still open, high/blocker findings lack fixed/accepted/waived resolution,
unsupported Instagram or hidden stale/partial/missing-history risk remains, rollback is not
confirmed, Raj/Mira acceptance is absent, or sensitive/user-level patterns appear.
Accepted or waived risk rows must also include structured approval metadata with a risk owner,
Raj/Mira acceptance, expiry or review-by date, and rationale so G12 can audit the decision.
Each adversarial row must also reference an existing, non-empty artifact under
`docs/project/evidence/dashthis-replacement/`; JSON artifacts must parse and text artifacts are
scanned for sensitive or user-level patterns.

G11 hardening-window template:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g11-hardening-window.template.json`

G11 hardening-window validator:

```bash
python3 scripts/validate_slb_g11_hardening_window.py \
  --window-file <filled-g11-hardening-window.json> \
  --g10-review-file <filled-g10-adversarial-review.json>
```

This validator is the local pre-G12 control. It fails if the G11 window is shorter than 24 hours
or longer than 48 hours, required checkpoints are missing, a reset occurred, preview/diagnostics/
export/dry-run/evidence validation did not pass, CSV/PDF/PNG artifacts are empty or hash-mismatched,
DashThis was not active, Raj/Mira acceptance is absent, or sensitive/user-level patterns appear.
It also parses the window and checkpoint timestamps, verifies the actual elapsed window spans the
declared length, and rejects out-of-order checkpoint evidence.
The filled window must also reference existing, non-empty checkpoint, final evidence-validation,
redaction-scan, and export-snapshot artifacts under `docs/project/evidence/dashthis-replacement/`;
JSON artifacts must parse and text artifacts are scanned for sensitive or user-level patterns.

G12 final recommendation template:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g12-final-recommendation.template.json`

G12 final recommendation validator:

```bash
python3 scripts/validate_slb_g12_final_recommendation.py \
  --recommendation-file <filled-g12-final-recommendation.json> \
  --status-manifest-file docs/project/evidence/dashthis-replacement/2026-06-16-slb-cancellation-readiness-status.json \
  --g11-window-file <filled-g11-hardening-window.json>
```

This validator is the final local no-go/cancel control. It fails unless G0-G11 are passed, the
decision matches the fixed G11 target, rollback and monitoring owners are named, reviewer and
business-owner sign-offs are filled with non-blocking approval values, Instagram remains excluded,
render/export source remains stored aggregate data only, and sensitive/user-level patterns are
absent.
Cancellation recommendations must also include a concrete DashThis cancellation date on or after
the decision effective date plus explicit business-owner cancellation approval; keep/no-cancel
recommendations must leave that date empty and still require business-owner acceptance.
Each G0-G11 `evidence_rollup` link must resolve to an existing, non-empty artifact under
`docs/project/evidence/dashthis-replacement/`; JSON artifacts must parse and text artifacts are
scanned for sensitive or user-level patterns.
Denied, pending, or review-pending approval/signoff values fail validation.

Full evidence-chain validator:

```bash
python3 scripts/validate_slb_evidence_chain.py \
  --g0-review-file <filled-g0-raj-mira-review-decision.json> \
  --g1-intake-file <filled-g1-runtime-target-intake.json> \
  --g2-g9-run-file <filled-g2-g9-evidence-run.json> \
  --g10-review-file <filled-g10-adversarial-review.json> \
  --g11-window-file <filled-g11-hardening-window.json> \
  --g12-recommendation-file <filled-g12-final-recommendation.json> \
  --status-manifest-file docs/project/evidence/dashthis-replacement/2026-06-16-slb-cancellation-readiness-status.json
```

This command orchestrates the existing stage validators so G0/G1, G2-G9, G10, G11, and G12 cannot
be checked as unrelated artifacts with mismatched target data or missing upstream evidence.

Validator test preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-status-validator-tests/`

G0 Raj/Mira review validator preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g0-raj-mira-review-validator/`

G0 validator consistency preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g0-validator-consistency/`

G0 decision-metadata validation preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g0-decision-metadata/`

G0 preflight-packet status validation preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g0-preflight-status/`

G0/G1 external handoff preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g0-g1-external-handoff/`

G0/G1 handoff validator preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g0-g1-handoff-validator/`

G0/G1 handoff bridge preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g0-g1-handoff-bridge/`

G0/G1 valid examples preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g0-g1-valid-examples/`

Status valid-example drift preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-status-example-drift/`

Readiness doctor preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-readiness-doctor/`

Unresolved-blocker invariant preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-status-validator-unresolved-blockers/`

G1 intake linkage preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-status-validator-g1-links/`

G2-G9 run validator preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g2-g9-run-validator/`

G2-G9 coverage proof validator preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g2-g9-coverage-proof/`

G2-G9 evidence artifact validator preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g2-g9-evidence-artifacts/`

G10 adversarial review validator preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g10-adversarial-validator/`

G10 accepted-risk approval preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g10-risk-approval/`

G10 evidence artifact validator preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g10-evidence-artifacts/`

G11 hardening-window validator preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g11-hardening-validator/`

G11 hardening-window timestamp preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g11-window-timestamps/`

G11 evidence artifact validator preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g11-evidence-artifacts/`

G12 final recommendation validator preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g12-final-recommendation-validator/`

G12 cancellation-date validation preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g12-cancellation-date/`

G12 evidence rollup link validator preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g12-evidence-rollup-links/`

G12 approval/signoff validation preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g12-approval-signoffs/`

Status-manifest G12 approval-link preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-status-g12-approval-link/`

Status-manifest hygiene-scan preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-status-hygiene-scan/`

Evidence chain validator preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-evidence-chain-validator/`

Validator preflight packet:

- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-status-validator-drift-checks/`

G2/G3 coverage and retained-history packet:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g2-g3-coverage-retained-history-proof.md`

G4/G5 render and export reproducibility packet:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g4-g5-render-export-reproducibility-proof.md`

G6 parity worksheet proof packet:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g6-parity-worksheet-proof.md`

G7/G8 delivery and diagnostics proof packet:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g7-g8-delivery-diagnostics-proof.md`

G9 permissions, tenant isolation, audit, quota, and aggregate-only safety proof packet:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g9-safety-controls-proof.md`

G10 adversarial cancellation review packet:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g10-adversarial-review.md`

G11 hardening-window packet:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g11-hardening-window.md`

G12 final cancellation recommendation packet:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g12-final-cancellation-recommendation.md`

Review route before cancellation claims:

- Raj/Mira: cross-stream architecture and DashThis go/no-go blocker classification.
- Sofia/Andre: backend validation, aggregate-only payloads, catalog/metric correctness, and preview/export parity.
- Lina/Joel: frontend payload assumptions, report review UX, responsive report rendering.
- Omar/Hannah: stale/disconnected/missing-history diagnostics and support evidence clarity.

Known preflight signal:

- `adinsights-preflight` may still return `GATE_BLOCK` for architecture-level scope on this
  cross-stream evidence chain. G0 is resolved by the validated Raj/Mira decision; later gates still
  need fixed-target evidence and reviewer-specific clearance.
- Latest refreshed G0/G1 preflight captured 2026-06-16:
  `make adinsights-preflight PROMPT="Assess SLB DashThis cancellation-readiness G0 G1 review and fixed-target intake"`
  returned router action `clarify`, scope `ESCALATE_ARCH_RISK`, contract
  `WARN_POSSIBLE_CONTRACT_CHANGE`, release `GATE_BLOCK`, and security/PII verification warning.
- Persisted preflight packet set:
  `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake/`.
- Persisted checked preflight packet set:
  `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake-with-checks/`.
  Data-contract and observability prerequisite checks passed; production readiness failed because
  `AIRBYTE_TEMPLATE_META_METRICS_CONNECTION_ID` is required to bootstrap connections.
- Persisted post-local-gate preflight packet set:
  `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-after-local-backend-frontend-gates/`.
  After local backend/frontend gates passed, preflight still returned router action `resolve`, scope
  `ESCALATE_ARCH_RISK`, contract `WARN_POSSIBLE_CONTRACT_CHANGE`, release `GATE_BLOCK`, and
  security/PII warning.
- Latest coverage-rollup correction preflight captured 2026-06-16:
  `make adinsights-preflight PROMPT="Assess report.v1 coverage rollup correction for SLB cancellation readiness"`
  returned router action `clarify`, scope `ESCALATE_ARCH_RISK`, contract
  `WARN_POSSIBLE_CONTRACT_CHANGE`, release `GATE_BLOCK`, and security/PII warning. This remains an
  architecture/reviewer blocker, not a backend test failure.
- Latest evidence-bundle-command preflight captured 2026-06-16:
  `backend/.venv/bin/python docs/ops/skills/adinsights-release-readiness/scripts/run_preflight_skillchain.py --prompt "Assess SLB evidence bundle command for DashThis cancellation readiness" --changed-files-from-git --output-dir docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-evidence-bundle-command --format markdown`
  returned router action `clarify`, scope `ESCALATE_ARCH_RISK`, contract
  `WARN_POSSIBLE_CONTRACT_CHANGE`, release `GATE_BLOCK`, and security/PII warning. Persisted packet:
  `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-evidence-bundle-command/`.
  This remains a Raj/Mira architecture/reviewer blocker, not a backend test failure.
- Latest parity-comparator-command preflight captured 2026-06-16:
  `backend/.venv/bin/python docs/ops/skills/adinsights-release-readiness/scripts/run_preflight_skillchain.py --prompt "Assess SLB parity comparison command for DashThis cancellation readiness" --changed-files-from-git --output-dir docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-parity-compare-command --format markdown`
  returned router action `clarify`, scope `ESCALATE_ARCH_RISK`, contract
  `WARN_POSSIBLE_CONTRACT_CHANGE`, release `GATE_BLOCK`, and security/PII warning. Persisted packet:
  `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-parity-compare-command/`.
  This remains a Raj/Mira architecture/reviewer blocker, not a backend test failure.
- Latest evidence-validator-command preflight captured 2026-06-16:
  `backend/.venv/bin/python docs/ops/skills/adinsights-release-readiness/scripts/run_preflight_skillchain.py --prompt "Assess SLB evidence validation command for DashThis cancellation readiness" --changed-files-from-git --output-dir docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-evidence-validate-command --format markdown`
  returned router action `clarify`, scope `ESCALATE_ARCH_RISK`, contract
  `WARN_POSSIBLE_CONTRACT_CHANGE`, release `GATE_BLOCK`, and security/PII warning. Persisted packet:
  `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-evidence-validate-command/`.
  This remains a Raj/Mira architecture/reviewer blocker, not a backend test failure.
- Latest target-intake-command preflight captured 2026-06-16:
  `backend/.venv/bin/python docs/ops/skills/adinsights-release-readiness/scripts/run_preflight_skillchain.py --prompt "Assess SLB target intake command for DashThis cancellation readiness" --changed-files-from-git --output-dir docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-target-intake-command --format markdown`
  returned router action `clarify`, scope `ESCALATE_ARCH_RISK`, contract
  `WARN_POSSIBLE_CONTRACT_CHANGE`, release `GATE_BLOCK`, and security/PII warning. Persisted packet:
  `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-target-intake-command/`.
  This remains a Raj/Mira architecture/reviewer blocker, not a backend test failure.
- Latest history-probe-command preflight captured 2026-06-16:
  `backend/.venv/bin/python docs/ops/skills/adinsights-release-readiness/scripts/run_preflight_skillchain.py --prompt "Assess SLB retained-history probe command for DashThis cancellation readiness" --changed-files-from-git --output-dir docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-history-probe-command --format markdown`
  returned router action `clarify`, scope `ESCALATE_ARCH_RISK`, contract
  `WARN_POSSIBLE_CONTRACT_CHANGE`, release `GATE_BLOCK`, and security/PII warning. Persisted packet:
  `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-history-probe-command/`.
  This remains a Raj/Mira architecture/reviewer blocker, not a backend test failure.
- Latest readiness-doctor preflight captured 2026-06-16:
  `backend/.venv/bin/python docs/ops/skills/adinsights-release-readiness/scripts/run_preflight_skillchain.py --prompt "Assess SLB cancellation readiness doctor for DashThis cancellation readiness" --changed-files-from-git --output-dir docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-readiness-doctor --format markdown`
  returned router action `clarify`, scope `ESCALATE_ARCH_RISK`, contract
  `WARN_POSSIBLE_CONTRACT_CHANGE`, release `GATE_BLOCK`, and security/PII warning. Persisted packet:
  `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-readiness-doctor/`.
  This remains a Raj/Mira architecture/reviewer blocker, not a backend test failure.
- The production-readiness blocker is tracked in
  `docs/project/evidence/dashthis-replacement/external-prerequisites-checklist.md` and must be
  resolved or explicitly waived before hardening or cancellation readiness can be claimed.
- Local runtime audit confirms `/Users/thristannewman/ADinsights/backend/db.sqlite3` cannot supply
  the fixed SLB proof target: it has no SLB `report.v1` report, no export jobs, no `dashboard.v1`
  dashboards, missing Content Ops tables, and only stale/demo/fake/warehouse snapshots. Content Ops
  migrations are present but unapplied locally, and the SLB template creation path exists for
  local-only smoke validation.
- Local smoke validation later applied local Content Ops migrations, created a local-only SLB
  `report.v1` report, successfully ran the aggregate-only parity command, built
  preview/diagnostics/export metadata, and completed a local CSV export. After installing local
  Playwright Chromium, PDF/PNG export and scheduled dry-run artifact rendering also completed
  locally. This is not cancellation-review evidence because values were zero/empty and
  DashThis/source comparison is absent.
- Focused backend reporting tests passed locally:
  `backend/.venv/bin/pytest -q backend/tests/test_reporting_catalog.py backend/tests/test_phase2_api.py`
  returned `59 passed`. This supports implementation readiness only.
- Focused frontend reporting tests passed locally:
  `npm --prefix frontend test -- --run src/lib/phase2Api.test.ts src/routes/__tests__/DashboardCreate.test.tsx src/routes/__tests__/SavedDashboardPage.test.tsx src/routes/__tests__/ReportDetailPage.test.tsx src/routes/__tests__/ReportsPage.test.tsx`
  returned `40 passed` across 5 files. This supports implementation readiness only.
- Frontend guardrails, lint, and build passed locally:
  `make frontend-guardrails`, `make frontend-lint`, and `make frontend-build` all completed
  successfully. This supports frontend implementation readiness only; it does not prove fixed
  SLB runtime coverage, browser screenshot parity, or cancellation readiness.
- Canonical backend gates passed locally:
  `make backend-lint` completed with Ruff `All checks passed!`; `make backend-test` completed the
  full backend pytest suite successfully. This supports backend implementation readiness only.
- G2/G3/G8 coverage-semantics regression coverage was added and passed:
  focused report preview/diagnostics tests returned `2 passed`; the broader
  `backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py` slice passed; and
  `make backend-lint && make backend-test` passed. This proves local `report.v1` coverage summaries
  and diagnostics do not count manual `report_section` widgets or zero-count placeholders as
  retained dataset history, not fixed-runtime monthly/90-day coverage proof.
- G5 export snapshot reproducibility regression coverage was added and passed:
  focused completed-export snapshot test returned `3 passed` across CSV, PDF, and PNG; the broader
  `backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py` slice passed; and
  `make backend-lint && make backend-test` passed. This proves local completed `report.v1`
  CSV/PDF/PNG exports preserve the request-time `report_preview.preview_hash`,
  `report_preview.report_snapshot.preview_hash`, and ordered SLB pages, not fixed-runtime CSV/PDF/PNG
  artifact proof.
- G6 parity worksheet seed regression coverage was added and passed:
  focused parity command test returned `1 passed`; the broader
  `backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py` slice passed; and
  `make backend-lint && make backend-test` passed. This proves local ADinsights-side parity rows use
  the governed `blocked_missing_dashthis_value` result before comparison values are filled and omit
  manual narrative report sections, not fixed-runtime DashThis/source parity proof.
- G6 parity comparator regression coverage was added and passed:
  focused comparator tests returned `2 passed` and backend lint passed. This proves
  `slb_report_parity_compare` can merge a redacted comparison-values JSON file with evidence-bundle
  rows, compute absolute deltas, percent deltas, pass/fail decisions from percent or absolute
  tolerances, keep missing comparison values blocked, block rows with missing tolerance as
  `blocked_metric_semantics`, redact sensitive-looking source references, and run while live network
  calls are blocked. The broader reporting slice, `make backend-lint`, and `make backend-test`
  passed after adding the comparator. This improves parity calculation quality but does not close
  fixed-runtime G6 until real DashThis/source values, approved tolerances, explanations, and
  reviewer approvals are attached.
- G10/G11 evidence validation regression coverage was added and passed:
  focused validator tests returned `2 passed`; the broader reporting slice, `make backend-lint`,
  and `make backend-test` passed. This proves
  `slb_report_evidence_validate` can pass a complete artifact set and surface blockers for date-range
  mismatch, missing required datasets, blocking coverage states, zero-row datasets, missing pages,
  empty/missing exports, export hash drift, missing scheduled dry-run proof, unresolved parity
  results, and sensitive payload patterns. This improves adversarial/hardening readiness but does
  not close G10 or G11 until run against fixed G1 artifacts after G0-G9 evidence is complete.
- G1 target-intake regression coverage was added and passed:
  focused tests returned `2 passed`; the broader reporting slice, `make backend-lint`, and
  `make backend-test` passed. This proves `slb_report_target_intake` identifies a valid SLB
  `report.v1` candidate, reports required datasets/pages and scope-presence fields without exposing
  delivery emails or tokens, flags invalid Instagram-including targets, and completes with live
  network calls blocked. This reduces G1 operator error but does not close G1 until human-owned
  runtime fields and Raj/Mira review are complete.
- G2/G3 retained-history probe regression coverage was added and passed:
  focused history-probe test returned `1 passed` and backend lint passed. This proves
  `slb_report_history_probe` emits separate primary-month and 90-day custom date ranges, a required
  dataset matrix for `paid_meta_ads`, `organic_facebook_page`, and `content_ops`, stored aggregate
  row counts where available, blocked decisions for missing retained history, redacted audit
  metadata, no injected token output, and no live network/provider calls. This improves G2/G3
  evidence collection but does not close fixed-runtime monthly or 90-day proof.
- G2/G3/G8 source-health probe regression coverage was added and passed:
  focused history-probe test returned `1 passed`, `make backend-lint` passed, and `make
  backend-test` passed. This proves `slb_report_history_probe` now emits a redacted `source_health`
  section covering Meta credential status counts, Page connection scope coverage, sanitized Airbyte
  sync error categories, stored ad/Page asset counts, stored row ranges, and recommended next
  actions without exposing raw Meta errors, account IDs, Page IDs, tokens, or host paths. This
  improves the ability to answer whether Facebook is connected and what needs repair, but it is not
  fixed-target SLB coverage proof until run after G0/G1 approval.
- Local Airbyte destination connectivity was repaired for the demo workspace:
  the `Meta Metrics Connection Postgres` destination was updated from `host.docker.internal:5435`
  to `host.docker.internal:5432`, and Airbyte's destination check returned `status: succeeded`.
  This fixes the local destination refusal path only. Meta credentials still require reauth, no
  provider sync was run, and Page/Post/Content Ops backfills remain required before fixed-target
  proof or DashThis parity can be claimed.
- Local Airbyte destination validation tooling was added:
  `scripts/check_local_airbyte_destination.py` validates a destination or connection ID against the
  expected local Postgres host/port, optionally runs Airbyte's destination check, and emits only
  redacted config fields. Focused script tests returned `4 passed`, and the script passed against
  the repaired local destination with `valid: true` and `airbyte_check.status: succeeded`.
- G7 scheduled dry-run completion regression coverage was added and passed:
  focused dry-run completion and coverage-blocked dry-run tests each returned `1 passed`; the broader
  `backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py` slice passed; and
  `make backend-lint && make backend-test` passed. This proves local scheduled dry-runs can render a
  non-empty artifact, transition delivery status to `rendered`, avoid email sending, and create
  sanitized `blocked_by_coverage` failed evidence jobs when required coverage is missing, not
  fixed-runtime delivery proof.
- G8 diagnostics sync-recency regression coverage was added and passed:
  focused diagnostics test returned `1 passed`; the broader reporting slice and canonical backend
  gate passed. This proves local diagnostics propagate stored snapshot `last_successful_sync_at`
  into dataset diagnostics when available, not fixed-runtime support proof.
- Full frontend test gate passed locally:
  `make frontend-test` reported `139 passed` test files and `893 passed` tests. The run emitted
  non-fatal jsdom/React test-console warnings, so this should not be treated as real browser UX or
  cancellation evidence.
- Implementation safety audit captured in
  `docs/project/evidence/dashthis-replacement/2026-06-16-g9-safety-controls-proof.md` found no
  live provider client imports, token-decrypt paths, or Meta Direct calls in the `report.v1`
  preview/export-preflight boundary. This supports the stored-aggregate implementation claim, but
  fixed-target preview/export payload inspection is still required before G9/G10 can pass.
- Additional local release/prerequisite gates passed:
  `backend/.venv/bin/python backend/manage.py backend_release_preflight`,
  `python3 infrastructure/airbyte/scripts/check_data_contracts.py`, and
  `python3 infrastructure/airbyte/scripts/verify_observability_prereqs.py`.
  `python3 infrastructure/airbyte/scripts/verify_production_readiness.py` still fails because
  `AIRBYTE_TEMPLATE_META_METRICS_CONNECTION_ID` is required to bootstrap connections.
- G9 quota regression coverage was added and passed:
  `backend/.venv/bin/pytest -q backend/tests/test_phase2_api.py::test_report_actions_return_sanitized_quota_blocks ...`
  returned `7 passed` for focused report safety paths, and
  `backend/.venv/bin/pytest -q backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py`
  returned `62 passed`. The post-change backend canonical gate
  `make backend-lint && make backend-test` also passed. This proves sanitized quota-block behavior
  in tests, not fixed-runtime quota evidence.
- G9 report privilege/audit regression coverage was added and passed:
  focused permission/audit tests returned `3 passed`; the broader
  `backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py` slice returned
  `64 passed`; `make backend-lint && make backend-test` passed. This proves local viewer/analyst/admin
  report action separation and schedule/delete audit redaction in tests, not fixed-runtime reviewer evidence.
- G9 report tenant-isolation regression coverage was added and passed:
  focused cross-tenant report action/export-history tests returned `10 passed`; the broader
  `backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py` slice passed; and
  `make backend-lint && make backend-test` passed. This proves local report object isolation and
  export-history tenant filtering in tests, not fixed-runtime tenant proof.
- G9 audit-redaction regression coverage was added and passed:
  focused SLB workflow/parity audit tests returned `2 passed`; the broader
  `backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py` slice passed; and
  `make backend-lint && make backend-test` passed. This proves local redacted audit metadata for
  SLB template creation, preview, diagnostics, export request/block, scheduled dry-run, and parity
  generation in tests, not fixed-runtime audit proof.
- G9 report mutation audit-redaction regression coverage was added and passed:
  focused create/update plus SLB workflow/parity audit tests returned `3 passed`; the broader
  `backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py` slice passed; and
  `make backend-lint && make backend-test` passed. This proves local field-name-only metadata for
  report create/update and completes local implementation coverage for the listed G9 audit-event
  rows, not fixed-runtime audit proof.
- G9 aggregate-output redaction coverage was added and passed:
  focused preview/diagnostics/export/dry-run/parity payload redaction test returned `1 passed`;
  the broader `backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py` slice
  passed; and `make backend-lint && make backend-test` passed. This proves local report output
  surfaces exclude injected token, secret, raw payload, delivery email, recipient, and user-level
  identifier strings in tests, not fixed-runtime payload proof.
- G9 no-live-provider regression coverage was added and passed:
  focused report preview/export/dry-run/parity test returned `1 passed` while socket, `urllib`,
  `requests`, and `httpx` network calls were blocked; the broader
  `backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py` slice passed; and
  `make backend-lint && make backend-test` passed. This proves the local report preview/export
  preflight, scheduled dry-run metadata, and parity evidence paths do not open live provider/network
  connections in tests, not fixed-runtime payload proof.
- G2-G9 fixed-target evidence bundle command was added and passed focused tests:
  `slb_report_evidence_bundle` emits `schema_version="slb_evidence_bundle.v1"` with the fixed custom
  date range, report metadata, preview hash, coverage summary, diagnostics for the same date range,
  diagnostics source health, rendering page/widget summary, export status/hash/artifact-size
  summary, and parity rows. Focused tests verify the command output is redacted, audit metadata is
  limited to date range/hash/row count, and the command runs inside the same blocked-network
  no-live-provider regression. The
  reporting slice, `make backend-lint`, and `make backend-test` passed after the command was added.
  This improves repeatable fixed-target evidence collection; it does not close G2-G9 until the
  command is run against the approved G1 runtime target and the remaining screenshots, artifact
  downloads, DashThis/source comparison values, and reviewer approvals are attached.
- G9 evidence-file hygiene scan was completed for the current DashThis evidence folder:
  high-signal credential and email-address scans found no matches. A broader keyword scan found
  only placeholders such as `<operator-token>`, route examples, `.env.sample` references, and
  policy/checklist text. Future fixed-target screenshots, exports, and copied runtime snippets
  still need their own scan before cancellation review.
- G10 pre-adversarial implementation review was filled:
  `2026-06-16-g10-adversarial-review.md` now records implementation-level evidence for tenant
  isolation, coverage blocking, disconnected-source labeling, Instagram deferral, aggregate-output
  redaction, artifact safety, CSV formula safety, dry-run sanitization, quota blocks, and audit
  redaction. G10 remains not executed for cancellation until G0-G9 fixed-target evidence exists.
  The machine-readable G10 validator now requires each adversarial row to link to an existing
  evidence artifact, so implementation notes alone cannot advance the work into G11 hardening.

## Required SLB Sections

G4/G5 render/export collection protocol:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g4-g5-render-export-reproducibility-proof.md`

| Section | Dataset | Evidence status | Notes |
| --- | --- | --- | --- |
| Cover and period | Report scaffold | Implemented path | Narrative section; inherits appendix coverage notes. |
| Executive summary | `paid_meta_ads`, `organic_facebook_page` | Implemented path | Renders governed KPI widgets. |
| Paid Meta Ads | `paid_meta_ads` | Implemented path | Must use `require_full_coverage` for cancellation proof. |
| Organic Facebook/Page | `organic_facebook_page` | Implemented path | Stored Page/Post Insight rows only. |
| Top posts | `organic_facebook_page` | Implemented path | Stored post insight rows only. |
| Content activity | `content_ops` | Implemented path | Uses aggregate Content Ops snapshots/published-post counts. |
| Recommendations | Report scaffold | Implemented path | Must not hide stale/partial states. |
| Appendix/data notes | All bound datasets | Implemented path | Must list coverage summary before cancellation review. |
| Instagram | `organic_instagram` | Deferred | Future-gated until data/scope readiness is proven. |

## Parity Worksheet

G6 SLB-specific worksheet protocol:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g6-parity-worksheet-proof.md`

| Metric/output | ADinsights source | DashThis/source comparison | Coverage status | Result |
| --- | --- | --- | --- | --- |
| Paid spend | `paid_meta_ads` | Pending fixed-range comparison | Pending | Not approved |
| Paid impressions | `paid_meta_ads` | Pending fixed-range comparison | Pending | Not approved |
| Paid reach | `paid_meta_ads` | Pending fixed-range comparison | Pending | Not approved |
| Paid clicks | `paid_meta_ads` | Pending fixed-range comparison | Pending | Not approved |
| CTR/CPC/CPM | `paid_meta_ads` | Pending fixed-range comparison | Pending | Not approved |
| Conversions | `paid_meta_ads` | Pending fixed-range comparison | Pending | Not approved |
| Organic reach/impressions | `organic_facebook_page` | Pending fixed-range comparison | Pending | Not approved |
| Organic engagement/actions | `organic_facebook_page` | Pending fixed-range comparison | Pending | Not approved |
| Follows/fans | `organic_facebook_page` | Pending fixed-range comparison | Pending | Not approved |
| Top posts | `organic_facebook_page` | Pending fixed-range comparison | Pending | Not approved |
| Published/scheduled/approved counts | `content_ops` | Pending fixed-range comparison | Pending | Not approved |

Generate the ADinsights-side worksheet rows with:

```bash
backend/.venv/bin/python backend/manage.py slb_report_parity_evidence \
  --report-id <slb-report-id> \
  --start-date YYYY-MM-DD \
  --end-date YYYY-MM-DD \
  --format markdown
```

The command output must remain aggregate-only. Add DashThis/source-platform values, absolute delta,
percentage delta, accepted tolerance, pass/fail, and explanation manually in the worksheet before
any cancellation recommendation.

## Snapshot And Diagnostics Evidence

G2/G3 collection protocol:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g2-g3-coverage-retained-history-proof.md`

G7/G8 diagnostics and scheduled dry-run protocol:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g7-g8-delivery-diagnostics-proof.md`

For every SLB export used as evidence, capture:

- `ReportExportJob.id`
- `ReportExportJob.export_format`
- `ReportExportJob.status`
- `metadata.report_preview.preview_hash`
- `metadata.report_preview.report_snapshot.generated_at`
- `metadata.report_preview.report_snapshot.pages[*].id`
- `metadata.report_preview.coverage_summary`
- `metadata.delivery_status`

Report Detail must show whether the visible preview hash matches the latest export snapshot hash.
If the source disconnects after export, the completed export metadata must still explain what was
rendered without making fresh provider calls.

Use `GET /api/reports/{id}/diagnostics/` to record:

- Dataset coverage status.
- Retained start/end dates.
- Aggregate row counts.
- Source label.
- Recent export history.
- Blocking reasons.
- Recommended next action.

No provider tokens, secrets, user-level metrics, or raw user engagement data are allowed in the
diagnostics packet.

## Scheduled Delivery Dry-Run Evidence

G7/G8 diagnostics and scheduled dry-run protocol:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g7-g8-delivery-diagnostics-proof.md`

Use `POST /api/reports/{id}/scheduled-dry-run/` before any real client delivery claim.

Required proof:

- Dry-run creates a `ReportExportJob`.
- `metadata.delivery_status.mode == "dry_run"`.
- Coverage-blocked reports record `blocked_by_coverage` and do not imply delivery success.
- Rendered dry-runs record a generated export artifact without sending client email.
- Failure messages are sanitized and do not include secrets or provider payloads.

## Evidence To Attach Before Cancellation Review

- Current blocker register with every blocker resolved, waived by the correct reviewer, or accepted
  as a reason to keep DashThis active.
- Report ID and template key.
- Fixed reporting date range in America/Jamaica.
- Completed G1 runtime target intake checklist with target environment, safe tenant/client,
  report ID, template key, `report.v1` confirmation, source scopes, comparison owner, delivery
  assumptions, Instagram deferral, and DashThis active status.
- Filled G0/G1 review and fixed-target intake handoff, including Raj/Mira decision record and
  operator-confirmed runtime target values.
- G1 fixed proof-target confirmation, including target environment, safe tenant/client identifier,
  account/Page scope, recipient assumptions, DashThis/source comparison owner, and Instagram
  deferral.
- Completed G2-G9 fixed-range execution checklist, or explicit notes showing which steps are
  blocked and why.
- G2/G3 stored coverage and retained-history proof for `paid_meta_ads`, `organic_facebook_page`, and
  `content_ops`, with monthly and 90-day ranges evaluated separately.
- G4/G5 rendering and export reproducibility proof, including saved `dashboard.v1` evidence, SLB
  `report.v1` screenshots or verified UI paths, CSV/PDF/PNG job IDs, non-empty download checks, and
  matching preview/snapshot hashes.
- G6 filled parity worksheet with ADinsights values, DashThis/source values, absolute deltas,
  percentage deltas, accepted tolerances, pass/fail decisions, and explanations for every required
  non-Instagram metric.
- G7/G8 scheduled dry-run and diagnostics proof, including dry-run job ID, `delivery_status`,
  no-client-email evidence, retained-history diagnostics, safe export history, blocking reasons, and
  support next actions.
- G9 safety proof, including role/privilege behavior, cross-tenant rejection, redacted audit events,
  preview/export/scheduled-dry-run quota evidence, and aggregate-only payload verification.
- G10 adversarial review, including date range, tenant/source mismatch, stale/partial/missing
  history, unsupported Instagram assumptions, empty/corrupt artifacts, delivery failure,
  cross-tenant leakage, quota bypass, audit gaps, and rollback readiness.
- G11 24-48 hour hardening-window evidence, including checkpoint timestamps, preview/diagnostics,
  exports, dry-run, freshness/sync state, safety checks, gate snapshots, reset conditions, and final
  reviewer approval.
- G12 final keep/cancel recommendation, including evidence rollup, reviewer sign-offs,
  rollback/monitoring plan, business decision record, and explicit DashThis action.
- Preview hash from `POST /api/reports/{id}/preview/`.
- Coverage summary by dataset and status.
- Export job IDs for CSV, PDF, and PNG.
- Export snapshot hash and generated timestamp.
- Diagnostics payload summary.
- Scheduled dry-run job ID and delivery status.
- Download proof that artifacts are non-empty.
- Backend/frontend/preflight command results.
- DashThis/source-platform comparison values and accepted tolerance.
- Adversarial review results and unresolved blockers.
- 24-48 hour hardening window result.

## Adversarial Review Checklist

- G10 adversarial protocol is complete:
  `docs/project/evidence/dashthis-replacement/2026-06-16-g10-adversarial-review.md`.
- G9 safety protocol is complete:
  `docs/project/evidence/dashthis-replacement/2026-06-16-g9-safety-controls-proof.md`.
- Report actions are permission-gated by the expected report privileges.
- Cross-tenant report/client/account/page references are rejected.
- User-level metrics are not exposed.
- Audit events are redacted and contain no provider payloads or secrets.
- Preview/export/scheduled dry-run quotas block abuse with sanitized errors.
- Stale data is never labeled fresh.
- Partial retained history is visible before preview/export.
- Missing history blocks when policy requires full coverage.
- Source-disconnected-with-history renders only with clear notes.
- Unsupported Instagram sections remain absent from the v1 template.
- CSV export sanitizes formula-leading cells.
- PDF/PNG artifacts are non-empty and inside the export artifact root.
- Long labels and tables do not overlap on desktop or mobile.
- Rollback and monitoring plan are explicit before any cancellation recommendation.

## Hardening Window

G11 hardening-window protocol:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g11-hardening-window.md`

Do not start the 24-48 hour hardening clock until G10 passes. During the window, DashThis must
remain active and every checkpoint must capture report preview, diagnostics, export proof,
scheduled dry-run, freshness/sync state, safety checks, UI proof, and gate snapshots for the same
fixed G1 report/date range.

The G11 packet now includes a pre-window readiness checklist, checkpoint command pack, redaction
scan command, and checkpoint result template. This prepares the hardening window execution but does
not start G11 or satisfy the hardening requirement.
The machine-readable G11 template and validator now also require concrete checkpoint/final
validation/redaction/export-snapshot evidence file paths, so G12 cannot rely on status fields alone.

Any reset condition in the G11 packet returns the work to the owning sub-goal before a new
hardening window can start.

## Final Recommendation

G12 final recommendation protocol:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g12-final-cancellation-recommendation.md`

Current recommendation: keep DashThis active. The recommendation can move to
`cancellation_review_ready` or `cancel_dashthis_recommended` only after G0-G11 are passed,
reviewer sign-offs are recorded as non-blocking approval values, rollback/monitoring is documented,
and the business owner accepts the scope and final keep/cancel action.

The G12 packet now includes a current no-go summary, post-cancellation monitoring template,
reversal triggers, and decision change log. Current decision remains `keep_dashthis_active`.

## Reviewer Route

- Raj: cross-stream scope and DashThis go/no-go.
- Mira: report preview/export architecture and schema-versioning.
- Sofia: backend API validation and tenant isolation.
- Andre: metric/dataset/catalog correctness.
- Lina: frontend report/dashboard rendering assumptions.
- Joel: shared widget component/responsive behavior.
- Omar: stale/disconnected/missing-history operational states.
- Hannah: support notes and evidence clarity.
- Priya/Martin: required only if retained-history proof requires dbt/mart changes.

## Current Decision

Implementation: go, pending full gate results and Raj/Mira review.

DashThis cancellation: no-go. Cancellation requires completed parity worksheet, non-empty CSV/PDF/PNG
export evidence, visible coverage notes, passing tenant-isolation tests, adversarial review with no
unresolved blocker, and a 24-48 hour hardening record.
