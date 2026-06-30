# SLB Cancellation-Readiness Blocker Register

Date: 2026-06-16
Timezone: America/Jamaica
Status: active blocker register; DashThis cancellation remains no-go.

## Purpose

Track the specific blockers that prevent ADinsights from reaching SLB DashThis
cancellation-review readiness. This register separates external/reviewer/runtime blockers from
ordinary evidence work so future sessions can pick the right next action without rediscovering the
same gaps.

This register does not replace the G0-G12 goal controller. It is the current no-go ledger.

Machine-readable status for future sessions is tracked in:

`docs/project/evidence/dashthis-replacement/2026-06-16-slb-cancellation-readiness-status.json`

Validate the manifest with:

```bash
python3 scripts/validate_slb_cancellation_readiness_status.py
```

The validator fails if the blocker statuses in this register drift from the machine-readable status
manifest, if a sub-goal is marked `passed` while a linked blocker remains unresolved, or if
cancellation-review readiness moves beyond `no_go` while any G0-G11 blocker remains unresolved.

Focused regression coverage:

```bash
cd backend
PYTHONPATH=.. ./.venv/bin/pytest -q ../scripts/tests/test_validate_slb_cancellation_readiness_status.py
```

The focused suite now includes false pass and false review-readiness regression cases.

Validator test preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-status-validator-tests/`

Latest unresolved-blocker invariant preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-status-validator-unresolved-blockers/`

