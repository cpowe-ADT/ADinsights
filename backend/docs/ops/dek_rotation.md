# DEK Rotation Runbook

## Trigger
- Weekly scheduled DEK rotation fails.
- Secrets decryption errors or invalid key version mismatches.

## Triage
- Confirm `KMS_PROVIDER`, `KMS_KEY_ID`, and cloud credentials are configured.
- Check Celery beat logs for `rotate_deks` task failures.
- Inspect recent audit/log events for failed rotations.
- Run a KMS smoke check: `python scripts/rotate_deks.py --smoke`

## Recovery
- Run a manual rotation:
  - `python manage.py shell -c "from core.tasks import rotate_deks; print(rotate_deks())"`
- Rotate a single tenant DEK:
  - `python manage.py shell -c "from core.crypto.dek_manager import rotate_tenant_dek; print(rotate_tenant_dek('<tenant-id>'))"`
- Verify the tenant key and credentials have the new key version.

## Edge cases
- **KMS unreachable:** confirm VPC endpoints, NAT/egress, and AWS region alignment with the key ARN.
- **Rotation errors:** review audit logs for `dek_rotation_failed` entries and resolve per-tenant data issues.

## Staging verification checklist
- `KMS_PROVIDER=aws` and `KMS_KEY_ID` are set to a real key ARN/alias.
- `AWS_REGION` aligns with the key ARN (or the ARN is used to infer the region).
- `python scripts/rotate_deks.py --smoke` returns success.
- `python scripts/rotate_deks.py --dry-run` reports the expected tenant count.
- Audit logs show `dek_rotated` entries for staged rotations.

## Escalation
- Escalate if:
  - KMS access is denied or throttled.
  - Multiple tenants fail to rotate in a single run.
  - Decryption errors persist after rotation.
