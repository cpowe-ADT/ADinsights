# G12 Final DashThis Cancellation Recommendation

Date: 2026-06-16
Timezone: America/Jamaica
Status: decision template; current recommendation is keep DashThis active.

## Purpose

Make the final SLB DashThis keep/cancel recommendation after G0-G11 evidence is complete. This
packet is the last decision artifact, not a place to gather missing proof. If earlier evidence is
missing, weak, contradictory, or unreviewed, the recommendation must be `keep_dashthis_active`.

Machine-readable template:

`docs/project/evidence/dashthis-replacement/2026-06-16-g12-final-recommendation.template.json`

Validate a filled final recommendation:

```bash
python3 scripts/validate_slb_g12_final_recommendation.py \
  --recommendation-file <filled-g12-final-recommendation.json> \
  --status-manifest-file docs/project/evidence/dashthis-replacement/2026-06-16-slb-cancellation-readiness-status.json \
  --g11-window-file <filled-g11-hardening-window.json>
```

The validator checks G0-G11 pass state, fixed-target consistency with G11, reviewer and business
owner sign-offs, rollback/monitoring ownership, included/excluded dataset scope, stored-aggregate
render/export guardrails, DashThis action, decision log, and sensitive-value hygiene.

## Decision Options

| Recommendation                    | Meaning                                                                                   | Allowed when                                                                |
| --------------------------------- | ----------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `keep_dashthis_active`            | Do not cancel DashThis. Continue using DashThis as the official fallback/source of truth. | Any G0-G11 evidence is missing, failed, unreviewed, or disputed.            |
| `cancellation_review_ready`       | Evidence is complete enough for business owner review, but DashThis is not cancelled yet. | G0-G11 pass and reviewers agree no blocker remains.                         |
| `cancel_dashthis_recommended`     | Recommend cancelling DashThis for SLB non-Instagram monthly reporting.                    | Business owner accepts G0-G11 evidence, rollback path, and monitoring plan. |
| `cancel_dashthis_not_recommended` | Evidence is complete enough to decide, but risks/gaps mean DashThis should stay.          | G0-G11 evidence exposes unacceptable gaps or parity failures.               |

Current recommendation: `keep_dashthis_active`.

## Current No-Go Summary

DashThis must remain active. The current `keep_dashthis_active` recommendation is not a business
preference; it follows directly from unresolved evidence gates.

| Blocking area                | Current state                                                                                      | Why cancellation cannot proceed                                                                       |
| ---------------------------- | -------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| G0 architecture/scope review | Raj/Mira review is still pending.                                                                  | Cross-stream architecture risk has not been accepted or cleared.                                      |
| G1 fixed proof target        | Runtime tenant/client/report/date range is not filled.                                             | No cancellation claim can be tied to a real SLB report.                                               |
| G2/G3 coverage/history       | Fixed-target stored coverage and monthly/90-day retained-history proof is missing.                 | ADinsights cannot yet prove it can report the required period from stored aggregate data.             |
| G4/G5 render/export          | Fixed-target dashboard/report rendering and CSV/PDF/PNG artifact proof is missing.                 | Export parity and reproducibility are unproven.                                                       |
| G6 parity                    | DashThis/source values and deltas are missing.                                                     | Metric parity has not been established.                                                               |
| G7/G8 delivery/diagnostics   | Fixed-target dry-run and diagnostics proof is missing.                                             | Support and delivery replacement are unproven.                                                        |
| G9 safety                    | Strong local implementation evidence exists, but fixed-target safety proof and review are missing. | Tenant, audit, quota, aggregate-only, and artifact hygiene must be proven on the real evidence chain. |
| G10 adversarial review       | Pre-review exists only; fixed-chain adversarial review has not run.                                | Known-risk challenge has not passed.                                                                  |
| G11 hardening                | Runbook is prepared, but no 24-48 hour window has started.                                         | Stability over time is unproven.                                                                      |

Decision rule: if any row above remains unresolved, the recommendation stays
`keep_dashthis_active`.

## Final Evidence Rollup

