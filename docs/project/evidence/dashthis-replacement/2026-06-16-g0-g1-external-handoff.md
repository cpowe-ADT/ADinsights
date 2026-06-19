# G0/G1 External Handoff: Raj/Mira Review And SLB Runtime Target

Date: 2026-06-16
Timezone: America/Jamaica
Status: ready for external review and operator intake; DashThis cancellation remains no-go.

## Purpose

Use this packet to unblock the first two SLB DashThis cancellation-readiness gates:

- **G0:** Raj/Mira classify the architecture/scope `GATE_BLOCK` and decide whether fixed-target
  evidence capture may proceed.
- **G1:** The operator locks one real SLB `report.v1` target, tenant/client, source scope, and date
  range so G2-G11 evidence all refers to the same proof chain.

This packet does not approve DashThis cancellation. DashThis remains active until G0-G11 pass and
G12 recommends cancellation.

## Current State

| Item | State |
| --- | --- |
| Default SLB scope | Monthly Social Report without Instagram in v1 |
| Render/export data source | Stored aggregate ADinsights data only |
| Live provider calls at preview/export | Forbidden |
| G0 status | `review_pending` |
| G1 status | `blocked_external` |
| Current preflight result | Release `GATE_BLOCK` from architecture-level scope risk |
| Current decision | Keep DashThis active |

Run the readiness doctor to confirm the current next blocker:

```bash
python3 scripts/slb_cancellation_readiness_doctor.py
```

Local demo bridge:

- `docs/project/evidence/dashthis-replacement/2026-06-17-local-demo-to-fixed-target-bridge.md`

The bridge records what the current local browser-visible report proves and, more importantly, what
must still be regenerated from the approved G1 target. Use it to avoid treating local-demo artifacts
as cancellation-review evidence.

Current local app interpretation:

- The report route renders and uses stored aggregate preview data.
- The report shows paid Meta retained rows with `source_disconnected` coverage.
- Organic Facebook/Page and Content Ops still show missing local retained history.
- The frontend now labels this state as `export with warnings`, not clean export readiness.
- The local visuals are enough to review the implementation direction, but not enough to approve
  DashThis cancellation or close fixed-target evidence goals.

## Raj/Mira Review Request

Please review:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g0-raj-mira-review-packet.md`
- `docs/project/evidence/dashthis-replacement/2026-06-16-g0-raj-mira-review-decision.template.json`
- `docs/project/evidence/dashthis-replacement/examples/g0-raj-mira-review-decision.valid-example.json`
- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake/`
- `docs/project/evidence/dashthis-replacement/preflight/2026-06-16-g0-g1-review-target-intake-with-checks/`

Decision needed:

1. Is this acceptable as a cross-stream reporting cancellation-readiness track?
2. Is the versioned report/dashboard architecture acceptable for fixed-range evidence capture?
3. May G1-G11 evidence capture proceed now, proceed with follow-ups, or must it stop for runtime
   changes first?
4. Are the reviewer routes correct for Sofia, Andre, Lina/Joel, Omar/Hannah, Nina, and
   Priya/Martin if retention gaps appear?
5. Confirm DashThis cancellation remains no-go until G0-G11 pass and G12 recommends cancellation.

Fill the G0 decision JSON, then run:

```bash
python3 scripts/validate_slb_g0_raj_mira_review.py \
  --review-file <filled-g0-raj-mira-review-decision.json>
```

G0 can move to `passed` only if the validator returns valid and BLK-001 is marked resolved or
explicitly waived by Raj/Mira.

The validator rejects internally inconsistent G0 decisions. Clean approvals must use clean scope and
architecture acceptance, approvals with followups must preserve the follow-up capture mode and real
follow-up rows, and blocked decisions must keep G1-G11 evidence capture blocked.

## Operator G1 Intake Request

After G0 allows evidence capture, fill:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g1-runtime-target-intake.template.json`
- `docs/project/evidence/dashthis-replacement/2026-06-16-g1-runtime-target-intake-checklist.md`
- `docs/project/evidence/dashthis-replacement/examples/g1-runtime-target-intake.valid-example.json`

The examples are schema-valid but are not evidence. They exist only to show the expected field
shape and wording.

Minimum required fields:

| Field | Required value |
| --- | --- |
| Environment | Target runtime used for evidence capture |
| Backend/frontend URLs | Safe runtime URLs |
| Safe tenant/client | Redacted labels only |
| `ReportDefinition.id` | Real SLB report record |
| `template_key` | `slb_monthly_social_report` |
| Schema version | `report.v1` |
| Primary date range | Fixed month, recommended 2026-05-01 through 2026-05-31 unless operator chooses otherwise |
| Timezone | `America/Jamaica` |
| Currency | Required for paid parity |
| Paid Meta account scope | Redacted account label or ID |
| Organic Facebook Page scope | Redacted Page label or ID |
| Content Ops scope | Redacted workspace/client label |
| DashThis/source owner | Person or team responsible for comparison values |
| Scheduled delivery | `dry_run_only` |
| Recipient assumption | Redacted recipient group only |
| Instagram decision | `deferred_in_v1` |
| DashThis status | Active |

Generate a redacted target summary:

```bash
backend/.venv/bin/python backend/manage.py slb_report_target_intake \
  --report-id <slb-report-id>
