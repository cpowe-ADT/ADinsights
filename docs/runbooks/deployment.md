# Deployment Runbook — ADinsights

Use this guide to promote ADinsights from development into a production-ready environment. It assumes AWS as the primary cloud provider and containerised workloads for the Django backend, Celery workers, Airbyte, and the React frontend. Adapt the specifics if you select an alternative cloud or orchestration platform.

## 1. Environments & Branch Flow

- **main**: integrates feature branches after review; always deployable to staging.
- **staging**: mirrors production infrastructure with synthetic data; runs integration, load, and security tests.
- **production**: customer-facing tenant workloads; no direct commits.

| Environment | Branch Source   | Deploy Target              | Data                       | Purpose                      |
| ----------- | --------------- | -------------------------- | -------------------------- | ---------------------------- |
| Dev         | feature/\*      | Local Docker/Vite          | Mock fixtures              | Individual developer testing |
| Staging     | main            | AWS `staging` ECS services | Masked or synthetic tenant | End-to-end validation, UAT   |
| Production  | tagged releases | AWS `prod` ECS services    | Live tenant data           | Customer traffic             |

Release cadence: weekly sprint cut for staging, bi-weekly (or on-demand) for production once staging verifies green.

## 2. Infrastructure Blueprint (AWS)

### 2.1 Networking & Security

- VPC with public (ALB/NAT) and private subnets (ECS, RDS, Redis).
- Security groups: allow ALB → ECS (HTTPS), ECS → RDS/Redis, ECS → Airbyte, VPC endpoints for Secrets Manager/KMS.
- IAM roles: execution roles per ECS task, read-only roles for dbt jobs, least-privileged policies for automation.

### 2.2 Core Services

- **ECS/Fargate**
  - `backend-service`: Django API + Gunicorn.
  - `celery-worker`: asynchronous tasks.
  - `celery-beat`: schedules `sync_*`, `rotate_deks`, alerts.
  - `frontend-service`: Vite build served via Nginx or S3 + CloudFront.
- **Airbyte**
  - Dedicated ECS/EC2 cluster (t3.large + EBS) with destination pointing to the analytics warehouse.
  - Configure connections via declarative configs in `infrastructure/airbyte/`.
- **Data Stores**
  - RDS PostgreSQL (PostGIS enabled), Multi-AZ, automated backups (7–14 days) + manual snapshots.
  - ElastiCache Redis (for Celery broker + caching).
  - S3 buckets for static assets, logs, dbt artifacts, and Airbyte staging.
- **Analytics Warehouse**
  - Option A: Same RDS instance (simpler, smaller tenants).
  - Option B: Dedicated warehouse (Snowflake, Redshift) if scale demands.

### 2.3 Observability & Ops

- CloudWatch Logs for ECS tasks; ship to centralized logging (e.g., Loki, DataDog).
- Prometheus-compatible metrics via `/metrics/app` endpoint (scrape using AWS Managed Prometheus or Prometheus on ECS).
- Alert destinations: Slack webhook + email (SES) for Airbyte/dbt failures, credential expiry, Celery retries.
- On-call rotation documented in `docs/runbooks/operations.md`.

## 3. Secrets & Configuration

- Store environment variables in AWS Secrets Manager or SSM Parameter Store.
- Wrap tenant DEKs using AWS KMS CMKs (`KMS_KEY_ID`).
- Inject secrets into ECS tasks using task definitions; never bake into docker images.
- Maintain `.env.sample` for reference only; update when adding new env vars.

## 4. Build & Release Pipeline

1. **CI (GitHub Actions)**
   - Lint + tests: `ruff check backend && pytest -q backend`, `npm test -- --run && npm run build`, `make dbt-build`.
   - Build docker images for backend, worker, frontend, Airbyte extensions.
   - Push to ECR with tags `main-<gitsha>` and `release-<semver>`.
2. **Artifact Promotion**
   - Create Git tag `vX.Y.Z` when staging passes UAT.
   - Trigger CD workflow: updates ECS task definitions, runs migrations (`python manage.py migrate`), seeds tenant roles (`manage.py seed_roles`), enables RLS (`manage.py enable_rls`).
3. **Smoke Tests**
   - Run `pytest -q backend --maxfail=1 --disable-warnings -k smoke` against production DB (read-only) via feature toggles.
   - Hit `/api/health/`, `/api/health/airbyte/`, `/api/health/dbt/`, `/api/timezone/`, `/metrics/app`.

## 5. Deployment Steps (Staging/Prod)

1. Confirm CI pipeline green for target commit.
2. Ensure dbt models and Airbyte connections are in desired state; run incremental sync on staging for validation.
3. Execute infrastructure changes via Terraform/CloudFormation (network, RDS, ECS updates).
4. Deploy ECS task revisions (backend, worker, beat, frontend).
5. Run database migrations (`python manage.py migrate`).
6. Warm caches: trigger `/api/dashboards/aggregate-snapshot/` for a sample tenant, run Celery job `sync_meta_metrics`.
7. Validate smoke tests + manual UI checks (login, dashboard load, Data Health view, credential management).
8. Announce release in change-log channel; update status page.

## 6. Rollback Strategy

- **App rollback**: redeploy previous ECS task definition revision; revert to prior docker image tag.
- **Database rollback**: prefer `manage.py migrate app <previous_migration>` only for reversible migrations; otherwise restore latest snapshot (document any data loss impact).
- **Airbyte/dbt rollback**: revert connection/config manifests in git, re-run dbt build with prior release tag.
- log rollback steps in incident log (`docs/runbooks/operations.md`).

## 7. Post-Deployment Checks

- Monitor CloudWatch/Prometheus dashboards for error spikes, latency, queue depth.
- Validate Airbyte sync telemetry recorded in `TenantAirbyteSyncStatus` and `AirbyteJobTelemetry`.
- Confirm dbt run results (`dbt/target/run_results.json`) updated within expected window.
- Review audit logs for credential activity; ensure no leaked secrets.
- Update `docs/ops/agent-activity-log.md` with summary of release.

## 8. Cost Monitoring

- Track monthly AWS bill segmented by service (RDS, ECS, Airbyte, Redis, CloudWatch).
- Implement budgets/alerts (AWS Budgets) with 80% and 100% thresholds.
- Right-size instances quarterly; scale down staging during off-hours.

## 9. Go-Live Checklist

- [ ] Combined metrics API (`/api/dashboards/aggregate-snapshot/`) returns fresh data for pilot tenant.
- [ ] Frontend pointing to production API with feature flags disabled.
- [ ] Airbyte connections for Meta & Google running hourly; alerts configured.
- [ ] dbt incremental builds scheduled (05:00 local) with success notifications.
- [ ] Credential rotation reminders active via Celery beat + notifications.
- [ ] Penetration test findings addressed; security review sign-off.
- [ ] Runbooks updated: operations, alerts, tenant onboarding/offboarding.
- [ ] SLA/SLO definitions published in `docs/ops/slo-sli.md` with active monitoring.

## 10. Reference Commands

- Local docker compose smoke: `docker compose up backend worker beat frontend` (use `.env.sample` overrides).
- Staging deployment trigger: `make deploy-staging` (wraps terraform plan/apply + ecs update).
- Prod deployment trigger: `make deploy-prod IMAGE_TAG=vX.Y.Z` (requires approval).
- Emergency credential rotation: `python manage.py rotate_deks` (ensure Celery beat disabled to avoid concurrent run).

Maintain this runbook as infrastructure evolves; update cost estimates, environment steps, and validation scripts each release cycle.