Latest validator preflight remains blocked on architecture-level scope review:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-status-validator-drift-checks/`

## Blocker Status Key

- `open`: blocks at least one cancellation-readiness sub-goal.
- `waiting_external`: needs a reviewer, operator, source owner, or runtime configuration.
- `evidence_needed`: implementation path may exist, but fixed-range proof is missing.
- `resolved`: blocker has evidence and no longer blocks the named goal.
- `waived`: correct reviewer explicitly accepts the risk for this proof chain.

## Active Blockers

| ID      | Blocker                                                                                                          | Status             | Affects                            | Owner/reviewer route                                          | Required unblock action                                                                                                                                                                                                                                                                                                                                              | Evidence path                                                                                                                                        |
| ------- | ---------------------------------------------------------------------------------------------------------------- | ------------------ | ---------------------------------- | ------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| BLK-001 | Raj/Mira architecture/scope classification for the cross-stream `GATE_BLOCK` is recorded.                        | `resolved`         | G0                                 | Raj, Mira                                                     | Resolved by validated conditional approval. G1-G11 evidence capture may proceed with followups; DashThis cancellation remains no-go.                                                                                                                                                                                                                                 | `2026-06-17-g0-raj-mira-agent-review-decision.json`; `2026-06-16-g0-raj-mira-review-packet.md`                                                       |
| BLK-002 | G1 runtime target is not filled.                                                                                 | `waiting_external` | G1-G11                             | Operator, Raj, Hannah                                         | Fill target environment, backend/frontend URLs, safe tenant/client, real `ReportDefinition.id`, template key, `report.v1`, date range, source scopes, comparison owner, delivery assumptions, Instagram deferral, and DashThis active status. Local audit confirms the current SQLite DB has no SLB `report.v1` candidate, though the template creation path exists. | `2026-06-16-g1-runtime-target-intake-checklist.md`; `2026-06-16-local-runtime-state-audit.md`                                                        |
| BLK-003 | Airbyte production-readiness check fails because `AIRBYTE_TEMPLATE_META_METRICS_CONNECTION_ID` is missing.       | `waiting_external` | G11, G12; release/hardening claims | Raj, Mira, Carlos/Mei if runtime/deploy path changes          | Configure the non-secret target-runtime template connection ID or approve an alternative bootstrap path that makes production readiness pass.                                                                                                                                                                                                                        | `external-prerequisites-checklist.md`; `preflight/2026-06-16-g0-g1-review-target-intake-with-checks/README.md`                                       |
| BLK-004 | DashThis/source comparison values are not attached for the fixed SLB range.                                      | `waiting_external` | G6, G10-G12                        | DashThis/source comparison owner, Andre, Raj, business owner  | Provide safe fixed-range comparison values or redacted evidence references for every required non-Instagram metric; fill deltas, tolerances, results, and explanations.                                                                                                                                                                                              | `2026-06-16-g6-parity-worksheet-proof.md`; `source-platform-comparison-worksheet.md`                                                                 |
| BLK-005 | Stored coverage and retained-history proof has not been captured for the fixed runtime target.                   | `evidence_needed`  | G2, G3, G6-G12                     | Sofia, Andre, Omar; Priya/Martin if dbt/retention gap appears | Run fixed-range preview and diagnostics after G1; classify monthly and 90-day history for `paid_meta_ads`, `organic_facebook_page`, and `content_ops`. Local audit confirms current SQLite cannot prove `content_ops` coverage because Content Ops tables are missing.                                                                                               | `2026-06-16-g2-g3-coverage-retained-history-proof.md`; `2026-06-16-g2-g9-evidence-execution-checklist.md`; `2026-06-16-local-runtime-state-audit.md` |
| BLK-006 | Report rendering and CSV/PDF/PNG export reproducibility proof is missing.                                        | `evidence_needed`  | G4, G5, G10-G12                    | Lina, Joel, Sofia, Omar, Nina if artifact sensitivity appears | Capture fixed-range saved dashboard/report rendering evidence, export job IDs, non-empty download checks, safe artifact paths, and matching preview/snapshot hashes.                                                                                                                                                                                                 | `2026-06-16-g4-g5-render-export-reproducibility-proof.md`                                                                                            |
| BLK-007 | Scheduled delivery dry-run and diagnostics support proof are missing.                                            | `evidence_needed`  | G7, G8, G10-G12                    | Omar, Hannah, Sofia                                           | Capture fixed-range dry-run job with `delivery_status.mode == "dry_run"`, proof no client email was sent, diagnostics retained-range/state summary, and sanitized support next actions.                                                                                                                                                                              | `2026-06-16-g7-g8-delivery-diagnostics-proof.md`                                                                                                     |
| BLK-008 | Safety evidence is missing for permissions, tenant isolation, audit events, quotas, and aggregate-only payloads. | `evidence_needed`  | G9-G12                             | Sofia, Nina, Omar, Raj                                        | Fill permission, cross-tenant, audit, quota, and redaction matrices against the fixed G1 report/date range.                                                                                                                                                                                                                                                          | `2026-06-16-g9-safety-controls-proof.md`                                                                                                             |
| BLK-009 | Adversarial review has not run against the fixed evidence chain.                                                 | `evidence_needed`  | G10-G12                            | Raj, Mira, Omar, Hannah, Nina as needed                       | Run adversarial checklist after G0-G9 evidence exists; convert every issue into a fix, waiver, evidence note, or cancellation blocker.                                                                                                                                                                                                                               | `2026-06-16-g10-adversarial-review.md`                                                                                                               |
| BLK-010 | 24-48 hour hardening window has not started.                                                                     | `evidence_needed`  | G11, G12                           | Raj, Mira, Omar                                               | Start only after G10 has no unresolved blocker or unaccepted high-risk issue; record checkpoint evidence and final gate snapshot.                                                                                                                                                                                                                                    | `2026-06-16-g11-hardening-window.md`                                                                                                                 |
| BLK-011 | Final keep/cancel recommendation cannot be written.                                                              | `open`             | G12                                | Raj, Mira, business owner                                     | Complete or explicitly waive G0-G11; write evidence rollup, rollback/monitoring plan, reviewer sign-offs, and business decision record.                                                                                                                                                                                                                              | `2026-06-16-g12-final-cancellation-recommendation.md`                                                                                                |

## Current Human Action Queue

These are the shortest external actions that unblock the most downstream work:

| Priority | Owner                                    | Ask                                                                                                                                                         | Unblocks             |
| -------- | ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------- |
| 1        | Operator + Hannah                        | Fill the G1 fixed SLB runtime target with safe tenant/client, report ID, fixed date range, source scopes, delivery assumptions, and DashThis active status. | BLK-002; G2-G11      |
| 2        | DashThis/source comparison owner + Andre | Provide redacted DashThis/source values, tolerances, and explanations for required non-Instagram SLB metrics.                                               | BLK-004; G6, G10-G12 |
| 3        | Runtime owner + Raj/Mira                 | Resolve `AIRBYTE_TEMPLATE_META_METRICS_CONNECTION_ID` or approve an alternate bootstrap path.                                                               | BLK-003; G11-G12     |

## 2026-06-30 Local G1 Draft

Local product-finish evidence has produced a G1 draft, but BLK-002 remains `waiting_external`.

Artifacts:

- `docs/project/evidence/dashthis-replacement/2026-06-30-slb-target-intake.local-product-finish.json`
- `docs/project/evidence/dashthis-replacement/2026-06-30-g1-runtime-target-intake.local-draft.json`

The draft fills the report ID, template, schema, date range, safe tenant/client labels, selected
paid account scope, dry-run recipient assumption, G0 conditional approval values, and source
comparison file path. It still fails `validate_slb_g1_runtime_target_intake.py` with 10 expected
errors: missing backend URL, frontend URL, currency, tenant-owned SLB Page scope, Content Ops
workspace scope, comparison owner, tolerance confirmation, `candidate_ready_for_review` status, and
target-intake source-scope evidence for Page/workspace.

After G0/G1 are complete, use `2026-06-16-g2-g9-evidence-execution-checklist.md` as the single-run
fixed-target evidence controller. It now includes a run sheet, temporary output naming convention,
and pre-G10 completion matrix.

## G1 Target Intake Command

Added `slb_report_target_intake` to summarize a candidate SLB `ReportDefinition` before fixed-range
evidence collection starts. The command validates the governed report layout, emits
`slb_target_intake.v1`, checks the expected SLB template, required datasets/pages, source-scope
presence, schedule/delivery counts, sensitive-pattern detection, and Instagram deferral without
printing recipient emails, tokens, raw provider payloads, or user-level identifiers. Focused tests
verify a valid SLB candidate and an invalid Instagram-including target. BLK-002 remains open until
the operator fills the real environment, safe tenant/client, source scopes, recipient assumptions,
DashThis active status, and Raj/Mira review route.
Preflight for this command was persisted under
`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-target-intake-command/` and
still returns release `GATE_BLOCK` from architecture-level scope risk with a possible-contract-change
warning. BLK-001 is now resolved by the validated G0 decision; the preflight result remains a
scope-review warning for later evidence gates.

## Local Smoke Evidence

Local smoke validation is recorded in:

`docs/project/evidence/dashthis-replacement/2026-06-16-local-slb-smoke-validation.md`

This reduces implementation uncertainty but does not resolve any blocker above. It is local SQLite
evidence only, with zero/empty values and no DashThis/source comparison. The extended local smoke
showed CSV export completion first; after installing local Playwright Chromium, PDF/PNG and
scheduled dry-run artifact rendering also completed locally. G5 still requires fixed-target
CSV/PDF/PNG evidence. Focused backend reporting tests passed locally (`59 passed`) but do not close
fixed-runtime blockers. Focused frontend reporting tests also passed locally (`40 passed`) and are
implementation-readiness evidence only. Broader frontend guardrails, lint, and build gates also
passed locally, but remain implementation-readiness evidence until run against the approved fixed
SLB proof target and paired with real coverage/parity evidence. Canonical backend lint/test gates
and the full frontend test gate also passed locally (`make backend-lint`, `make backend-test`,
`make frontend-test`), but these do not resolve the fixed-runtime, parity, review, adversarial, or
hardening blockers.

## Latest Preflight Evidence

After the local backend/frontend gates passed, the release-readiness preflight was rerun and
persisted in:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-after-local-backend-frontend-gates/`

