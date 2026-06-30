# G10 Adversarial Cancellation Review

Date: 2026-06-16
Timezone: America/Jamaica
Status: pre-adversarial implementation review captured; G10 remains `not_started` for
cancellation evidence until G0-G9 fixed-target evidence is available.

## Purpose

Try to disprove SLB DashThis cancellation-readiness before anyone relies on ADinsights as the
replacement reporting system. This is not a feature QA checklist. It is an adversarial review of
the fixed G1 report/date range, stored aggregate data path, export artifacts, delivery proof,
safety controls, and rollback plan.

If a check exposes a real issue, it must become one of:

- Code fix with focused tests.
- Evidence note with reviewer acceptance.
- Runbook/support update.
- Explicit cancellation blocker.

## Preconditions

G10 should not be executed until these are at least evidence-complete for the same fixed SLB report:

- G0 Raj/Mira review route.
- G1 fixed SLB tenant/client/report/date range.
- G2/G3 stored coverage and retained-history evidence.
- G4/G5 render/export reproducibility evidence.
- G6 parity worksheet evidence.
- G7/G8 scheduled dry-run and diagnostics evidence.
- G9 safety controls evidence.

If any prerequisite is missing, record it in the findings table and keep G10 `not_started` or
`evidence_pending`.

Machine-readable G10 review template:

- `docs/project/evidence/dashthis-replacement/2026-06-16-g10-adversarial-review.template.json`

Validate the filled G10 review before starting G11:

```bash
python3 scripts/validate_slb_g10_adversarial_review.py \
  --review-file <filled-g10-adversarial-review.json> \
  --g2-g9-run-file <filled-g2-g9-evidence-run.json>
```

The validator fails if the G10 target drifts from the G2-G9 run, any adversarial row remains open,
high/blocker findings lack a fixed/accepted/waived resolution, unsupported Instagram claims appear,
DashThis is not active, rollback is not confirmed, Raj/Mira acceptance is missing, or sensitive/
user-level patterns appear.

It also requires the referenced G2-G9 run to include `evidence_files.evidence_validation`, pointing
to a passing `slb_evidence_validation.v1` JSON artifact from `slb_report_evidence_validate`. That
artifact must have `readiness_status == "pass"`, `blocker_count == 0`, and evidence identity matching
the G10 target report ID, `slb_monthly_social_report` template key, fixed date range, and preview
hash. This prevents G10 from advancing on a self-reported G2-G9 status without validated render,
export, parity, coverage, delivery, diagnostics, and safety evidence underneath it.

## Pre-Adversarial Implementation Review

This section records repo-side implementation evidence available before the fixed G1 SLB target is
confirmed. It is useful for narrowing future review work, but it does not satisfy G10 pass rules.
Any row marked implementation pass must be rechecked against the same fixed report/date range used
for G2-G9 evidence.

## Adversarial Test Matrix

