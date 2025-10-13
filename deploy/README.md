# Deployment Guide

## Prerequisites

- Docker 26+
- docker compose plugin
- Access to GHCR (`ghcr.io/adinsights/*`)
- Superset admin credentials for metadata import

## Steps

1. Authenticate to the container registry:
   ```bash
   echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
   ```
2. Run the deployment script:
   ```bash
   ./deploy_full_stack.sh
   ```
3. Import Superset assets:
   ```bash
   docker exec -it deploy_superset_1 superset import-dashboards /app/superset_home/export/dashboards
   docker exec -it deploy_superset_1 superset import-datasources /app/superset_home/export/datasets
   docker exec -it deploy_superset_1 superset import-assets /app/superset_home/export/subscriptions
   ```
4. Validate health endpoints and review the operations runbook in `docs/runbooks/`.

## AWS KMS Requirements

The backend container requires access to an AWS KMS key to unwrap tenant data encryption keys. Make
sure the deployment environment provides:

- A symmetric CMK with the backend IAM role or user granted `kms:Encrypt`, `kms:Decrypt`, and
  `kms:ReEncrypt*` permissions.
- Environment variables for the stack:
  - `KMS_KEY_ID` — the key ARN or alias ARN.
  - `AWS_REGION` — region where the key lives.
  - Optional credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`) when no
    instance profile is available.

These variables can be injected via the compose overrides or infrastructure automation.
