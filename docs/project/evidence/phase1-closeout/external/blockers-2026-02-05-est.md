# External Blockers

Timestamp: 2026-02-05 23:29 EST (America/Jamaica)
External production actions must be tracked in `docs/runbooks/external-actions-aws.md`.

## Still externally required

1. `S7-D` SES production sender closeout
- Domain identity verification
- DKIM verification
- SPF/DMARC alignment
- Sandbox exit
- Final approved from-address confirmation

2. `P1-X1` Production KMS provisioning
- Provision production key/alias
- Wire `KMS_PROVIDER`, `KMS_KEY_ID`, `AWS_REGION`
- Validate rotation in target environment

3. `P1-X2` Airbyte production credential readiness
- Load real Meta/Google credentials
- Run readiness scripts against live Airbyte API

4. `P1-X4` Observability alert simulation
- Validate sync failure/empty sync/stale health alerts in monitoring stack

5. `P1-X9` Staging rehearsal
- Full go/no-go rehearsal with release evidence bundle in staging
- Local dry run evidence captured at:
  - `docs/project/evidence/phase1-closeout/release/staging-rehearsal-2026-02-05-est.md`

## Completed locally (no longer blocked)

- `P1-X6` Secrets baseline refresh
  - Evidence: `docs/project/evidence/phase1-closeout/external/secrets-baseline-2026-02-05-est.md`
- External access execution audit
  - Evidence: `docs/project/evidence/phase1-closeout/external/external-access-audit-2026-02-06-est.md`