| Goal | Required proof                                                               | Evidence link                                             | Reviewer approval | Status  |
| ---- | ---------------------------------------------------------------------------- | --------------------------------------------------------- | ----------------- | ------- |
| G0   | Raj/Mira architecture and scope review cleared                               | `2026-06-16-g0-raj-mira-review-packet.md`                 | Pending           | Pending |
| G1   | Fixed SLB tenant/client/report/date range chosen                             | `2026-06-16-g1-fixed-slb-proof-target.md`                 | Pending           | Pending |
| G2   | Stored data coverage proven                                                  | `2026-06-16-g2-g3-coverage-retained-history-proof.md`     | Pending           | Pending |
| G3   | Monthly and 90-day retained history proven                                   | `2026-06-16-g2-g3-coverage-retained-history-proof.md`     | Pending           | Pending |
| G4   | Saved dashboard and SLB report rendering proven                              | `2026-06-16-g4-g5-render-export-reproducibility-proof.md` | Pending           | Pending |
| G5   | CSV/PDF/PNG exports proven non-empty and reproducible                        | `2026-06-16-g4-g5-render-export-reproducibility-proof.md` | Pending           | Pending |
| G6   | Parity worksheet completed against DashThis/source values                    | `2026-06-16-g6-parity-worksheet-proof.md`                 | Pending           | Pending |
| G7   | Scheduled delivery dry-run proven without client email                       | `2026-06-16-g7-g8-delivery-diagnostics-proof.md`          | Pending           | Pending |
| G8   | Diagnostics/support proof captured safely                                    | `2026-06-16-g7-g8-delivery-diagnostics-proof.md`          | Pending           | Pending |
| G9   | Permissions, tenant isolation, audit, quotas, aggregate-only behavior proven | `2026-06-16-g9-safety-controls-proof.md`                  | Pending           | Pending |
| G10  | Adversarial review completed                                                 | `2026-06-16-g10-adversarial-review.md`                    | Pending           | Pending |
| G11  | 24-48 hour hardening window recorded                                         | `2026-06-16-g11-hardening-window.md`                      | Pending           | Pending |

## Cancellation Scope

| Scope item                                 | Decision                                                                 |
| ------------------------------------------ | ------------------------------------------------------------------------ |
| Client/report                              | Pending G1                                                               |
| Reporting period                           | Pending G1                                                               |
| Included datasets                          | `paid_meta_ads`, `organic_facebook_page`, `content_ops` pending proof    |
| Excluded datasets                          | `organic_instagram` deferred in v1 unless separately proven and approved |
| Render source                              | Stored aggregate ADinsights data only                                    |
| Live provider calls at preview/export time | Not allowed                                                              |
| Official fallback during review            | DashThis remains active                                                  |

## Final Acceptance Criteria

All must be true before the recommendation can move beyond `keep_dashthis_active`:

- G0-G11 statuses are `passed` in the goal controller.
- G1 identifies the exact tenant/client/report/date range in safe terms.
- Every required non-Instagram SLB section renders from stored aggregate data.
- CSV, PDF, and PNG exports are non-empty, safe to download, and reproducible from
  `report_snapshot` metadata.
- Preview, diagnostics, export metadata, parity output, dry-run metadata, and evidence files contain
  no secrets, raw provider payloads, or user-level metrics.
- Parity worksheet includes ADinsights values, DashThis/source values, deltas, tolerances,
  pass/fail, and explanations for every required metric.
- Scheduled delivery dry-run is proven without sending client email.
- Diagnostics/support proof explains missing/stale/partial/disconnected states without reading logs.
- G9 safety proof passes permissions, tenant isolation, audit, quota, and aggregate-only checks.
- G10 adversarial review has no unresolved blocker.
- G11 hardening window completes without reset conditions.
- Raj, Mira, Sofia, Andre, Lina, Omar, Hannah, Nina, and the business owner have recorded the
  approvals relevant to their domains.
- Rollback and monitoring path is documented.

## Rollback And Monitoring Plan

DashThis may be cancelled only after the business owner accepts this plan.

| Area                  | Required plan                                                                                                                 | Evidence/status |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------- | --------------- |
| Short-term rollback   | Keep DashThis active until cancellation date; confirm ability to re-subscribe or recover exported DashThis reports if needed. | Pending         |
| ADinsights monitoring | Monitor report preview, diagnostics, export, scheduled dry-run, freshness, and sync states after cancellation.                | Pending         |
| Support owner         | Name the person responsible for first SLB reporting support response.                                                         | Pending         |
| Escalation owner      | Name Raj/Mira/Omar escalation path for report failure after cancellation.                                                     | Pending         |
| Client communication  | Define whether SLB receives ADinsights-generated report artifacts, DashThis artifacts, or both during transition.             | Pending         |
| Reversal trigger      | Define conditions that require reinstating DashThis or using exported DashThis historical reports.                            | Pending         |

## Post-Cancellation Monitoring Template

Fill this before recommending cancellation. It should name the owner, interval, signal, and action
for each operational surface.

