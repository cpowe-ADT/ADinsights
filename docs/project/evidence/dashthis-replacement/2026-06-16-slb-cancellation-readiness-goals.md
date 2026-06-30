# SLB Cancellation-Readiness Goal System

Date: 2026-06-16
Timezone: America/Jamaica
Status: active control system; DashThis cancellation remains no-go until evidence gates pass.

## North-Star Goal

Get ADinsights to SLB DashThis cancellation-review readiness without Instagram in v1, using stored
aggregate data only, with parity evidence, export snapshots, diagnostics, scheduled dry-run proof,
hardening evidence, and Raj/Mira review clearance.

This is the active engineering goal. It is deliberately narrower than "cancel DashThis" and broader
than "finish reporting implementation."

## Readiness Definitions

| State                         | Meaning                                                                                                                                      | Decision                                             |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| Implementation readiness      | The repo has the needed reporting features, APIs, UI paths, docs, and tests.                                                                 | Necessary but not enough to cancel DashThis.         |
| Cancellation-review readiness | A fixed SLB report/date range has evidence for rendering, parity, exports, snapshots, diagnostics, scheduled dry-run, safety, and hardening. | Ready for Raj/Mira and business cancellation review. |
| Actual DashThis cancellation  | Business owner accepts the evidence, unresolved blockers are absent, and a rollback/monitoring path exists.                                  | DashThis can be cancelled only after this decision.  |

Current decision: implementation readiness is partially achieved for the reporting ops slice, but
cancellation-review readiness is not achieved. Actual DashThis cancellation is no-go.
Canonical local backend/frontend gates have now passed for implementation readiness, but they do
not close any cancellation-readiness sub-goal without the fixed SLB runtime target, real stored-data
coverage, DashThis/source parity, reviewer clearance, adversarial review, and hardening evidence.
The `report.v1` export-readiness gate now blocks exports and scheduled dry-run rendering when
required stored coverage is `missing_history`, `not_previously_synced`, `permission_missing`, or
`unsupported_metric`; previews may still render available stored data with explicit notes.
Report diagnostics now include support-safe `source_health` so G8 evidence can cite Meta credential
status, Page connection state, Airbyte status categories, stored row counts, and recommended next
actions without logs, secrets, raw provider payloads, or user-level metrics.
The machine-readable status manifest for future sessions is:

`docs/project/evidence/dashthis-replacement/2026-06-16-slb-cancellation-readiness-status.json`

Validate it before using it for a readiness handoff:

```bash
python3 scripts/validate_slb_cancellation_readiness_status.py
```

Print the next actionable blocker and commands:

```bash
python3 scripts/slb_cancellation_readiness_doctor.py
```

The doctor also prints a fixed-target prerequisite row and an objective map for the active
SLB/RPT/META/UX/OPS IDs. The map is intentionally conservative: it only ties each user-facing
objective to its governing G0-G12 goals and active blockers. It does not mark an objective complete
from local implementation work while G1, parity, fixed-range evidence, hardening, or G12 remain
unproven.
The doctor also emits a separate `product_capability_assessment` lane so implementation confidence
is not confused with human/source inputs. Missing target intake, runtime release configuration, real
DashThis/source values, and final business sign-off are tracked as comparison/release/decision
inputs, not product-capability defects. They still block parity or cancellation claims when required,
and missing source values must remain missing rather than invented. Internal product confidence is
blocked only by product evidence still under our control: fixed-range preview/history diagnostics,
CSV/PDF/PNG export proof, scheduled dry-run/support diagnostics, tenant-safety proof, adversarial
review, and hardening.
Each objective row also carries a fixed-target prerequisite gate. Until G1 is passed, the doctor
sets `can_start_fixed_target_evidence=false` and repeats the G1 status on every SLB/RPT/META/UX/OPS
row so `evidence_pending` cannot be mistaken for permission to start cancellation-grade proof.
The status validator runs the doctor against the same manifest and fails if this objective map is
missing, malformed, or no longer lists the active SLB/RPT/META/UX/OPS IDs in order.
It also fails if any objective row drops or misstates the fixed-target prerequisite gate.
The doctor also reads the linked G1 intake template and lists the remaining placeholder fields plus
false confirmations such as `comparison.tolerances_confirmed`; the status validator fails if that
G1 intake summary disappears or no longer points at the active template.
The status validator also runs `slb_g1_intake_draft.py` against the checked-in redacted target
example using the checked-in G1 valid-example values. It fails if the helper disappears, stops
writing the draft, leaves example fields pending, marks a draft candidate-ready, or produces a
draft that fails the final G1 validator for any reason beyond the required operator status
promotion.

The validator checks JSON schema, G0-G12 ordering/statuses, BLK-001 through BLK-011
ordering/statuses, evidence paths, no-go/pass invariants, and drift between this goal table and the
machine-readable manifest. It also fails if a sub-goal is marked `passed` while its linked blocker
is still open/waiting/evidence-needed, or if cancellation-review readiness moves beyond `no_go`
while any G0-G11 blocker remains unresolved. It now also verifies that the next execution handoff is
linked to the machine-readable G0 Raj/Mira review template, G1 intake template, G2-G9 fixed-range
evidence run template, G10 adversarial review template, G11 hardening-window template, G12
final-recommendation template, `validate_slb_g0_raj_mira_review.py`,
`validate_slb_g1_runtime_target_intake.py`, `validate_slb_g0_g1_handoff.py`,
`validate_slb_g2_g9_evidence_run.py`, `validate_slb_g10_adversarial_review.py`,
`validate_slb_g11_hardening_window.py`, and `validate_slb_g12_final_recommendation.py`. It also
checks the active G0/G1 external handoff packet is present, and validates the non-evidence G0/G1
example artifacts with the current G0, G1, and combined handoff validators so examples cannot drift
after schema hardening. It also requires the G12 approval/signoff preflight packet to stay linked
from `next_execution`, so the final recommendation handoff cannot drop the explicit reviewer
approval-value gate.
It also inspects the G11 and G12 JSON templates directly to make sure their `references` blocks keep
the upstream G1 intake, G2-G9 evidence-run, G10 review, and G11 window handoff fields with pending
boolean defaults, so template drift cannot silently detach downstream evidence from the fixed-target
chain.
The advertised G11/G12 validator commands must also keep their upstream artifact arguments:
`--g10-review-file` for G11, and `--status-manifest-file` plus `--g11-window-file` for G12.
The full evidence-chain command must keep the complete handoff argument set:
`--status-manifest-file`, `--g1-intake-file`, `--g2-g9-run-file`, `--g10-review-file`,
`--g11-window-file`, and `--g12-recommendation-file`.
Finally, the status validator scans the machine-readable manifest, this goal controller, and the
blocker register for secret, raw-payload, email, and user-level identifier patterns. This keeps the
cancellation-readiness control plane itself safe before later G8/G9 evidence is collected.