| Attack area               | Disproof question                                                                                      | Evidence to collect                                                                                           | Expected safe result                                                                                    | Actual result                                                                                                                                                                                                            | Decision                                     |
| ------------------------- | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------- |
| Date range                | Can the report silently use the wrong start/end date or timezone?                                      | Compare G1 date range, preview payload, export snapshot, parity command, artifact labels, and appendix notes. | All surfaces use the same bounded range in `America/Jamaica`, or differences are explicit and approved. | Blocked: G1 fixed report/date range is still missing. Existing report/catalog validation rejects unbounded ranges, but no fixed SLB runtime comparison exists.                                                           | Runtime pending                              |
| Tenant scope              | Can one tenant read another tenant's report, export metadata, diagnostics, or artifact?                | Reuse G9 cross-tenant checks plus export download checks.                                                     | Cross-tenant access returns 403/404 or empty; no foreign data appears.                                  | Implementation evidence: focused G9 tests verify cross-tenant report action rejection and export-history tenant filtering. Fixed runtime proof and artifact download checks still pending.                               | Implementation pass; runtime pending         |
| Client/account/page scope | Can paid account, Page, or client filters drift from the SLB proof target?                             | Compare report filters, preview coverage source labels, diagnostics source labels, and parity rows.           | Every widget is scoped to the fixed G1 account/Page/client.                                             | Partial implementation evidence: dashboard widget preview rejects cross-tenant account references. Fixed SLB client/account/Page scope is blocked by G1.                                                                 | Partial implementation pass; runtime pending |
| Stale freshness           | Can stale data be labeled fresh or exported without a stale note?                                      | Force or inspect stale coverage state in preview, diagnostics, export metadata, report UI, and appendix.      | Stale state is visible beside widgets and in appendix/export metadata.                                  | Implementation path exists through coverage states and diagnostics, but fixed stale/fresh SLB evidence has not been captured.                                                                                            | Runtime pending                              |
| Partial coverage          | Can partial data be exported as complete?                                                              | Inspect `coverage_policy`, blocking reasons, coverage summary, and exported notes.                            | `require_full_coverage` blocks; `render_with_warning` renders with visible warning.                     | Implementation evidence: report preview/export tests verify `require_full_coverage` blocks missing coverage and export preflight stores coverage metadata. Fixed SLB coverage still pending.                             | Implementation pass; runtime pending         |
| Missing history           | Can missing monthly or 90-day history be hidden?                                                       | Compare G2/G3 retained range tables against preview/export coverage.                                          | Missing history is blocked or explicit; no parity pass claimed.                                         | Blocked: G2/G3 monthly and 90-day retained-history proof has not been captured for a fixed SLB report.                                                                                                                   | Runtime pending                              |
| Source disconnected       | Can disconnected sources render misleading current data?                                               | Disconnect or simulate disconnected state and inspect preview/export/diagnostics.                             | Historical data renders only with clear disconnected-source note, or blocks if required.                | Implementation evidence: widget preview tests label disconnected sources with available history. Fixed SLB disconnected-source proof still pending.                                                                      | Implementation pass; runtime pending         |
| Unsupported Instagram     | Can Instagram leak into v1 claims or template pages without proof?                                     | Inspect template pages, catalog datasets, evidence packet, parity worksheet, and final recommendation.        | Instagram remains deferred and absent from cancellation parity claims.                                  | Implementation/evidence pass: SLB template tests assert `organic_instagram` is absent; evidence packets keep Instagram deferred. Reviewer/final recommendation still pending.                                            | Implementation pass; reviewer pending        |
| User-level data           | Can payloads expose user, viewer, commenter, reaction identity, recipient email, or raw provider data? | Inspect preview, diagnostics, export metadata, parity output, artifacts, audit logs, evidence docs.           | Aggregate-only values; no secrets or user-level records.                                                | Implementation evidence: G9 payload, audit, and evidence-file scans pass locally; fixed runtime payload/artifact scan still pending.                                                                                     | Implementation pass; runtime pending         |
| Empty artifacts           | Can CSV/PDF/PNG jobs report success with empty or corrupt files?                                       | Verify artifact byte size, MIME/content type, download status, and renderer verification.                     | Non-empty artifacts only count as evidence; failures are blockers.                                      | Implementation/local smoke evidence exists for non-empty CSV/PDF/PNG exports after local Playwright setup; fixed SLB export jobs and download proof still pending.                                                       | Implementation pass; runtime pending         |
| Artifact safety           | Can export paths escape the artifact root or expose private server paths?                              | Inspect download route response and stored metadata.                                                          | Public payloads do not expose unsafe paths; downloads are rooted safely.                                | Implementation evidence: export download tests cover rooted path containment, path traversal rejection, empty artifact failure, and cross-tenant download rejection. Fixed artifact metadata review still pending.       | Implementation pass; runtime pending         |
| CSV formula safety        | Can exported CSV cells trigger formulas in spreadsheet tools?                                          | Inspect CSV values beginning with `=`, `+`, `-`, `@`, tab, or carriage return.                                | Dangerous formula-leading values are sanitized or blocked.                                              | Implementation evidence: CSV export test verifies formula-leading campaign values are prefixed before download. Fixed SLB CSV artifact inspection still pending.                                                         | Implementation pass; runtime pending         |
| Delivery failure          | Can scheduled dry-run imply real delivery success, or hide failures?                                   | Inspect dry-run metadata, latest scheduled run, and no-client-email proof.                                    | Dry-run is labeled `mode=dry_run`; failure statuses are sanitized and visible.                          | Implementation evidence: scheduled dry-run tests verify sanitized dry-run metadata and no real send path; fixed SLB no-client-email proof still pending.                                                                 | Implementation pass; runtime pending         |
| Quota bypass              | Can preview/export/scheduled dry-run be abused past limits?                                            | Reuse G9 quota evidence and API responses.                                                                    | Quotas return sanitized 429 responses at the configured boundary.                                       | Implementation evidence: quota regression tests return sanitized 429 responses for preview, export, and scheduled dry-run denial. Fixed runtime quota exercise still pending.                                            | Implementation pass; runtime pending         |
| Audit gap                 | Can important report actions happen without redacted audit evidence?                                   | Compare G9 audit matrix against runtime activity.                                                             | Required actions are audited with redacted metadata.                                                    | Implementation evidence: G9 audit regressions cover create/update/delete, schedule toggle, template, preview, diagnostics, export request/block, dry-run, and parity generation. Fixed runtime audit rows still pending. | Implementation pass; runtime pending         |
| Rollback gap              | If cancellation happens and ADinsights fails, is the rollback path clear?                              | Inspect G12 rollback/keep-DashThis decision and ops runbook notes.                                            | DashThis remains active until final approval; rollback/monitoring owner is named.                       | Partial evidence: all current packets say DashThis remains active/no-go. Final rollback/monitoring owner and G12 decision are still missing.                                                                             | Blocked until G12                            |

