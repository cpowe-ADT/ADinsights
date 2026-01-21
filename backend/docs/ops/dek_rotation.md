# DEK Rotation Runbook

## Trigger
- Weekly scheduled DEK rotation fails.
- Secrets decryption errors or invalid key version mismatches.

## Triage
- Confirm `KMS_PROVIDER`, `KMS_KEY_ID`, and cloud credentials are configured.
- Check Celery beat logs for `rotate_deks` task failures.
- Inspect recent audit/log events for failed rotations.

## Recovery
- Run a manual rotation:
  - `python manage.py shell -c "from core.tasks import rotate_deks; print(rotate_deks())"`
- Rotate a single tenant DEK:
  - `python manage.py shell -c "from core.crypto.dek_manager import rotate_tenant_dek; print(rotate_tenant_dek('<tenant-id>'))"`
- Verify the tenant key and credentials have the new key version.

## Escalation
- Escalate if:
  - KMS access is denied or throttled.
  - Multiple tenants fail to rotate in a single run.
  - Decryption errors persist after rotation.