Focused regression coverage:

```bash
cd backend
PYTHONPATH=.. ./.venv/bin/pytest -q ../scripts/tests/test_validate_slb_cancellation_readiness_status.py
```

Current focused coverage verifies valid current state, goal-table drift, blocker-register drift, G0
review handoff links, the G0/G1 external handoff packet link, G0/G1 valid-example links and
validity, G1 intake handoff links, G2-G9 run handoff links, combined G0/G1 handoff validator links,
G10 adversarial handoff links, premature DashThis cancellation claims, G11 hardening handoff links,
G12 final-recommendation handoff links, passed-goal/unresolved-blocker conflicts, and
cancellation-review-readiness claims with unresolved G0-G11 blockers. It also covers sensitive
value rejection in the status manifest, goal doc, and blocker register, plus status-level drift in
the G1 draft helper's checked-in example output.

G0 Raj/Mira review validator:

```bash
python3 scripts/validate_slb_g0_raj_mira_review.py \
  --review-file <filled-g0-raj-mira-review-decision.json>
```

Template:

`docs/project/evidence/dashthis-replacement/2026-06-16-g0-raj-mira-review-decision.template.json`

The G0 validator also enforces consistency between overall status, Raj/Mira reviewer decisions,
scope classification, architecture classification, G1-G11 evidence-capture mode, and required
follow-up rows. This prevents a review from accidentally marking G0 approved while leaving
follow-up or blocked-state semantics ambiguous. It also requires a stable `slb-g0-*` decision ID,
timezone-aware decision timestamp, ordered decision log timestamps, non-placeholder follow-up owner
routes, and explicit before-G1 follow-up rows when Raj/Mira block fixed-target evidence capture.
The validator also opens the referenced regular and checked preflight packet directories and
requires their `scope-packet.json`, `contract-packet.json`, and `release-packet.json` statuses to
match the filled `preflight_interpretation` fields.

G0/G1 external handoff packet:

`docs/project/evidence/dashthis-replacement/2026-06-16-g0-g1-external-handoff.md`

G0/G1 valid examples:

`docs/project/evidence/dashthis-replacement/examples/README.md`

G0/G1 combined handoff validator:

```bash
python3 scripts/validate_slb_g0_g1_handoff.py \
  --g0-review-file <filled-g0-raj-mira-review-decision.json> \
  --g1-intake-file <filled-g1-runtime-target-intake.json>
```

The combined handoff validator verifies G1 preserves the filled G0 reviewer decisions, keeps
conditional/follow-up approvals conditional, rejects reversed or malformed fixed date ranges, and
requires the target-intake output evidence before G2-G11 fixed-target evidence starts.

G2-G9 fixed-range evidence run validator:

```bash
python3 scripts/validate_slb_g2_g9_evidence_run.py \
  --run-file <filled-g2-g9-evidence-run.json> \
  --intake-file <filled-g1-runtime-target-intake.json>
```

The G2-G9 validator requires each active dataset coverage row to use valid ordered covered dates.
Fresh, stale, and source-disconnected-with-history rows must span the fixed target date range.
Stale, partial, source-disconnected, and source-disconnected-with-history rows must include an
explicit reviewer note before G10 can start.
It now requires `--intake-file` and refuses to pass unless the referenced G1 runtime target intake
is `candidate_ready_for_review`, has confirmed tolerances, preserves dry-run delivery and active
DashThis status, and keeps Instagram deferred with stored-aggregate/no-live-render guardrails.
It also requires filled `evidence_files` entries to point at existing, non-empty repo-relative
artifacts under `docs/project/evidence/dashthis-replacement/`; text artifacts are parsed or scanned
for invalid JSON, secrets, emails, raw provider payloads, and user-level identifiers.

Template:

`docs/project/evidence/dashthis-replacement/2026-06-16-g2-g9-fixed-range-evidence-run.template.json`

G10 adversarial review validator:

```bash
python3 scripts/validate_slb_g10_adversarial_review.py \
  --review-file <filled-g10-adversarial-review.json> \
  --g2-g9-run-file <filled-g2-g9-evidence-run.json> \
  --intake-file <filled-g1-runtime-target-intake.json>
```

The validator requires both upstream artifacts: the same candidate-ready G1 runtime target intake
used by G2-G9, and the validated G2-G9 evidence run. Do not start G10 from a standalone adversarial
checklist or a G2-G9 packet that has not been bound back to the approved G1 target.

Accepted or waived adversarial risks must include structured approval metadata: risk owner,
accepted-by route including Raj and Mira, expiry/review date, and rationale. These rows remain
warnings for G12 even when valid.
Each adversarial row must also link to an existing, non-empty evidence artifact under
`docs/project/evidence/dashthis-replacement/`; JSON artifacts must parse and text artifacts are
scanned for secrets, emails, raw provider payloads, and user-level identifiers.

Template:

`docs/project/evidence/dashthis-replacement/2026-06-16-g10-adversarial-review.template.json`

G11 hardening-window validator:

```bash
python3 scripts/validate_slb_g11_hardening_window.py \
  --window-file <filled-g11-hardening-window.json> \
  --g10-review-file <filled-g10-adversarial-review.json>
```

The G11 validator requires ISO-8601 window and checkpoint timestamps, verifies the elapsed window
actually spans the declared 24-48 hour length, and rejects out-of-order checkpoint timestamps before
G12 can be written.
It also requires the supplied G10 review to carry the same validated G1 runtime intake and G2-G9
evidence-run references as the G11 window, plus filled checkpoint, final evidence-validation,
redaction-scan, and export-snapshot artifact paths under
`docs/project/evidence/dashthis-replacement/`; JSON artifacts must parse and text artifacts are
scanned for secrets, emails, raw provider payloads, and user-level identifiers.

Template:

`docs/project/evidence/dashthis-replacement/2026-06-16-g11-hardening-window.template.json`

G12 final recommendation validator:

```bash
python3 scripts/validate_slb_g12_final_recommendation.py \
  --recommendation-file <filled-g12-final-recommendation.json> \
  --status-manifest-file docs/project/evidence/dashthis-replacement/2026-06-16-slb-cancellation-readiness-status.json \
  --g11-window-file <filled-g11-hardening-window.json>
```

The G12 validator requires the supplied G11 window to carry the same validated G1 runtime intake,
G2-G9 evidence-run, and G10 review references as the final recommendation packet, so the final
decision cannot be detached from the fixed-target evidence chain.

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

The chain validator runs the stage validators in order and fails when downstream evidence is
provided without the required upstream artifact. It passes the same G1 runtime target intake into
both G2-G9 and G10 validation, so the adversarial review cannot detach from the approved fixed
target. It is the final local consistency command before a future session can claim the filled
G0-G12 packet is ready for cancellation review.