## Required Gates

Attach the command output or evidence packet reference for the same code state under review:

Offline evidence artifact validation:

```bash
backend/.venv/bin/python backend/manage.py slb_report_evidence_validate \
  --evidence-bundle "$ADI_EVIDENCE_TMP/evidence-bundle.json" \
  --parity-comparison "$ADI_EVIDENCE_TMP/parity-comparison.json" \
  --expected-start-date "$ADI_START_DATE" \
  --expected-end-date "$ADI_END_DATE" \
  --format markdown
```

The validator must return `readiness_status == "pass"` before G10 can move from pre-adversarial
review into cancellation evidence. Any blocker must become a fix, accepted evidence note, runbook
update, or explicit cancellation blocker.

The same validation output must be attached to the filled G2-G9 run as
`evidence_files.evidence_validation`; G10 validation checks that the attached artifact matches the
same fixed report, template, date range, and preview hash.

```bash
make backend-lint
make backend-test
make frontend-guardrails
make frontend-lint
make frontend-test
make frontend-build
scripts/dev-healthcheck.sh
make adinsights-preflight PROMPT="Assess SLB DashThis adversarial cancellation readiness"
```

Run dbt gates only if G10 exposes a retained-history or mart gap that requires dbt changes:

```bash
make dbt-deps
./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' run --select staging
./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' snapshot
./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' run --select marts
./scripts/dbt-wrapper.sh 'dbt' 'dbt' 'dbt' test --select all_ad_performance dim_campaign fact_performance vw_campaign_daily
```

## Findings Log