Result: router action `resolve`, scope `ESCALATE_ARCH_RISK`, contract
`WARN_POSSIBLE_CONTRACT_CHANGE`, release `GATE_BLOCK`, and security/PII warning. This remains an
architecture scope warning, not a local test-gate failure; BLK-001 is resolved by the G0 decision.

## Safety/PII Implementation Audit

The G9 packet now includes an implementation safety audit of the reporting preview/export boundary.
It found no live provider client imports, Meta Direct calls, HTTP client calls, or token-decrypt
paths in the `report.v1` preview/export-preflight modules. This reduces the security/PII warning
from an implementation-unknown to a reviewer-confirmation item, but it does not close BLK-008 until
fixed-target preview, diagnostics, export metadata, dry-run metadata, parity output, permissions,
tenant isolation, audit, and quota evidence are captured and reviewed.

## Fresh Release/Prerequisite Gate Snapshot

Latest local gate results:

| Gate                                                                     | Result | Interpretation                                                                                                                           |
| ------------------------------------------------------------------------ | ------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/.venv/bin/python backend/manage.py backend_release_preflight`   | Passed | Local deterministic backend release preflight is green; Airbyte/dbt health returned allowed degraded local statuses, not live readiness. |
| `python3 infrastructure/airbyte/scripts/check_data_contracts.py`         | Passed | Data-contract validation passed.                                                                                                         |
| `python3 infrastructure/airbyte/scripts/verify_observability_prereqs.py` | Passed | Observability prerequisite validation passed.                                                                                            |
| `python3 infrastructure/airbyte/scripts/verify_production_readiness.py`  | Failed | BLK-003 remains open: `AIRBYTE_TEMPLATE_META_METRICS_CONNECTION_ID` is required to bootstrap connections.                                |

This snapshot reduces local gate uncertainty but does not close G0, G1, BLK-003, or any fixed SLB
runtime evidence blocker.

## G2/G3/G8 Coverage-Semantics Regression Evidence

Added and ran focused backend coverage proving `report.v1` manual narrative sections do not count
as stored dataset coverage and zero-row datasets do not claim retained start/end dates. The focused
preview/diagnostics tests returned `2 passed`; the broader reporting slice and canonical backend
gate passed. This reduces the risk of overstating Content Ops retained history in evidence packets,
but BLK-005 and BLK-007 remain open until fixed-target monthly/90-day coverage, diagnostics, and
reviewer evidence are complete.

Added `slb_report_history_probe` to collect primary-month and retained-90-day coverage/diagnostics
summaries for `paid_meta_ads`, `organic_facebook_page`, and `content_ops` in one command. Focused
tests verify separate date ranges, dataset matrix decisions, redacted audit metadata, no injected
token output, and no-live-provider behavior. BLK-005 remains open until this command is run against
the approved G1 report/date ranges and any blocked retained-history rows are resolved or accepted.
Preflight for this command is persisted at
`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-history-probe-command/` and
still returns release `GATE_BLOCK` from architecture-level scope risk.

## G5 Export Snapshot Reproducibility Regression Evidence

Added and ran focused backend coverage proving completed `report.v1` CSV, PDF, and PNG exports preserve the
request-time `report_preview.preview_hash`, durable `report_snapshot.preview_hash`, and ordered SLB
pages after the export task writes non-empty artifacts. Focused completed-export coverage returned
`3 passed`; the broader reporting slice and canonical backend gate passed. BLK-006 remains open
until fixed-target CSV/PDF/PNG export jobs, downloads, artifact checks, and reviewer evidence are
complete.

## G6 Parity Worksheet Seed Regression Evidence

Added and ran focused backend coverage proving `slb_report_parity_evidence` emits worksheet rows
with the governed `blocked_missing_dashthis_value` result when DashThis/source comparison values are
not yet filled, and excludes manual report sections from parity rows. Focused parity command
coverage returned `1 passed`; the broader reporting slice and canonical backend gate passed.
BLK-004 remains open until fixed-target DashThis/source values, deltas, tolerances, explanations,
and reviewer approvals are complete.

Added `slb_report_parity_compare` to merge evidence-bundle parity rows with a redacted
comparison-values JSON file and compute absolute deltas, percentage deltas, pass/fail outcomes, and
blocked states. Focused tests verify pass/fail behavior for percent and absolute tolerances,
`blocked_missing_dashthis_value` for missing source values, `blocked_missing_adinsights_value` for
source-present/report-missing rows, `blocked_metric_semantics` for missing
tolerance, sensitive source-reference redaction, and no-live-provider behavior. BLK-004 remains open
until real DashThis/source values, approved tolerances, explanations, and reviewer approvals are
attached for the fixed G1 report/date range.
Preflight for this command was persisted under
`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-parity-compare-command/` and
still returns release `GATE_BLOCK` from architecture-level scope risk with a possible-contract-change
warning. BLK-001 is resolved by the validated G0 decision; later gates still need their own evidence.

## G10/G11 Evidence Artifact Validator

Added `slb_report_evidence_validate` to check fixed-target evidence artifacts offline before G10 or
G11 claims. The validator inspects the evidence bundle and parity comparison for date-range
consistency, required datasets, blocking coverage states, zero-row datasets, required report pages,
non-empty CSV/PDF/PNG export summaries, preview/snapshot hash consistency, rendered scheduled
dry-run evidence, unresolved parity rows, Instagram leakage, and high-signal sensitive payload
patterns. Focused tests verify both pass and blocker outputs. BLK-009 and BLK-010 remain open until
the validator is run against approved fixed G1 artifacts after G0-G9 evidence is complete and any
blocker is resolved or explicitly accepted.
Preflight for this command was persisted under
`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-evidence-validate-command/` and
still returns release `GATE_BLOCK` from architecture-level scope risk with a possible-contract-change
warning. BLK-001 is resolved by the validated G0 decision; later gates still need their own evidence.

## G7 Scheduled Dry-Run Completion Regression Evidence

Added and ran focused backend coverage proving a scheduled report dry-run can complete the export
task, write a non-empty artifact, transition `metadata.delivery_status.status` to `rendered`, and
avoid client email sending. The regression also verifies dry-run metadata does not include recipient
email values or `delivery_emails`. Focused dry-run completion coverage returned `1 passed`; the
broader reporting slice and canonical backend gate passed. Additional blocked-path coverage verifies
coverage-blocked dry-runs create sanitized failed evidence jobs with `blocked_by_coverage`, no
artifact path, and no export enqueue; that focused test also returned `1 passed`. BLK-007 remains
open until fixed-target dry-run job evidence, no-client-email proof, diagnostics, and reviewer
evidence are complete.

## G8 Diagnostics Sync-Recency Regression Evidence

Added and ran focused backend coverage proving report diagnostics propagate stored snapshot
`last_successful_sync_at` into dataset diagnostics when coverage metadata provides it. The same test
continues to verify empty Content Ops coverage reports missing history with no retained range.
Focused diagnostics coverage returned `1 passed`; the broader reporting slice and canonical backend
gate passed. BLK-007 remains open until fixed-target diagnostics, no-secret payload evidence, and
reviewer evidence are complete.

## G9 Quota Regression Evidence

Added and ran focused backend coverage for report preview/export/scheduled dry-run quota blocks.
The regression verifies sanitized HTTP 429 responses do not include traceback text, SQL fragments,
`access_token`, or `secret` strings. Focused report safety paths returned `7 passed`; the broader
`backend/tests/test_phase2_api.py backend/tests/test_reporting_catalog.py` slice returned
`62 passed`. BLK-008 remains open until fixed-target permissions, tenant isolation, audit, quota,
payload redaction, and reviewer evidence are complete.

## G9 Permission/Audit Regression Evidence

Added and ran focused backend coverage for local report privilege separation and schedule/delete
audit redaction. The regression verifies viewer read-only behavior, analyst preview/export/edit
without schedule/delete authority, admin schedule/delete authority, and redacted schedule/delete
audit metadata. Focused permission/audit tests returned `3 passed`; the broader reporting slice
returned `64 passed`; the canonical backend gate passed. BLK-008 remains open until the same safety
claims are proven against the fixed G1 SLB runtime target and reviewed.

## G9 Tenant-Isolation Regression Evidence

Added and ran focused backend coverage for cross-tenant report object access and export-history
filtering. Cross-tenant report IDs return `404` for retrieve, preview, diagnostics, export history,
export creation, scheduled dry-run, schedule toggle, edit, and delete; mismatched-tenant export jobs
are filtered from an otherwise accessible report's export history. Focused tenant-isolation tests
returned `10 passed`; the broader reporting slice and canonical backend gate passed. BLK-008
remains open until fixed-target runtime tenant isolation evidence is captured and reviewed.

## G9 Audit-Redaction Regression Evidence

Added and ran focused backend coverage for redacted audit metadata across the SLB workflow and
parity command. The regression verifies approved metadata shapes for `report_template_created`,
`report_previewed`, `report_diagnostics_viewed`, `report_export_requested`,
`report_export_blocked`, `report_scheduled_dry_run_requested`, and
`report_parity_evidence_generated`, and verifies no layout snapshots, widget/page snapshots, raw
rows, delivery emails, tokens, or secret strings are stored in those audit rows. Focused
audit-redaction tests returned `2 passed`; the broader reporting slice and canonical backend gate
passed. Follow-up mutation audit coverage verifies `report_created` and `report_updated` store only
field names plus `redacted`, without report text, layout widget values, recipient emails, tokens, or
secrets; focused create/update plus workflow/parity audit tests returned `3 passed`, and the
broader reporting slice and canonical backend gate passed. BLK-008 remains open until fixed-target
runtime audit evidence and reviewer clearance are complete.

## G9 Aggregate-Output Redaction Evidence

Added and ran focused backend coverage for report preview, diagnostics, manual export metadata,
scheduled dry-run metadata, and parity evidence output. The regression injects sensitive-looking
values into report filters, delivery emails, and historical export metadata, then verifies the
report output surfaces do not echo token, secret, raw payload, delivery email, recipient, or
user-level identifier strings. Focused aggregate-output redaction coverage returned `1 passed`; the
broader reporting slice and canonical backend gate passed. BLK-008 remains open until fixed-target
runtime payload evidence, evidence-file hygiene, and reviewer clearance are complete.

## G9 No-Live-Provider Regression Evidence

Added and ran focused backend coverage proving report preview, manual export preflight, scheduled
dry-run metadata, and parity evidence generation do not open live network/provider calls. The
regression blocks socket connections, `urllib.request.urlopen`, `requests.sessions.Session.request`,
and `httpx` client requests after authentication, stubs async export dispatch, then executes the
SLB report preview, export, scheduled dry-run, and parity command paths. Focused no-live-provider
coverage returned `1 passed`; the broader reporting slice and canonical backend gate passed.
BLK-008 remains open until fixed-target runtime payload inspection and reviewer clearance are
complete.

## G2-G9 Evidence Bundle Command

Added `slb_report_evidence_bundle` as an aggregate-only fixed-target evidence collector. The command
emits one sanitized JSON bundle with report metadata, preview hash, coverage summary, diagnostics
for the same custom date range, rendering page/widget summary, export status/hash/artifact-size
summary, and parity rows. Focused tests verify redacted output, safe audit metadata, and that the
command runs under the same no-live-provider network-blocking regression. This reduces operator
error during G2-G9 collection, but BLK-005 through BLK-008 remain open until the command and
supporting screenshots/artifacts are run against the approved G1 runtime target and reviewed.
Preflight for this command was persisted under
`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-evidence-bundle-command/` and
still returns release `GATE_BLOCK` from architecture-level scope risk with a possible-contract-change
warning. BLK-001 is resolved by the validated G0 decision; later gates still need their own evidence.

## G9 Evidence-File Hygiene Evidence

Ran targeted scans across `docs/project/evidence/dashthis-replacement/` for high-signal credential
patterns and email addresses. Both returned no matches. A broader keyword scan found placeholders
such as `<operator-token>`, route examples, `.env.sample` references, and policy/checklist text, not
real credentials, private recipient emails, raw provider payloads, or unsafe artifact paths. BLK-008
remains open until fixed-target runtime payload evidence, future screenshot/export/snippet hygiene,
and reviewer clearance are complete.

## G10 Pre-Adversarial Implementation Review

Filled the G10 adversarial matrix with implementation-level results where local evidence exists and
explicit runtime-pending decisions where fixed SLB evidence is required. The pre-review records
implementation-pass evidence for tenant isolation, coverage blocking, disconnected-source labeling,
Instagram deferral, aggregate-output redaction, artifact safety, CSV formula safety, scheduled
dry-run sanitization, quota blocks, and audit redaction. BLK-009 remains open because the
adversarial review has not run against the fixed G1 report/date range and G0-G9 evidence chain.

## G11 Pre-Hardening Runbook

Expanded the hardening-window packet with a pre-window readiness checklist, checkpoint command
pack, redaction scan command, and checkpoint result template. This makes the 24-48 hour observation
window executable once G0-G10 pass. BLK-010 remains open because the hardening clock has not
started and must not start until G10 has no unresolved blocker or unaccepted high-risk issue.

## G12 Decision Packet

Expanded the final cancellation recommendation packet with a current no-go summary,
post-cancellation monitoring template, reversal triggers, and decision change log. BLK-011 remains
open because G0-G11 are incomplete and the recommendation remains `keep_dashthis_active`.

## Explicit Non-Blockers

These items should not be treated as reasons to expand the v1 proof unless a reviewer changes scope.

| Item                                             | Current handling                                                                                                                                        |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Instagram                                        | Deferred in v1. It becomes a blocker only if the cancellation claim says Instagram parity is included.                                                  |
| DashThis active subscription                     | Required during proof. It remains active until G12 recommends cancellation and the business owner accepts.                                              |
| Live provider calls at render/export time        | Not allowed. Missing live calls are not a blocker; using them would be a blocker.                                                                       |
| `adinsights-preflight` architecture `GATE_BLOCK` | Expected as cross-stream scope signal. BLK-001 is resolved for G0; future evidence gates still need reviewer-specific clearance and fixed-target proof. |

## Update Rules

When a blocker changes:

1. Update this register.
2. Update the relevant G0-G12 packet.
3. Update `2026-06-16-slb-cancellation-readiness-goals.md`.
4. Update `2026-06-16-slb-reporting-render-export-parity-evidence.md`.
5. Add a one-line entry to `docs/ops/agent-activity-log.md`.

Do not mark DashThis cancellation ready while any active blocker remains `open`,
`waiting_external`, or `evidence_needed` unless the correct reviewer explicitly records a waiver and
G12 accepts the risk.