If G12 recommends cancellation, the validator requires a concrete DashThis cancellation date on or
after the decision effective date. If G12 recommends keeping DashThis active, the cancellation date
must remain empty.
The G12 validator also treats reviewer approvals as enumerated controls, not free-text notes:
G0-G11 rollup approvals and reviewer sign-offs must use approved, accepted, passed, waived, or
not-required style values. Denied, pending, or review-pending values fail validation. The business
owner must explicitly approve or accept the final keep/cancel recommendation, and must approve
cancellation when cancellation is recommended.

Template:

`docs/project/evidence/dashthis-replacement/2026-06-16-g12-final-recommendation.template.json`

Validator test preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-status-validator-tests/`

Latest G0 Raj/Mira review validator preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g0-raj-mira-review-validator/`

Latest G0 validator consistency preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g0-validator-consistency/`

Latest G0 decision-metadata validation preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g0-decision-metadata/`

Latest G0 preflight-packet status validation preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g0-preflight-status/`

Latest G0/G1 external handoff preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g0-g1-external-handoff/`

Latest G0/G1 handoff validator preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g0-g1-handoff-validator/`

Latest G0/G1 handoff bridge preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g0-g1-handoff-bridge/`

Latest G0/G1 valid examples preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g0-g1-valid-examples/`

Latest status valid-example drift preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-status-example-drift/`

Latest readiness doctor preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-readiness-doctor/`

Latest unresolved-blocker invariant preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-status-validator-unresolved-blockers/`

Latest G1 intake linkage preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-status-validator-g1-links/`

Latest G2-G9 run validator preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g2-g9-run-validator/`

Latest G2-G9 coverage proof validator preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g2-g9-coverage-proof/`

Latest G2-G9 evidence artifact validator preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g2-g9-evidence-artifacts/`

Latest G10 adversarial review validator preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g10-adversarial-validator/`

Latest G10 accepted-risk approval preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g10-risk-approval/`

Latest G10 evidence artifact validator preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g10-evidence-artifacts/`

Latest G11 hardening-window validator preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g11-hardening-validator/`

Latest G11 hardening-window timestamp preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g11-window-timestamps/`

Latest G11 evidence artifact validator preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g11-evidence-artifacts/`

Latest G12 final-recommendation validator preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g12-final-recommendation-validator/`

Latest G12 cancellation-date validation preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g12-cancellation-date/`

Latest G12 evidence rollup link validator preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g12-evidence-rollup-links/`

Latest G12 approval/signoff validation preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g12-approval-signoffs/`

Latest status-manifest G12 approval-link preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-status-g12-approval-link/`

Latest status-manifest hygiene-scan preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-status-hygiene-scan/`

Latest evidence chain validator preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-evidence-chain-validator/`

Latest validator preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-status-validator-drift-checks/`

## Operating Rules

- Keep Instagram deferred unless source rows, scopes, metric catalog entries, and reviewer approval
  are proven.
- Use only stored aggregate ADinsights data for report preview/export. No live provider calls at
  render/export time.
- Keep DashThis active until parity, export, delivery, diagnostics, safety, and hardening evidence
  are complete.
- Treat `adinsights-preflight` `GATE_BLOCK` as expected until Raj/Mira clear the cross-stream
  architecture scope.
- Every sub-goal must end in evidence. Implemented code without evidence does not close a sub-goal.
- If a sub-goal requires backend/frontend/dbt/infrastructure changes, route through Raj first and
  Mira when architecture or schema-versioning semantics are affected.

## Status Key

- `not_started` - no meaningful evidence has been collected.
- `implemented_path` - repo support exists, but fixed-range SLB evidence is not complete.
- `evidence_pending` - the next work is evidence capture, comparison, or review.
- `blocked_external` - needs operator, source, staging, DashThis, or reviewer access.
- `review_pending` - evidence exists and needs named reviewer clearance.
- `passed` - evidence and reviewer route are complete.
- `failed_or_blocked` - evidence disproves readiness or exposes a blocker.

## Sub-Goals

| ID  | Sub-goal                                              | Status             | Evidence needed                                                                                                                                                                                                                                                                 | Reviewer route                                                     | Update when complete                                                     |
| --- | ----------------------------------------------------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------ |
| G0  | Raj/Mira architecture and scope review                | `passed`           | `2026-06-17-g0-raj-mira-agent-review-decision.json`; validated conditional approval that preflight block is architecture scope, not test failure                                                                                                                                | Raj, Mira                                                          | Goal doc, evidence packet, activity log                                  |
| G1  | Fixed SLB proof target and date range                 | `blocked_external` | Tenant/client, SLB report ID, template key, reporting date range in America/Jamaica, recipient assumptions, Instagram defer note                                                                                                                                                | Raj, Hannah                                                        | Evidence packet parity section                                           |
| G2  | Stored data coverage proof                            | `evidence_pending` | Coverage summary for `paid_meta_ads`, `organic_facebook_page`, and `content_ops`; source labels; row counts; freshness states; no user-level metrics                                                                                                                            | Andre, Sofia, Omar                                                 | Evidence packet coverage section                                         |
| G3  | 90-day/monthly retained-history proof                 | `evidence_pending` | Separate monthly and 90-day retained-history classification per active dataset: fresh, stale, partial, source_disconnected, missing_history, or not_previously_synced                                                                                                           | Priya/Martin if dbt or retention gap appears; Andre/Omar otherwise | Evidence packet and retention/handoff note                               |
| G4  | Report rendering proof                                | `evidence_pending` | Saved `dashboard.v1` and SLB `report.v1` page render proof, including cover, executive summary, paid, organic Page/top posts, Content Ops, recommendations, appendix/data notes                                                                                                 | Lina, Joel                                                         | Evidence packet with screenshots or verified UI paths                    |
| G5  | CSV/PDF/PNG export reproducibility proof              | `evidence_pending` | Export job IDs for CSV/PDF/PNG; non-empty artifact checks; `report_snapshot`; snapshot hash; generated timestamp; coverage summary; download proof                                                                                                                              | Sofia, Omar, Nina if artifact sensitivity appears                  | Evidence packet export section                                           |
| G6  | Parity worksheet against DashThis/source values       | `evidence_pending` | ADinsights values from `slb_report_parity_evidence`; DashThis/source values; absolute deltas; percentage deltas; accepted tolerance; pass/fail; explanation                                                                                                                     | Andre, Raj, business owner                                         | Evidence packet parity worksheet                                         |
| G7  | Scheduled delivery dry-run proof                      | `evidence_pending` | Dry-run export job ID; `delivery_status.mode == "dry_run"`; blocked coverage behavior; sanitized failures; proof no client email was sent                                                                                                                                       | Omar, Hannah, Carlos/Mei if runtime delivery path changes          | Evidence packet delivery section                                         |
| G8  | Diagnostics/support proof                             | `evidence_pending` | Diagnostics payload showing dataset status, retained range, row count, source label, export history, blocking reasons, recommended next action, and no secrets/user-level data                                                                                                  | Omar, Hannah, Sofia                                                | Evidence packet diagnostics section; support/runbook if behavior changes |
| G9  | Permissions, tenant isolation, audit, and quota proof | `evidence_pending` | Viewer/editor/admin action behavior; cross-tenant rejection; audit events; quota behavior; aggregate-only verification                                                                                                                                                          | Sofia, Nina, Raj if cross-stream                                   | Evidence packet safety section                                           |
| G10 | Adversarial review                                    | `not_started`      | Review against wrong date range/timezone, wrong tenant/client/account/page, stale shown as fresh, partial export without warning, missing history, unsupported Instagram assumptions, empty artifacts, delivery failure, cross-tenant leak, quota bypass, missing rollback path | Raj, Mira, Omar, Hannah, Nina as needed                            | Evidence packet adversarial checklist                                    |
| G11 | 24-48 hour hardening window                           | `not_started`      | Timestamped observation window with sync/freshness/export/dry-run checks, failures, mitigations, unresolved blockers, and rollback path                                                                                                                                         | Raj, Mira, Omar                                                    | Evidence packet hardening section                                        |
| G12 | Final cancellation recommendation                     | `not_started`      | Completed G0-G11 evidence; explicit keep/cancel DashThis recommendation; known gaps; rollback/monitoring plan                                                                                                                                                                   | Raj, Mira, business owner                                          | Evidence packet current decision                                         |

