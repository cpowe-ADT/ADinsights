# G1 Runtime Target Intake Checklist

Date: 2026-06-16
Timezone: America/Jamaica
Goal ID: G1
Status: operator intake checklist; G1 remains `blocked_external` until completed and reviewed.

## Purpose

Use this checklist to lock the exact runtime target for the SLB DashThis cancellation-readiness
proof before collecting coverage, retained-history, rendering, export, parity, delivery,
diagnostics, safety, adversarial, or hardening evidence.

This is not a cancellation approval. It only turns G1 from an abstract proof target into a concrete
runtime target that later evidence can consistently reference.

## Rules

- Do not paste secrets, OAuth tokens, raw provider exports, private recipient lists, or user-level
  rows.
- Use safe/redacted tenant, client, ad-account, Page, workspace, and recipient labels.
- Keep Instagram deferred unless source rows, scopes, catalog entries, and reviewer approval are
  proven in a separate decision record.
- Use stored aggregate ADinsights data only for report preview/export evidence. Do not call live
  provider APIs during render/export proof.
- If any later evidence uses a different tenant, report, source scope, or date range, it does not
  count for this G1 chain until this checklist is updated and re-approved.

## Operator Fill-In

| Field | Value | Evidence/source | Owner | Status |
| --- | --- | --- | --- | --- |
| Target environment | Pending | Pending | Pending | Required |
| Backend URL | Pending | Pending | Pending | Required |
| Frontend URL | Pending | Pending | Pending | Required |
| Safe tenant identifier | Pending | Pending | Pending | Required |
| Safe client identifier | SLB / Students' Loan Bureau | Gmail-derived inventory; operator to confirm | Pending | Required |
| `ReportDefinition.id` | Pending | Runtime report record | Pending | Required |
| `template_key` | `slb_monthly_social_report` expected | Runtime report record | Pending | Required |
| Report schema version | `report.v1` expected | Runtime report record | Pending | Required |
| Primary date range | Recommended: 2026-05-01 through 2026-05-31 | SLB May 2026 report inventory; operator to confirm | Pending | Required |
| Baseline date range | Recommended: 2026-03-01 through 2026-04-30 | SLB March-April report inventory; operator to confirm | Pending | Optional |
| Timezone used for proof | America/Jamaica | Goal guardrail | Pending | Required |
| Currency | Pending | Source/report config | Pending | Required for paid parity |
| Paid Meta account scope | Pending | Redacted account label or ID | Pending | Required |
| Organic Facebook Page scope | Pending | Redacted Page label or ID | Pending | Required |
| Content Ops workspace/client scope | Pending | Redacted workspace/client label | Pending | Required |
| DashThis/source comparison owner | Pending | Operator/business confirmation | Pending | Required |
| DashThis/source evidence location | Pending | Redacted evidence path or owner note | Pending | Required for G6 |
| Scheduled delivery mode | Dry-run only | Goal guardrail | Pending | Required |
| Recipient assumption | Pending | Redacted recipient group or owner note | Pending | Required for G7 |
| Instagram decision | Deferred in v1 | Goal guardrail | Pending | Required confirmation |
| DashThis status during proof | Active | Goal guardrail | Pending | Required confirmation |

Machine-readable intake template:

`docs/project/evidence/dashthis-replacement/2026-06-16-g1-runtime-target-intake.template.json`

Validate the filled JSON intake before G2-G11 evidence capture:

```bash
python3 scripts/validate_slb_g1_runtime_target_intake.py \
  --intake-file <filled-g1-runtime-target-intake.json>
```

The checked-in template is intentionally invalid until an operator replaces the pending values,
records G0 clearance, confirms DashThis remains active, keeps delivery dry-run only, and attaches
the redacted `slb_report_target_intake` output path.

Local demo bridge:

`docs/project/evidence/dashthis-replacement/2026-06-17-local-demo-to-fixed-target-bridge.md`

