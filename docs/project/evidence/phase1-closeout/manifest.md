# Phase 1 Evidence Manifest

## Required artifacts

External production actions must be tracked in `docs/runbooks/external-actions-aws.md`.

1. Backend

- [x] `ruff check backend && pytest -q backend`
- [x] CORS/throttle verification evidence (tests or smoke run output)
- Evidence: `docs/project/evidence/phase1-closeout/backend/validation-2026-02-05-est.md`

2. dbt

- [x] `dbt` dependency/install log
- [x] staging run output
- [x] snapshot output
- [x] marts run output
- [x] blocker notes if environment preconditions are missing
- Evidence: `docs/project/evidence/phase1-closeout/dbt/validation-2026-02-05-est.md`

3. Airbyte

- [x] `docker compose config` output
- [x] readiness script output (`validate_tenant_config.py`, `verify_production_readiness.py`, `airbyte_health_check.py`)
- [x] data contract check output (`python3 infrastructure/airbyte/scripts/check_data_contracts.py`)
- Evidence:
- `docs/project/evidence/phase1-closeout/airbyte/compose-validation-2026-02-05-est.md`
- `docs/project/evidence/phase1-closeout/airbyte/readiness-scripts-2026-02-05-est.md`
- `docs/project/evidence/phase1-closeout/airbyte/data-contract-validation-2026-02-06-est.md`

4. External prerequisites

- [ ] SES identity + DKIM/SPF/DMARC + sandbox-exit proof
- [ ] KMS key/alias provisioning proof
- [ ] production secret manager updates proof
- [ ] Meta authenticated field/scope validation proof
- [ ] Observability simulation proof (consecutive failures, empty sync, stale airbyte/dbt health)
- [ ] Staging rehearsal proof with rollback readiness
- Evidence templates:
- `docs/project/evidence/phase1-closeout/external/templates/ses-verification-template.md`
- `docs/project/evidence/phase1-closeout/external/templates/kms-provisioning-template.md`
- `docs/project/evidence/phase1-closeout/external/templates/airbyte-prod-readiness-template.md`
- `docs/project/evidence/phase1-closeout/external/templates/observability-simulation-template.md`
- `docs/project/evidence/phase1-closeout/external/templates/staging-rehearsal-template.md`
- Expected evidence files:
- `docs/project/evidence/phase1-closeout/external/ses-verification-<date>-est.md`
- `docs/project/evidence/phase1-closeout/external/kms-provisioning-<date>-est.md`
- `docs/project/evidence/phase1-closeout/external/airbyte-prod-readiness-<date>-est.md`
- `docs/project/evidence/phase1-closeout/external/observability-simulation-<date>-est.md`
- `docs/project/evidence/phase1-closeout/external/staging-rehearsal-<date>-est.md`
- Current blocker register: `docs/project/evidence/phase1-closeout/external/blockers-2026-02-05-est.md`
- External execution audit: `docs/project/evidence/phase1-closeout/external/external-access-audit-2026-02-06-est.md`
- [x] `P1-X6` secrets baseline refreshed and validated
- Evidence: `docs/project/evidence/phase1-closeout/external/secrets-baseline-2026-02-05-est.md`
- Evidence: `docs/project/evidence/phase1-closeout/external/meta-authenticated-validation-required-2026-02-06-est.md`

5. Release gate

- [x] merge order confirmation
- [x] local rehearsal sequence evidence
- [ ] Raj/Mira review references
- [x] current closure decision (`READY_PENDING_EXTERNALS`)
- Evidence: `docs/project/evidence/phase1-closeout/release/gate-status-2026-02-05-est.md`
- Evidence: `docs/project/evidence/phase1-closeout/release/staging-rehearsal-2026-02-05-est.md`