## Recommended Execution Order

1. **G1** - Lock the exact SLB report, tenant/client, and fixed date range.
   G0 is conditionally approved for evidence capture.
2. **G2 + G3** - Prove stored coverage and retained history before trusting parity numbers.
3. **G6** - Generate and fill the parity worksheet while the date range is fixed.
4. **G4 + G5** - Capture render/export reproducibility proof for the same report/date range.
5. **G7 + G8** - Capture scheduled dry-run and support diagnostics proof.
6. **G9** - Verify permissions, tenant isolation, audit events, quotas, and aggregate-only behavior.
7. **G10** - Run adversarial cancellation review and convert every issue into a fix, evidence note,
   or explicit blocker.
8. **G11** - Record the 24-48 hour hardening window.
9. **G12** - Make the cancellation recommendation.

## Current External Action Queue

The next meaningful progress is external. The consolidated intake lives in
`2026-06-16-g0-g1-review-target-intake.md` and `external-prerequisites-checklist.md`.

| Priority | Owner                                    | Required answer                                                                                                                             |
| -------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| 1        | Operator + Hannah                        | Fill environment, URLs, safe tenant/client, runtime report ID, date range, source scopes, delivery assumptions, and DashThis active status. |
| 2        | DashThis/source comparison owner + Andre | Provide redacted fixed-range comparison values and tolerances for required non-Instagram metrics.                                           |
| 3        | Runtime owner + Raj/Mira                 | Resolve the non-secret Airbyte Meta metrics template connection prerequisite or approve an alternate bootstrap path.                        |

After G1 is filled, use `2026-06-16-g2-g9-evidence-execution-checklist.md` as the single-run
evidence controller. It now includes a run sheet, recommended output filenames, and a completion
matrix that must be filled before G10 can start. It also starts with the aggregate-only
`slb_report_evidence_bundle` command so preview, diagnostics, rendering summary, export metadata
summary, and parity rows can be captured for the same fixed SLB report/date range before the
operator collects screenshots, downloads, DashThis/source values, and reviewer approvals.
The machine-readable G2-G9 run template and validator should be filled after those artifacts are
collected; G10 should not start while that validator fails.

## Exact Repo Location

This goal system lives at:

`docs/project/evidence/dashthis-replacement/2026-06-16-slb-cancellation-readiness-goals.md`

Reason: it is not a product architecture contract or runtime spec. It is the control plane for the
SLB DashThis cancellation evidence packet, so it belongs beside the evidence artifacts it governs.

## Docs To Update As Sub-Goals Close

Always update:

- `docs/project/evidence/dashthis-replacement/2026-06-16-slb-cancellation-readiness-goals.md`
- `docs/project/evidence/dashthis-replacement/2026-06-16-slb-reporting-render-export-parity-evidence.md`
- `docs/ops/agent-activity-log.md`

Update conditionally:

- `docs/project/api-contract-changelog.md` when endpoints, payloads, metadata, validation, or commands change.
- `docs/project/reporting-builder-catalog-contract.md` when datasets, metrics, dimensions, widget rules, coverage statuses, or invalid combinations change.
- `docs/project/reporting-builder-architecture-plan.md` when architecture, schema-versioning, or long-term builder strategy changes.
- `docs/project/dashthis-replacement-reporting-plan.md` when the business gate, phase order, or cancellation criteria change.
- `docs/ops/exports.md` when export/snapshot/artifact behavior changes.
- Relevant runbooks when operational behavior, diagnostics, delivery, alerting, or support actions change.
- `docs/ops/doc-index.md` only when a new document is added, moved, or materially reclassified.

## Evidence Packet Sections To Maintain

| Evidence area                | Primary doc section                            |
| ---------------------------- | ---------------------------------------------- |
| G0 review control            | Current Reporting Ops Review Packet            |
| G1 proof target              | Evidence To Attach Before Cancellation Review  |
| G2/G3 coverage and retention | Snapshot And Diagnostics Evidence              |
| G4 rendering                 | Required SLB Sections                          |
| G5 exports                   | Snapshot And Diagnostics Evidence              |
| G6 parity                    | Parity Worksheet                               |
| G7 delivery                  | Scheduled Delivery Dry-Run Evidence            |
| G8 diagnostics               | Snapshot And Diagnostics Evidence              |
| G9 permissions/safety        | Adversarial Review Checklist plus gate results |
| G10 adversarial review       | Adversarial Review Checklist                   |
| G11 hardening                | Evidence To Attach Before Cancellation Review  |
| G12 decision                 | Current Decision                               |

## Active Blocker Register

Current no-go blockers are tracked in:

`docs/project/evidence/dashthis-replacement/2026-06-16-slb-cancellation-readiness-blocker-register.md`

Machine-readable status is tracked in:

`docs/project/evidence/dashthis-replacement/2026-06-16-slb-cancellation-readiness-status.json`

Validate status consistency with:

```bash
python3 scripts/validate_slb_cancellation_readiness_status.py
```

This catches status drift between the machine-readable manifest, this goal document, and the active
blocker register, and it catches missing or miswired G1 intake handoff links before a future session
starts fixed-target evidence capture. It also catches missing or miswired G2-G9 run handoff links
before a future session claims evidence is ready for G10, and missing or miswired G10 links before a
future session claims evidence is ready for G11 hardening.

