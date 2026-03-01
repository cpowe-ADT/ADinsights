# External Access Audit Evidence

- Operator: Codex
- Date/Time (America/Jamaica): 2026-02-06 00:30:33 EST
- Environment: Local laptop (`/Users/thristannewman/ADinsights`)

## Purpose

Execute every external closeout step that is technically possible from this machine and record what is blocked by missing access/credentials.

## Executed checks

1. Tooling/Runtime availability

- `jq`, `docker`, `python3` available.
- AWS CLI not available in PATH.

2. AWS access probes (via `boto3`)

- STS probe: failed (`Unable to locate credentials`).
- SES API probe (`sesv2.get_account`): failed (`Unable to locate credentials`).
- KMS API probe (`kms.list_aliases`): failed (`Unable to locate credentials`).

3. KMS smoke checks

- Local KMS smoke: `DJANGO_SETTINGS_MODULE=config.settings.test python3 scripts/rotate_deks.py --smoke` -> passed.
- AWS KMS smoke: `DJANGO_SETTINGS_MODULE=core.settings ... KMS_PROVIDER=aws ... python3 scripts/rotate_deks.py --smoke` -> failed (`AWS credentials are not configured`).

4. Airbyte readiness scripts

- `verify_production_readiness.py` (with parsed env file): ran and correctly detected placeholder credentials for Meta/Google.
- `airbyte_health_check.py` (with parsed env file): failed (`Unable to reach Airbyte API at http://localhost:8001: [Errno 61] Connection refused`).
- `validate_tenant_config.py` (with parsed env file): failed because Airbyte API is unreachable.

5. Airbyte local service startup attempt

- `cd infrastructure/airbyte && docker compose up -d db temporal server`
- Result: failed (`error from registry: denied`) while pulling images.

## What was completed vs blocked

### Completed locally

- Repo-side observability/documentation prerequisites remain green.
- Local KMS smoke path validated.
- External readiness scripts executed and produced deterministic blockers.

### Blocked externally

1. AWS credentials/profile unavailable on this machine (blocks SES/KMS account operations).
2. Airbyte service images unavailable from registry in current Docker context.
3. Production connector credentials are placeholders in local env.

## Immediate operator actions

1. Configure AWS credentials/profile on this machine (or run in CI runner with IAM role).
2. Resolve Docker registry access for Airbyte images.
3. Replace placeholder Meta/Google values in secure target env.
4. Re-run:
   - `python3 infrastructure/airbyte/scripts/verify_production_readiness.py`
   - `python3 infrastructure/airbyte/scripts/airbyte_health_check.py`
   - `python3 infrastructure/airbyte/scripts/validate_tenant_config.py`
5. Execute SES/KMS AWS actions from `docs/runbooks/external-actions-aws.md`.

External production actions must be tracked in `docs/runbooks/external-actions-aws.md`.