Use the bridge to separate the current local browser proof from the approved G1 evidence target.
Do not reuse local-demo preview/export artifacts for G2-G12 unless the operator and Raj/Mira choose
that exact runtime/report/date range as the fixed evidence target.

Validator preflight packet:

`docs/project/evidence/dashthis-replacement/preflight/2026-06-16-slb-g1-runtime-intake-validator/`

## Minimum Validation Before G2-G11

Run or capture the following after the fields above are filled. Store only summarized/redacted
outputs in evidence docs.

| Check | Required result | Evidence destination |
| --- | --- | --- |
| Generate redacted report target intake | `slb_target_intake.v1` shows `candidate_ready_for_operator_confirmation`, `report.v1`, expected SLB template, required datasets/pages present, Instagram deferred, and no sensitive values in output | This checklist and G1 packet |
| Validate filled G1 intake JSON | `validate_slb_g1_runtime_target_intake.py` returns valid with zero errors | This checklist and G1 packet |
| Confirm report exists and belongs to the expected tenant/client | Report ID, safe tenant/client label, `template_key`, and `report.v1` match this checklist | This checklist and G1 packet |
| Confirm report preview route is reachable | Preview returns report metadata, ordered pages, coverage summary, and no live-provider-call evidence | G2/G3 and G4/G5 packets |
| Confirm diagnostics route is reachable | Diagnostics returns dataset statuses, retained range, row counts, source labels, and no secrets/user-level rows | G2/G3 and G7/G8 packets |
| Confirm parity command can run for the fixed range | Command emits aggregate-only SLB rows for paid, organic Page, top posts, and Content Ops | G6 packet |
| Confirm export route can queue CSV/PDF/PNG | Export preflight stores coverage metadata/report snapshot or blocks clearly | G4/G5 packet |
| Confirm scheduled dry-run route can execute | Dry-run metadata records no client email sent | G7/G8 packet |
| Confirm G0 route | Raj/Mira either approve proceeding or explicitly allow evidence capture while scope review remains open | G0 packet and goal doc |

## First Evidence Commands

Use the exact values from this checklist.

```bash
backend/.venv/bin/python backend/manage.py slb_report_target_intake \
  --report-id <slb-report-id>
```

```bash
backend/.venv/bin/python backend/manage.py slb_report_parity_evidence \
  --report-id <slb-report-id> \
  --start-date <YYYY-MM-DD> \
  --end-date <YYYY-MM-DD> \
  --format markdown
```

Capture API evidence from the same runtime target:

```text
POST /api/reports/<report-id>/preview/
GET /api/reports/<report-id>/diagnostics/
POST /api/reports/<report-id>/exports/ for csv, pdf, png
POST /api/reports/<report-id>/scheduled-dry-run/
GET /api/reports/<report-id>/exports/
GET /api/exports/<job-id>/download/
```

Run gates for any code state used as cancellation-review evidence:

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

## G1 Pass Criteria

G1 can move to `passed` only when:

- Every required operator field above is filled.
- The filled machine-readable G1 intake JSON validates with zero errors.
- `slb_report_target_intake` confirms the target report is a valid SLB `report.v1` candidate and
  emits only redacted/safe summary fields.
- The selected report is confirmed as `report.v1` with the expected SLB template key.
- The primary date range is confirmed and used consistently.
- Paid Meta, organic Facebook Page, and Content Ops scopes are recorded in redacted form.
- DashThis/source comparison ownership and evidence location are recorded.
- Scheduled delivery is explicitly dry-run only.
- Instagram is explicitly deferred.
- DashThis remains active.
- Raj/Mira clear G0 or explicitly allow fixed-range evidence capture to proceed while G0 remains
  under review.

## Handoff

After this checklist is completed:

1. Update `2026-06-16-g1-fixed-slb-proof-target.md`.
2. Update `2026-06-16-g0-g1-review-target-intake.md`.
3. Update `2026-06-16-slb-cancellation-readiness-goals.md`.
4. Update `2026-06-16-slb-reporting-render-export-parity-evidence.md`.
5. Start G2/G3 coverage and retained-history evidence using only the confirmed values.