Validator preflight is persisted at:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-status-validator-drift-checks/`

Use that register to distinguish external/reviewer/runtime blockers from ordinary evidence capture.
DashThis cancellation cannot move to review-ready while any active blocker remains open,
waiting-external, or evidence-needed without the correct reviewer waiver and G12 acceptance.

## Current G0 Evidence

G0 review packet:

`docs/project/evidence/dashthis-replacement/2026-06-16-g0-raj-mira-review-packet.md`

G0/G1 review and fixed-target intake handoff:

`docs/project/evidence/dashthis-replacement/2026-06-16-g0-g1-review-target-intake.md`

External G0/G1 handoff:

`docs/project/evidence/dashthis-replacement/2026-06-16-g0-g1-external-handoff.md`

Current G0 status is `passed` for conditional evidence capture. The validated decision lives at:

`docs/project/evidence/dashthis-replacement/2026-06-17-g0-raj-mira-agent-review-decision.json`

Raj and Mira both approved with followups: G1-G11 fixed-target evidence capture may proceed, but
DashThis cancellation remains `no_go`. The latest refreshed preflight for the G0/G1 handoff still
returns `GATE_BLOCK` because scope control is architecture-level review, not a runtime test failure.
The stable packet set is stored at
`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake/`.
A checked packet set is also stored at
`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake-with-checks/`;
it records passing data-contract and observability prerequisite checks, plus a production-readiness
failure for missing `AIRBYTE_TEMPLATE_META_METRICS_CONNECTION_ID`.
That blocker is now tracked in
`docs/project/evidence/dashthis-replacement/external-prerequisites-checklist.md` and must be
resolved or explicitly waived before G11/G12 can claim release or cancellation readiness.
After local backend/frontend gates passed, the preflight was rerun and persisted at
`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-after-local-backend-frontend-gates/`.
The result remains release `GATE_BLOCK`: router action `resolve`, scope `ESCALATE_ARCH_RISK`,
contract `WARN_POSSIBLE_CONTRACT_CHANGE`, and security/PII warning. This reinforces that the
remaining G0 blocker is reviewer/architecture classification, not the local backend/frontend gate
result.
After adding the evidence bundle command, preflight was rerun and persisted at
`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-evidence-bundle-command/`.
The result remains release `GATE_BLOCK`: router action `clarify`, scope `ESCALATE_ARCH_RISK`,
contract `WARN_POSSIBLE_CONTRACT_CHANGE`, and security/PII warning. This reinforces that the
evidence-bundle command is contract/scope-sensitive and requires Raj/Mira classification before any
release or cancellation-readiness claim.
After adding the parity comparison command, preflight was rerun and persisted at
`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-parity-compare-command/`.
The result remains release `GATE_BLOCK`: router action `clarify`, scope `ESCALATE_ARCH_RISK`,
contract `WARN_POSSIBLE_CONTRACT_CHANGE`, and security/PII warning. This reinforces that the
comparator is part of the contract/scope-sensitive evidence chain and requires Raj/Mira
classification before any release or cancellation-readiness claim.
After adding the evidence validation command, preflight was rerun and persisted at
`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-evidence-validate-command/`.
The result remains release `GATE_BLOCK`: router action `clarify`, scope `ESCALATE_ARCH_RISK`,
contract `WARN_POSSIBLE_CONTRACT_CHANGE`, and security/PII warning. This reinforces that the
validator is part of the contract/scope-sensitive evidence chain and requires Raj/Mira
classification before any release or cancellation-readiness claim.
Additional local gates now show `backend_release_preflight`, the Airbyte data-contract validation,
and the observability prerequisite validation passing. Production readiness still fails on missing
`AIRBYTE_TEMPLATE_META_METRICS_CONNECTION_ID`, so release/cancellation readiness remains blocked
unless that external prerequisite is resolved or explicitly waived by the correct reviewers.

## Current G1 Evidence

G1 proof-target packet:

`docs/project/evidence/dashthis-replacement/2026-06-16-g1-fixed-slb-proof-target.md`

G1 runtime target intake checklist:

`docs/project/evidence/dashthis-replacement/2026-06-16-g1-runtime-target-intake-checklist.md`

G1 machine-readable intake template:

`docs/project/evidence/dashthis-replacement/2026-06-16-g1-runtime-target-intake.template.json`

G1 intake validator:

```bash
python3 scripts/validate_slb_g1_runtime_target_intake.py \
  --intake-file <filled-g1-runtime-target-intake.json>
```

G1 intake draft helper:

```bash
python3 scripts/slb_g1_intake_draft.py \
  --target-intake-output <redacted-slb-target-intake-output.json> \
  --output <draft-g1-runtime-target-intake.json>
```

The G1 validator rejects blocked reviewer decisions, missing conditional approval notes, and G1
intakes that collapse Raj/Mira conditional approval or followups into a clean proceed state.
It also loads `evidence.slb_report_target_intake_output` and verifies the referenced
`slb_target_intake.v1` JSON agrees with the filled report ID, primary date range, SLB template,
`report.v1` schema, required active datasets, required report pages, source-scope presence, and
Instagram/stored-aggregate/no-sensitive-pattern guardrails.

G1 intake validator preflight:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g1-runtime-intake-validator/`

Latest G1 clearance consistency preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g1-clearance-consistency/`

Latest G1 target-intake output validation preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-17-slb-g1-target-output/`

Local runtime-state audit:

`docs/project/evidence/dashthis-replacement/2026-06-16-local-runtime-state-audit.md`

Local SLB smoke validation:

`docs/project/evidence/dashthis-replacement/2026-06-16-local-slb-smoke-validation.md`

Local browser render/export proof:

`docs/project/evidence/dashthis-replacement/2026-06-17-local-browser-render-export-proof.md`

Local demo to fixed-target bridge:

`docs/project/evidence/dashthis-replacement/2026-06-17-local-demo-to-fixed-target-bridge.md`

Local visual render proof:

`docs/project/evidence/dashthis-replacement/2026-06-17-local-visual-render-proof.md`

G0/G1 review and fixed-target intake handoff:

`docs/project/evidence/dashthis-replacement/2026-06-16-g0-g1-review-target-intake.md`