| Monitor                    | Owner   | Interval                          | Signal                                                              | Action threshold                                      | Evidence location |
| -------------------------- | ------- | --------------------------------- | ------------------------------------------------------------------- | ----------------------------------------------------- | ----------------- |
| Report preview             | Pending | Daily for first week, then weekly | Preview HTTP status, preview hash, coverage summary                 | Any failed preview or unexpected coverage drop        | Pending           |
| Diagnostics                | Pending | Daily for first week, then weekly | Dataset status, retained range, row counts, recommended next action | Any missing/stale/partial state without expected note | Pending           |
| Exports                    | Pending | Each report cycle                 | CSV/PDF/PNG job status, byte count, snapshot hash                   | Empty/corrupt artifact or snapshot mismatch           | Pending           |
| Scheduled dry-run/delivery | Pending | Each scheduled cycle              | Delivery status, failure reason, no unintended recipient exposure   | Failed delivery or unredacted recipient issue         | Pending           |
| Sync/freshness             | Pending | Daily                             | Last successful sync, source disconnected state, row counts         | Sync stale beyond SLA or unexpected empty sync        | Pending           |
| Safety/audit               | Pending | Weekly during transition          | Audit event presence, permission/tenant boundaries, secret scan     | Missing audit, unsafe payload, or cross-tenant issue  | Pending           |
| Client support             | Pending | Each SLB reporting cycle          | Support tickets/questions, report discrepancy claims                | Any parity dispute or missing section                 | Pending           |

## Reversal Triggers

If DashThis is ever cancelled, any trigger below should activate the rollback path immediately.

| Trigger                                                                         | Severity | Immediate action                                                                    |
| ------------------------------------------------------------------------------- | -------- | ----------------------------------------------------------------------------------- |
| Required SLB report cannot render from stored aggregate data.                   | blocker  | Use DashThis fallback/exported historical packet and stop ADinsights-only delivery. |
| CSV/PDF/PNG artifact is empty, corrupt, unsafe, or not downloadable.            | blocker  | Use fallback artifact path and open export incident.                                |
| Coverage metadata hides stale, partial, disconnected, or missing-history state. | blocker  | Stop cancellation rollout and route to Omar/Sofia/Andre.                            |
| Parity drifts beyond accepted tolerance without approved explanation.           | high     | Compare source/DashThis values and decide keep/reinstate fallback.                  |
| Tenant isolation, permission, audit, secret, or user-level data issue appears.  | blocker  | Stop report delivery, preserve evidence, escalate to Raj/Mira/Nina.                 |
| Scheduled delivery sends to wrong recipients or exposes recipient data.         | blocker  | Stop scheduler/delivery path and notify owners per incident process.                |
| SLB/business owner disputes report correctness.                                 | high     | Keep/restore DashThis fallback until dispute is resolved.                           |

## Business Decision Record

| Field              | Value                    |
| ------------------ | ------------------------ |
| Recommendation     | `keep_dashthis_active`   |
| Decision maker     | Pending                  |
| Decision date      | Pending                  |
| Accepted scope     | Pending                  |
| Known exclusions   | Instagram deferred in v1 |
| Known risks        | Pending G0-G11 evidence  |
| Required follow-up | Complete G0-G11          |
| DashThis action    | Keep active              |

## Decision Change Log

| Date/time America/Jamaica | Recommendation         | Reason                                                                  | Approver/owner |
| ------------------------- | ---------------------- | ----------------------------------------------------------------------- | -------------- |
| 2026-06-16                | `keep_dashthis_active` | Initial G12 packet; G0-G11 evidence incomplete.                         | Pending        |
| Pending                   | Pending                | Update only after G0-G11 pass or expose an accepted no-cancel decision. | Pending        |

## Reviewer Sign-Off

| Reviewer       | Domain                                            | Decision | Notes/date |
| -------------- | ------------------------------------------------- | -------- | ---------- |
| Raj            | Cross-stream scope and DashThis go/no-go          | Pending  | Pending    |
| Mira           | Architecture and report/export consistency        | Pending  | Pending    |
| Sofia          | Backend API, tenant isolation, permissions        | Pending  | Pending    |
| Andre          | Metrics, catalog, parity, coverage semantics      | Pending  | Pending    |
| Lina           | Frontend report UX and payload assumptions        | Pending  | Pending    |
| Joel           | Shared renderer/responsive behavior               | Pending  | Pending    |
| Omar           | Diagnostics, stale/disconnected states, hardening | Pending  | Pending    |
| Hannah         | Support clarity and evidence packet               | Pending  | Pending    |
| Nina           | Secrets, artifacts, aggregate-only safety         | Pending  | Pending    |
| Business owner | Final cancellation decision                       | Pending  | Pending    |

## G12 Pass Rules

G12 can move to `passed` only when all are true:

- G0-G11 are `passed`.
- The recommendation is no longer pending and is one of the explicit decision options above.
- Required reviewer sign-offs are filled.
- Rollback/monitoring plan is filled.
- The main evidence packet current decision matches this packet.
- The decision is logged in `docs/ops/agent-activity-log.md`.

Current decision: keep DashThis active. Cancellation remains no-go.
