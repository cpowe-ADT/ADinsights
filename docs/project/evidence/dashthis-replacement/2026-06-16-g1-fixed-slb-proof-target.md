# G1 Fixed SLB Proof Target Packet

Date: 2026-06-16
Timezone: America/Jamaica
Goal ID: G1
Status: recommended default prepared; blocked on operator/runtime confirmation.

## Decision Needed

Lock the first SLB DashThis cancellation-readiness proof target so every later evidence step uses
the same client, report, date range, sources, and delivery assumptions.

This packet does not clear G1 by itself. It defines the recommended default and lists the exact
values still required before G2/G3/G6 evidence can be treated as fixed-range proof.

## Recommended Default Proof Target

| Field                        | Recommended value                                       | Evidence basis                                                                                               | Status                                  |
| ---------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | --------------------------------------- |
| Client/proof target          | SLB / Students' Loan Bureau                             | Gmail inventory identifies SLB as the strongest first proof target.                                          | Operator confirmation pending           |
| Report family                | SLB monthly social/campaign status report               | Reviewed SLB PDFs show a recurring monthly campaign status report shape.                                     | Operator confirmation pending           |
| Template key                 | `slb_monthly_social_report`                             | Existing sprint scope and template endpoint target the SLB monthly report scaffold.                          | Runtime report confirmation pending     |
| Primary fixed proof range    | 2026-05-01 through 2026-05-31                           | Gmail attachment review found a complete May 2026 SLB monthly report.                                        | Operator confirmation pending           |
| Baseline/comparison range    | 2026-03-01 through 2026-04-30                           | Gmail attachment review found a March-April 2026 SLB report and recommends it for trend/baseline comparison. | Optional; operator confirmation pending |
| Active v1 datasets           | `paid_meta_ads`, `organic_facebook_page`, `content_ops` | Current v1 reporting goal excludes Instagram and uses stored aggregate ADinsights data only.                 | Coverage proof pending                  |
| Deferred dataset             | `organic_instagram`                                     | Instagram remains out of v1 until source rows, scopes, catalog entries, and reviewer approval are proven.    | Deferred                                |
| Render/export source         | Stored aggregate ADinsights data only                   | Reporting guardrail: no live provider calls at report preview/export time.                                   | Required                                |
| Delivery mode for proof      | Manual preview/export plus scheduled delivery dry-run   | DashThis cancellation bar requires export and dry-run delivery proof before real delivery claims.            | Runtime proof pending                   |
| Actual DashThis cancellation | No-go                                                   | G0-G11 evidence and G12 recommendation are not complete.                                                     | No-go                                   |

## Required Runtime Values To Close G1

Operator checklist:

`docs/project/evidence/dashthis-replacement/2026-06-16-g1-runtime-target-intake-checklist.md`

Record these values in the evidence packet before marking G1 `passed`:

| Required value                   | Why it matters                                                                                                                   | Status                                     |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| Target environment               | Prevents mixing local, staging, and production evidence.                                                                         | Pending                                    |
| Tenant/client identifier         | Required for tenant isolation and source scoping. Use safe/redacted identifiers in docs.                                         | Pending                                    |
| Created `ReportDefinition.id`    | Required for preview, export, diagnostics, dry-run, and parity commands.                                                         | Pending                                    |
| Confirmed `template_key`         | Proves the report uses the governed SLB template.                                                                                | Pending                                    |
| Date range                       | Must be fixed before coverage, parity, export, and hardening evidence can be compared.                                           | Recommended May 2026; pending confirmation |
| Account/page/source scope        | Required to prove the report is using the intended ad account/Page and not demo or wrong-tenant data.                            | Pending                                    |
| Recipient/delivery assumptions   | Required for scheduled dry-run and eventual delivery replacement evidence. Do not store private recipient lists unless redacted. | Pending                                    |
| DashThis/source comparison owner | Required because DashThis/source values are manually added to the parity worksheet in v1.                                        | Pending                                    |
| Instagram defer confirmation     | Prevents the v1 report from accidentally claiming full historical SLB parity.                                                    | Pending                                    |

## Target Intake Command

After a candidate `ReportDefinition.id` exists, generate a redacted target summary before starting
G2-G11:

```bash
backend/.venv/bin/python backend/manage.py slb_report_target_intake \
  --report-id <slb-report-id>
```

Also fill and validate the machine-readable runtime intake:

```bash
python3 scripts/validate_slb_g1_runtime_target_intake.py \
  --intake-file <filled-g1-runtime-target-intake.json>
```

Template:

`docs/project/evidence/dashthis-replacement/2026-06-16-g1-runtime-target-intake.template.json`

The command output must show:

- `schema_version == "slb_target_intake.v1"`.
- `status == "candidate_ready_for_operator_confirmation"`.
- `schema_version == "report.v1"` and `template_key == "slb_monthly_social_report"`.
- Required active datasets are present: `paid_meta_ads`, `organic_facebook_page`, and `content_ops`.
- Required SLB pages are present.
- `instagram_deferred == true`.
- No private recipient emails, provider tokens, raw provider payloads, or user-level identifiers are
  emitted.

This command does not close G1 by itself. It reduces operator error before the human-owned
environment, safe tenant/client, source scope, recipient assumptions, DashThis status, and Raj/Mira
clearance fields are filled.

## Acceptance Criteria To Mark G1 Passed

G1 can move from `blocked_external` to `passed` only when all of the following are true:

- Raj/Mira have cleared G0 or explicitly allowed fixed-range evidence capture to proceed while G0
  remains under architecture review.
- The operator confirms SLB as the first proof target.
- The operator confirms the primary date range, with May 2026 as the recommended default.
- A target environment and safe tenant/client identifier are recorded.
- A real SLB `ReportDefinition.id` and `template_key` are recorded.
- The filled G1 runtime target intake JSON validates with zero errors.
- The account/page/source scope is recorded in redacted form.
- Recipient and scheduled dry-run assumptions are recorded.
- Instagram remains explicitly deferred for v1.

## Next Sub-Goals After G1

Use the confirmed G1 values for every following packet:

1. G2 stored data coverage proof for `paid_meta_ads`, `organic_facebook_page`, and `content_ops`.
2. G3 monthly and 90-day retained-history proof for the same datasets.
3. G6 parity worksheet using the same report ID and fixed date range.
4. G4/G5 rendering and CSV/PDF/PNG export evidence for the same report snapshot.

If any later evidence uses a different report, tenant, account, Page, or date range, it does not
count toward this cancellation-readiness chain until G1 is updated.

## Source Evidence

- `docs/project/evidence/dashthis-replacement/2026-06-15-report-inventory-from-gmail.md`
- `docs/project/evidence/dashthis-replacement/2026-06-15-email-attachment-review.md`
- `docs/project/evidence/dashthis-replacement/2026-06-16-slb-cancellation-readiness-goals.md`
- `docs/project/evidence/dashthis-replacement/2026-06-16-slb-reporting-render-export-parity-evidence.md`