Current G1 status is `blocked_external`. The packet recommends SLB May 2026 as the default proof
target because Gmail evidence includes a complete May 2026 SLB monthly report and a March-April
baseline report. G1 is not passed until the operator/runtime context records the target environment,
safe tenant/client identifier, real `ReportDefinition.id`, confirmed `template_key`, account/Page
scope, recipient assumptions, DashThis/source comparison owner, and explicit Instagram deferral.
The intake handoff is the canonical place to collect those runtime values before G2-G11 evidence.
The runtime checklist is the operator-facing fill-in artifact for those values and the minimum
validation steps before G2-G11 can produce cancellation-review evidence. A read-only local audit
confirmed the current SQLite database has no SLB `report.v1` candidate, no export jobs, no
`dashboard.v1` dashboards, missing Content Ops tables, and only stale/demo/fake/warehouse snapshots;
therefore local runtime state cannot close G1 or start cancellation-grade G2/G3 proof. The audit
also confirms Content Ops migrations are present but unapplied locally, and the SLB template creation
path exists for local-only smoke validation.
A subsequent local smoke run applied local Content Ops migrations, created a local-only SLB
`report.v1` target, successfully ran `slb_report_parity_evidence`, built preview/diagnostics/export
metadata, and completed local CSV export. After installing local Playwright Chromium, PDF/PNG export
and scheduled dry-run artifact rendering also completed locally. This does not close G1-G12 because
it is not an approved runtime target and has zero/empty values with no DashThis comparison.
A later local browser/API proof confirmed the local report detail route rendered eight ordered
`report.v1` pages, surfaced paid `source_disconnected` coverage plus organic/content
`missing_history` diagnostics, and downloaded non-empty CSV, PDF, and PNG artifacts. This is useful
implementation proof only; it does not close G1-G12 because the report remains local-only, visually
rough, unreviewed by Raj/Mira, and lacks fixed-target DashThis/source parity.
The local demo to fixed-target bridge records how to convert this working local report path into a
real G1/G2-G11 evidence chain: fill G0, select the approved runtime target, generate target intake,
validate G0/G1 agreement, and then regenerate all evidence from the approved target rather than
reusing local-demo artifacts.
A local Playwright visual proof now captures desktop and mobile screenshots after the report
readability pass. It confirms the local report route is visually renderable and non-fresh coverage
states are visible, but it remains local-only and does not close G4/G5 without an approved G1
target.
Canonical local implementation gates now include passing `make backend-lint`, `make backend-test`,
`make frontend-guardrails`, `make frontend-lint`, `make frontend-test`, and `make frontend-build`.
These reduce implementation uncertainty only; they do not replace fixed-target evidence.
The deterministic backend release preflight, data-contract gate, and observability prerequisite
gate have also passed locally. The Airbyte production-readiness check still fails on the missing
template Meta metrics connection ID, so G11/G12 cannot claim release/cancellation readiness.
The new `slb_report_target_intake` command can summarize a candidate report for G1 with redacted
schema/template/date-range/dataset/page/scope-presence guardrails and explicit Instagram deferral.
Focused regression coverage verifies valid SLB candidates and invalid Instagram-including targets.
This improves the G1 intake mechanism but does not close G1 because environment, safe tenant/client,
source scope, recipient assumptions, DashThis status, and Raj/Mira clearance remain external.
The `validate_slb_g1_runtime_target_intake.py` validator now covers the operator-owned G1 fields
that are not available from the report object itself. It rejects pending placeholders, missing G0
clearance, non-dry-run delivery, inactive DashThis, Instagram included in v1,
live-provider/render-export violations, missing comparison ownership, mismatched target-intake
output, and sensitive values.
The `slb_g1_intake_draft.py` helper can now prefill a draft G1 intake from a redacted
`slb_target_intake.v1` output plus safe CLI-supplied environment/scope notes. It remains a
read-only drafting aid and intentionally emits `status=pending_operator_input`, so it cannot close
G1 or start G2-G11 evidence without operator review, G0 clearance, confirmed tolerances, and a
passing `validate_slb_g1_runtime_target_intake.py` run. Its `--output` result packet lists remaining
pending fields, false confirmations, and next required review actions for the operator handoff.
The status validator now exercises this helper against the checked-in redacted example and verifies
that the helper-generated draft is still blocked only by operator status promotion.
After adding the target intake command, preflight was rerun and persisted at
`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-target-intake-command/`.
The result remains release `GATE_BLOCK`: router action `clarify`, scope `ESCALATE_ARCH_RISK`,
contract `WARN_POSSIBLE_CONTRACT_CHANGE`, and security/PII warning. This reinforces that G1 target
intake remains part of the contract/scope-sensitive evidence chain and still requires Raj/Mira
classification before any release or cancellation-readiness claim.
After adding the retained-history probe command, preflight was rerun and persisted at
`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-history-probe-command/`.
The result remains release `GATE_BLOCK`: router action `clarify`, scope `ESCALATE_ARCH_RISK`,
contract `WARN_POSSIBLE_CONTRACT_CHANGE`, and security/PII warning. This reinforces that G2/G3
history evidence collection is contract/scope-sensitive and still requires Raj/Mira classification
before any release or cancellation-readiness claim.

## Current G2/G3 Evidence

G2-G9 fixed-range execution checklist:

`docs/project/evidence/dashthis-replacement/2026-06-16-g2-g9-evidence-execution-checklist.md`

Stored coverage and retained-history packet:

`docs/project/evidence/dashthis-replacement/2026-06-16-g2-g3-coverage-retained-history-proof.md`

Current G2 and G3 statuses are `evidence_pending`. The packet defines the exact preview,
diagnostics, and parity-command fields to capture for `paid_meta_ads`, `organic_facebook_page`, and
`content_ops`, plus separate monthly and 90-day retained-history tables. It does not pass G2/G3
because fixed-runtime proof still depends on the G1 target environment, report ID, tenant/client,
date range, account/Page scope, and Instagram deferral. The G2-G9 checklist is the post-G1 ordered
execution path for collecting the fixed-range proof without mixing report IDs, scopes, or date
ranges.
Local backend regression coverage now verifies that manually authored `report_section` widgets do
not inflate dataset-level coverage summaries or diagnostics retained ranges, and that zero-row
datasets do not report covered start/end dates. This strengthens G2/G3 implementation evidence but
does not close fixed monthly or 90-day retained-history proof.
Local backend regression coverage now also verifies `slb_report_history_probe`, which builds a
primary-month and retained-90-day matrix for `paid_meta_ads`, `organic_facebook_page`, and
`content_ops` without raw rows or live provider calls. This improves G2/G3 evidence collection
quality but does not close fixed monthly or 90-day retained-history proof until run against the
approved G1 report/date ranges.

## Current G4/G5 Evidence

Render and export reproducibility packet:

`docs/project/evidence/dashthis-replacement/2026-06-16-g4-g5-render-export-reproducibility-proof.md`

Current G4 and G5 statuses are `evidence_pending`. The implementation path exists, but cancellation
proof still needs fixed-range saved `dashboard.v1` screenshots or browser evidence, SLB `report.v1`
page-render evidence, CSV/PDF/PNG export job IDs, non-empty download checks, and matching
`report_snapshot.preview_hash` versus the visible report preview hash for the G1 report/date range.
Local backend regression coverage now verifies completed `report.v1` CSV, PDF, and PNG exports preserve
`metadata.report_preview.preview_hash`, `metadata.report_preview.report_snapshot.preview_hash`, and
ordered SLB pages after the export task completes. This strengthens G5 implementation evidence but
does not close fixed-target CSV/PDF/PNG export reproducibility or G4 rendering proof.

