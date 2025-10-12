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