| ID      | Finding                                                                                                                                                 | Severity  | Evidence                                                                                                                                                                                                                                                                                      | Resolution path                                                                                                                       | Owner/reviewer           | Status        |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------ | ------------- |
| ADV-001 | G10 cannot be executed as cancellation evidence until G0-G9 fixed-target evidence exists.                                                               | `blocker` | G0 remains `review_pending`; G1 remains `blocked_external`; G2-G9 are not fixed-runtime complete.                                                                                                                                                                                             | Keep DashThis active and do not start G11 hardening until G0-G9 are evidence-complete.                                                | Raj, Mira, Omar, Hannah  | Open          |
| ADV-002 | Pre-adversarial implementation audit found no live provider client imports or token-decrypt paths in the `report.v1` preview/export-preflight boundary. | `info`    | `2026-06-16-g9-safety-controls-proof.md` implementation safety audit.                                                                                                                                                                                                                         | Re-run payload inspection against the fixed G1 SLB report/date range before marking G9/G10 passed.                                    | Sofia, Nina, Raj         | Evidence-only |
| ADV-003 | Local implementation evidence now covers several adversarial safety risks, but fixed-target runtime evidence is still missing.                          | `info`    | G9 proof includes quota, role/permission, tenant isolation, audit redaction, aggregate-output redaction, evidence-file hygiene, artifact safety, and CSV formula safety tests.                                                                                                                | Treat as pre-review acceleration only; re-run the matrix against the fixed G1 report/date range.                                      | Sofia, Nina, Omar, Raj   | Evidence-only |
| ADV-004 | G10 remains blocked by external proof dependencies, not by a known failing implementation test.                                                         | `blocker` | BLK-001 through BLK-009 remain open, especially Raj/Mira review, G1 target, DashThis/source values, fixed coverage/history, render/export, delivery/diagnostics, and fixed-target G9 evidence.                                                                                                | Do not start G11 hardening or G12 cancellation recommendation until external blockers are resolved or explicitly waived.              | Raj, Mira, Hannah, Omar  | Open          |
| ADV-005 | Offline evidence validation now exists to catch artifact-level G10 blockers before hardening.                                                           | `info`    | `slb_report_evidence_validate` verifies date-range consistency, required datasets, coverage blockers, report pages, non-empty CSV/PDF/PNG exports, scheduled dry-run evidence, parity comparison results, Instagram deferral, and sensitive-pattern hygiene. Focused validation tests passed. | Run it against fixed G1 artifacts after G2-G9 evidence exists; any blocker remains a cancellation blocker until resolved or accepted. | Sofia, Omar, Hannah, Raj | Evidence-only |

Severity values:

- `blocker` - DashThis cancellation cannot proceed.
- `high` - must be fixed or explicitly accepted by Raj/Mira before cancellation review.
- `medium` - can proceed only with documented mitigation.
- `low` - note or follow-up is acceptable.
- `info` - evidence-only observation.

## Reviewer Route

- Raj: cancellation gate, business risk, rollback path, unresolved blocker acceptance.
- Mira: architecture, preview/export/report snapshot consistency, cross-stream implications.
- Sofia: backend API behavior, permission/tenant boundaries, export safety.
- Andre: metric semantics, coverage state correctness, parity interpretation.
- Lina/Joel: frontend report rendering, responsive behavior, visible coverage notes.
- Omar/Hannah: operational diagnosis, stale/disconnected/missing-history handling, support clarity.
- Nina: secrets, raw provider payloads, artifact safety, user-level data checks.
- Priya/Martin: required if retained-history, marts, or dbt coverage gaps appear.
- Carlos/Mei: required if export runtime, artifact storage, delivery runtime, or rollback process changes.

## G10 Pass Rules

G10 can move to `passed` only when all are true:

- Every row in the adversarial matrix has actual evidence and a decision.
- Every blocker/high issue is fixed, accepted with named reviewer sign-off, or recorded as a
  cancellation blocker.
- No unsupported Instagram claim remains in v1 evidence.
- No stale/partial/missing-history state can be mistaken for full fresh coverage.
- No user-level data, secrets, raw provider payloads, or unsafe artifact paths appear in the proof.
- Raj and Mira agree the remaining risk posture is acceptable for the 24-48 hour hardening window.

Current decision: G10 is not executed. DashThis cancellation remains no-go.