## Current G6 Evidence

Parity worksheet proof packet:

`docs/project/evidence/dashthis-replacement/2026-06-16-g6-parity-worksheet-proof.md`

Current G6 status remains `evidence_pending`. The packet defines the fixed-range parity worksheet,
delta formulas, tolerances, required DashThis/source comparison values, result codes, and reviewer
route for paid Meta Ads, organic Facebook/Page, top posts, and Content Ops. G6 cannot pass until
G1-G5 evidence is fixed for the same report/date range and every required non-Instagram metric has
DashThis/source values, deltas, pass/fail decisions, explanations, and Andre/Raj/business approval.
Local backend regression coverage now verifies `slb_report_parity_evidence` seeds rows with the
allowed `blocked_missing_dashthis_value` result and excludes manual narrative report sections from
parity rows. This strengthens G6 implementation evidence but does not close fixed-target parity.
Local backend regression coverage now also verifies `slb_report_parity_compare` computes absolute
delta, percentage delta, pass/fail outcomes from approved percent or absolute tolerances, blocks
missing source values or missing tolerances, redacts sensitive-looking source references, and runs
without live network/provider calls. This strengthens G6 calculation quality but does not close
fixed-target parity because real DashThis/source values, approved tolerances, explanations, and
reviewer approvals remain missing.
Comparator and validator coverage now also rejects non-finite placeholder values such as `NaN` or
`Infinity` in source values, deltas, and tolerances, so a `pass` row still requires finite numeric
evidence.

## Current G7/G8 Evidence

Scheduled delivery and diagnostics proof packet:

`docs/project/evidence/dashthis-replacement/2026-06-16-g7-g8-delivery-diagnostics-proof.md`

Current G7 and G8 statuses are `evidence_pending`. The runtime paths exist, but cancellation proof
still needs a dry-run `ReportExportJob` with `delivery_status.mode == "dry_run"`, proof no client
email was sent, and support-safe diagnostics for the fixed G1 report/date range.
Local dry-run regression coverage now verifies a scheduled report dry-run can complete an export
task, produce a non-empty artifact, transition `delivery_status.status` to `rendered`, avoid email
sending, and omit recipient email values from metadata. Additional blocked-path coverage verifies
coverage-blocked dry-runs create sanitized failed evidence jobs with
`delivery_status.status == "blocked_by_coverage"` and no artifact or export enqueue. This
strengthens G7 implementation evidence but does not close fixed-target delivery proof.
Local diagnostics regression coverage now verifies an empty Content Ops dataset reports
`missing_history`, `row_count == 0`, and a null retained range instead of inheriting dates from
manual report sections or zero-count placeholders, and verifies `paid_meta_ads.last_successful_sync_at`
is populated from stored snapshot coverage when available. This strengthens G8 implementation
evidence but does not close fixed-target diagnostics or delivery proof.

## Current G9 Evidence

Safety controls proof packet:

`docs/project/evidence/dashthis-replacement/2026-06-16-g9-safety-controls-proof.md`

Current G9 status is `evidence_pending`. The backend now has explicit report action privileges,
tenant-scoped querysets, audit events, and quotas for preview/export/scheduled dry-runs, but
cancellation proof still needs fixed G1 evidence for role behavior, cross-tenant rejection,
redacted audit events, quota failures, and aggregate-only preview/diagnostics/export/dry-run/parity
payloads.
An implementation safety audit now records that the `report.v1` preview/export-preflight boundary
does not import live provider clients, Meta Direct, HTTP clients, or token-decrypt paths, and
instead routes through stored snapshots, stored Page/Post Insight rows, Content Ops aggregate
snapshots, report snapshots, sanitized audit metadata, and export artifact safety checks. This
reduces implementation uncertainty only; fixed-target runtime payloads and reviewer clearance are
still required.
Focused quota regression coverage now verifies preview, export, and scheduled dry-run quota blocks
return sanitized HTTP 429 responses without traceback, SQL, `access_token`, or `secret` strings.
This strengthens G9 implementation evidence but does not close fixed-runtime quota proof or
reviewer clearance.
Focused report privilege/audit regression coverage now verifies local viewer/analyst/admin
separation for report retrieve/export history, preview, diagnostics, export, scheduled dry-run,
schedule toggle, edit, and delete paths, plus redacted schedule/delete audit metadata. This
strengthens G9 implementation evidence but does not close fixed-target role, audit, tenant, or
reviewer proof.
Focused report tenant-isolation regression coverage now verifies cross-tenant report IDs return
`404` for retrieve, preview, diagnostics, export history, export creation, scheduled dry-run,
schedule toggle, edit, and delete, and verifies mismatched-tenant export jobs are filtered out of an
accessible report's export history. This strengthens G9 implementation evidence but does not close
fixed-target tenant proof or reviewer clearance.
Focused audit-redaction regression coverage now verifies local redacted metadata for SLB template
creation, report preview, diagnostics, export request, export blocked, scheduled dry-run, and parity
evidence generation audit events. Follow-up mutation audit coverage now verifies report
create/update metadata stores field names only without report text, layout widget values, recipient
emails, tokens, or secrets. This completes local implementation coverage for the listed G9 audit
rows, but does not close fixed-target runtime audit proof or reviewer clearance.
Focused aggregate-output redaction coverage now verifies report preview, diagnostics, manual export
metadata, scheduled dry-run metadata, and parity command output exclude injected token, secret, raw
payload, delivery email, recipient, and user-level identifier strings. This strengthens G9
implementation evidence but does not close fixed-target runtime payload proof or reviewer
clearance.
Focused no-live-provider regression coverage now verifies report preview, manual export preflight,
scheduled dry-run metadata, and parity evidence generation complete while socket, `urllib`,
`requests`, and `httpx` network calls are blocked. This strengthens the stored-aggregate-only
implementation claim for G9 but does not close fixed-target runtime payload proof or reviewer
clearance.
The new `slb_report_evidence_bundle` management command now produces a sanitized fixed-range bundle
with report metadata, preview hash, coverage summary, diagnostics for the same date range,
diagnostics source health, rendering summary, export summary, and parity rows. Focused regression
coverage verifies output redaction, safe audit metadata, and no-live-provider behavior for the
command. This improves the G2-G9 evidence collection mechanism, but it does not close any
fixed-target sub-goal until run against the approved G1 report/date range and paired with
screenshots, artifact downloads, DashThis/source comparison values, and reviewer clearance.
The new `slb_report_evidence_validate` management command now checks fixed-target evidence artifacts
offline for G10/G11 readiness hazards, including date-range mismatch, missing datasets, coverage
blockers, missing diagnostics source health, report-page gaps, empty/missing CSV/PDF/PNG export
summaries, scheduled dry-run gaps, unresolved parity rows, Instagram leakage, and high-signal
sensitive payload patterns. Focused regression coverage verifies both pass and blocker outputs.
This improves G8/G10/G11 preparation but does not close G8, G10, or G11 until run against approved
fixed G1 artifacts after G0-G9 evidence is complete.
Current evidence-file hygiene scan found no high-signal credential patterns and no email-address
matches in `docs/project/evidence/dashthis-replacement/`; broader keyword hits were placeholders,
route examples, `.env.sample` references, and policy/checklist text. This strengthens current G9
evidence-file hygiene but does not cover future fixed-target screenshots, exports, copied runtime
snippets, or reviewer clearance.