```

Validate the filled G1 intake JSON:

```bash
python3 scripts/validate_slb_g1_runtime_target_intake.py \
  --intake-file <filled-g1-runtime-target-intake.json>
```

The G1 validator requires Raj and Mira clearance values to approve or conditionally approve fixed
evidence capture. If either reviewer decision includes followups or conditions, the intake must
preserve that conditional approval state and include real condition notes.

Validate that G0 and G1 agree before starting G2-G11 evidence:

```bash
python3 scripts/validate_slb_g0_g1_handoff.py \
  --g0-review-file <filled-g0-raj-mira-review-decision.json> \
  --g1-intake-file <filled-g1-runtime-target-intake.json>
```

The combined handoff validator is the final local bridge before fixed-target evidence capture. It
checks that Raj/Mira reviewer decisions in G1 preserve the filled G0 reviewer decisions, target dates
are bounded and ordered, comparison owner/location fields are filled, and the redacted target-intake
output is attached.

G1 can move to `passed` only if the validator returns valid, the target summary is attached, and
BLK-002 is marked resolved or explicitly waived by the correct reviewer route.

## Copy/Paste Review Message

```text
Raj/Mira: please review the SLB DashThis cancellation-readiness G0 packet and classify the current
architecture/scope preflight GATE_BLOCK. The ask is not to cancel DashThis. The ask is whether
G1-G11 fixed-target evidence capture may proceed for the SLB Monthly Social Report without
Instagram in v1, using stored aggregate ADinsights data only and no live provider calls at
preview/export time.

Decision artifact:
docs/project/evidence/dashthis-replacement/2026-06-16-g0-raj-mira-review-decision.template.json

Validator:
python3 scripts/validate_slb_g0_raj_mira_review.py --review-file <filled-g0-raj-mira-review-decision.json>

Current decision remains: keep DashThis active / cancellation no-go.
```

## Current-State Review Message

Use this shorter message when Raj/Mira only need the current decision request:

```text
Raj/Mira: please classify the current ADinsights SLB reporting G0 architecture/scope gate.

What exists now:
- report.v1 SLB report rendering works locally.
- Preview/render uses stored aggregate ADinsights data only.
- Paid Meta has retained rows, but the local source state is disconnected.
- Organic Facebook/Page and Content Ops show missing local retained history.
- The frontend now shows "export with warnings" when export can run but coverage is stale,
  missing, partial, or disconnected.

Decision needed:
1. Is the implemented cross-stream reporting scope acceptable for fixed-target evidence capture?
2. Is the architecture acceptable for this proof: governed catalog, versioned dashboard/report
   layouts, stored aggregate preview/render, report snapshots, diagnostics, dry-run delivery,
   permissions/audit/quotas?
3. May G1-G11 fixed-target evidence capture proceed, proceed with follow-ups, or stop for runtime
   changes first?
4. Are Sofia, Andre, Lina/Joel, Omar/Hannah, Nina, and Priya/Martin the correct reviewer route?
5. Confirm DashThis remains active and cancellation remains no-go until G0-G11 pass and G12 makes
   the final recommendation.

Decision artifact:
docs/project/evidence/dashthis-replacement/2026-06-16-g0-raj-mira-review-decision.template.json

Validator:
python3 scripts/validate_slb_g0_raj_mira_review.py --review-file <filled-g0-raj-mira-review-decision.json>
```

## Completion Rules

G0/G1 handoff is complete only when:

- G0 decision JSON validates.
- G1 runtime target JSON validates.
- Combined G0/G1 handoff validation confirms the G1 clearance follows the filled Raj/Mira decision.
- Goal doc, evidence packet, blocker register, status manifest, and activity log are updated.
- DashThis remains active.
- No downstream G2-G12 packet claims cancellation-review readiness until the same fixed G1 target
  is used throughout the evidence chain.
