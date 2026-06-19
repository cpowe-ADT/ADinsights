# SLB Cancellation-Readiness Example Artifacts

These files are examples only. They are not runtime evidence and must not be used to mark G0, G1,
or any downstream sub-goal as passed.

## Files

- `g0-raj-mira-review-decision.valid-example.json`
- `g1-runtime-target-intake.valid-example.json`
- `slb-report-target-intake-output.redacted-example.json`

They show the expected shape of a Raj/Mira G0 decision and a G1 runtime target intake when evidence
capture is allowed with followups. The G1 example references the redacted target-intake output
example so the validator can prove the report ID, dates, template, datasets, pages, source-scope
presence, and guardrails agree. Before using them for real work, copy them to a non-example evidence
path and replace every example runtime value with approved, safe, redacted values.

## Validate Examples

```bash
python3 scripts/validate_slb_g0_raj_mira_review.py \
  --review-file docs/project/evidence/dashthis-replacement/examples/g0-raj-mira-review-decision.valid-example.json
```

```bash
python3 scripts/validate_slb_g1_runtime_target_intake.py \
  --intake-file docs/project/evidence/dashthis-replacement/examples/g1-runtime-target-intake.valid-example.json
```

```bash
python3 scripts/validate_slb_g0_g1_handoff.py \
  --g0-review-file docs/project/evidence/dashthis-replacement/examples/g0-raj-mira-review-decision.valid-example.json \
  --g1-intake-file docs/project/evidence/dashthis-replacement/examples/g1-runtime-target-intake.valid-example.json
```

All three example validations should pass. Passing examples only proves the schema and handoff
rules are understandable; it does not prove the SLB runtime target exists or that DashThis can be
cancelled.

DashThis remains active and cancellation remains no-go until G0-G11 pass and G12 recommends
cancellation.