## Current G10 Evidence

Adversarial cancellation review packet:

`docs/project/evidence/dashthis-replacement/2026-06-16-g10-adversarial-review.md`

Current G10 status remains `not_started`. The packet defines the adversarial matrix for date range,
tenant/client/account/Page scope, stale/partial/missing-history states, unsupported Instagram
claims, user-level data, empty artifacts, artifact safety, CSV formula safety, delivery failure,
quota bypass, audit gaps, and rollback gaps.
The G10 packet now includes a pre-adversarial implementation review. It records local
implementation-pass evidence for tenant isolation, coverage blocking, disconnected-source labeling,
Instagram deferral, aggregate-output redaction, artifact safety, CSV formula safety, dry-run
sanitization, quota blocks, and audit redaction, while keeping every fixed-target/runtime row
pending until G0-G9 evidence exists.
G10 should not execute as cancellation evidence until G0-G9 evidence is available for the same
fixed G1 report/date range.
The machine-readable G10 validator now requires every adversarial row to point to an existing
artifact under the DashThis evidence tree, so G11 hardening cannot start from unsupported review
claims.

## Current G11 Evidence

Hardening-window packet:

`docs/project/evidence/dashthis-replacement/2026-06-16-g11-hardening-window.md`

Current G11 status remains `not_started`. The packet defines start conditions, checkpoints, reset
conditions, final gate snapshot, and reviewer route for a 24-48 hour observation window. The
hardening clock should not start until G10 has no unresolved blocker or unaccepted high-risk issue.
The G11 packet now also includes a pre-window readiness checklist, checkpoint command pack,
redaction scan, and checkpoint result template so the hardening window can be run consistently once
G0-G10 pass. This is preparation only; it does not start or satisfy G11.
The machine-readable G11 validator now requires the filled window to reference existing checkpoint,
final validation, redaction-scan, and export-snapshot artifacts under the DashThis evidence tree.
The final validation artifact must now be `slb_evidence_validation.v1` JSON from
`slb_report_evidence_validate` for the same target, with zero blockers, zero unresolved parity rows,
zero missing/unmatched source values, and no remaining parity-completion requirements. This makes
hardening evidence reproducible for G12, but current G11 status remains `not_started`.

## Current G12 Evidence

Final recommendation packet:

`docs/project/evidence/dashthis-replacement/2026-06-16-g12-final-cancellation-recommendation.md`

Current G12 status remains `not_started`, and the recommendation remains `keep_dashthis_active`.
The packet defines the final evidence rollup, cancellation scope, acceptance criteria,
rollback/monitoring plan, reviewer sign-off table, and business decision record. It cannot recommend
cancellation until G0-G11 are `passed`.
The G12 packet now includes a current no-go summary, post-cancellation monitoring template,
reversal triggers, and decision change log so the final decision can be reviewed cleanly once
G0-G11 pass. The current decision remains `keep_dashthis_active`.
The machine-readable G12 validator now requires each G0-G11 evidence rollup link to resolve to an
existing, non-empty artifact under the DashThis evidence tree, with JSON parsing and sensitive
pattern scans for text artifacts. This prevents a final keep/cancel recommendation from passing with
dead evidence links.
For G6, the rollup link must now be the `slb_evidence_validation.v1` JSON generated by
`slb_report_evidence_validate` for the same target, with zero blockers, zero unresolved parity rows,
zero missing/unmatched source values, and no remaining parity-completion requirements.
It also rejects denied, pending, or review-pending approval/signoff values in the G0-G11 rollup,
reviewer signoff table, and business-owner final decision fields.

## Reusable Next-Session Prompt

```text
You are resuming ADinsights SLB DashThis cancellation-readiness work.

Read:
- AGENTS.md
- docs/workstreams.md
- docs/project/evidence/dashthis-replacement/2026-06-16-slb-cancellation-readiness-goals.md
- docs/project/evidence/dashthis-replacement/2026-06-16-slb-reporting-render-export-parity-evidence.md
- docs/project/dashthis-replacement-reporting-plan.md
- docs/project/api-contract-changelog.md
- docs/ops/agent-activity-log.md

Task:
Pick the lowest-numbered SLB cancellation-readiness sub-goal that is not `passed` and can make
progress in the current repo/runtime context.

For that sub-goal:
1. State the selected G# and why it is next.
2. Confirm whether the work is docs-only, backend-only, frontend-only, or cross-stream.
3. If cross-stream or architecture-sensitive, route Raj/Mira before runtime edits.
4. Gather the exact evidence required by the goal doc.
5. Update the goal doc status and the SLB evidence packet.
6. Update API contract/docs/runbooks only if behavior or contracts changed.
7. Run the canonical tests/gates for touched folders, or state why no runtime tests apply.
8. End with the current DashThis decision: keep, cancellation-review ready, or cancel recommended.

Guardrails:
- Instagram remains deferred unless source rows, scopes, catalog entries, and reviewer approval are proven.
- Use stored aggregate data only; no live provider calls at report render/export time.
- Do not expose user-level metrics, secrets, OAuth tokens, or raw provider payloads.
- DashThis cancellation stays no-go until G0-G11 are complete and G12 recommends cancellation.
```

## Review Route Summary

- Raj: cross-stream scope, DashThis go/no-go, final cancellation review.
- Mira: architecture, schema versioning, snapshot/diagnostics/export consistency.
- Sofia: backend API, validation, permissions, tenant isolation.
- Andre: metric correctness, catalog semantics, parity values, coverage semantics.
- Lina: frontend payload assumptions and report review UX.
- Joel: shared renderer, responsive behavior, design consistency.
- Omar: diagnostics, stale/disconnected/missing-history states, hardening window.
- Hannah: evidence packet, support clarity, delivery proof notes.
- Priya/Martin: retained-history, dbt, mart, or retention gaps.
- Nina: artifact safety, secrets, sensitive evidence, aggregate-only proof.
- Carlos/Mei: deployment/export runtime or scheduled delivery runtime changes.
