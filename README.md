# ADinsights

## Project Overview
ADinsights will be a self-hosted, multi-tenant marketing analytics platform for Jamaican agencies. It will ingest performance data from Meta, Google Ads, and optional LinkedIn/TikTok sources, normalize it with dbt, and deliver dashboards, grids, maps, alerts, and AI-generated summaries tailored to Jamaica's parishes.

## Repository Structure
- **backend/**: Django + DRF API with multi-tenant auth, Celery tasks, and encrypted credential storage.
- **infrastructure/airbyte/**: Docker Compose stack and redacted source templates for Airbyte.
- **dbt/**: dbt project with staging models, macros, and parish lookup seed.
- **frontend/**: React + Vite shell featuring TanStack Table and Leaflet choropleth with mock data.
- **docs/**: Planning artifacts including the roadmap breakdown.

## Implementation Roadmap

### Phase 0 – Foundations
1. **Repository & Documentation**
   - Establish coding standards, environment variables management, and secrets handling guidelines.
   - Document data protection compliance requirements (Jamaica Data Protection Act) and platform-specific terms of service.
2. **Infrastructure Planning**
   - Decide on target cloud (e.g., AWS) and baseline services (VPC, networking, storage, container orchestration).
   - Select database engine (PostgreSQL + PostGIS or cloud warehouse) and sizing assumptions.

### Phase 1 – Core Platform Setup (Sprint 1)
1. **Identity & Multi-Tenancy**
   - Scaffold backend service (Django) with database migrations.
   - Create Tenant, User, Role, PlatformCredential models with encryption for stored tokens.
   - Implement RBAC and tenant-scoped API authentication.
2. **Connector Bootstrapping**
   - Deploy Airbyte and configure Meta & Google Ads sources with incremental sync and geo breakdowns.
   - Define custom connector stubs for LinkedIn Ads and TikTok transparency (even if optional).
3. **Warehouse & dbt Skeleton**
   - Create staging models (stg_*), core fact/dim tables without SCD2, and geo lookup scaffolding.
   - Load Jamaica parish GeoJSON and seed initial mappings.
4. **Initial Analytics UX**
   - Stand up Metabase (or Superset) and publish a basic campaign dashboard.
   - Scaffold React frontend with TanStack Table and Leaflet map components wired to mocked data.

### Phase 2 – Data Modeling & Metrics (Sprint 2)
1. **SCD2 & Metrics Layer**
   - Extend dbt models for SCD2 on campaign/adset/ad dimensions and implement metrics dictionary/macros.
   - Materialize aggregated views for campaign, creative, and pacing use cases.
2. **Enhanced Visualizations**
   - Add creative analysis and budget pacing dashboards with cross-filters.
   - Implement parish choropleth interactions and deck.gl custom tooltips (if using Superset).
3. **Operational Automation**
   - Configure dashboard subscriptions (email/Slack), SQL alerts, and orchestrated dbt runs (dbt Cloud/Cron/Celery).
   - Implement hourly Airbyte syncs with rolling 30-day backfill; nightly dbt transformations.

### Phase 3 – Advanced Features (Sprint 3)
1. **AI Summaries & Integrations**
   - Integrate LLM provider for summary generation with guardrailed prompts.
   - Explore Canva SDK automation for templated report exports.
2. **Audit, Security & Compliance**
   - Implement audit logging (logins, data access, report generation) and retention policies.
   - Document OIC registration, data minimization, storage limitation, and cross-border transfer safeguards.
3. **Admin & Monitoring**
   - Build admin console for credential rotation, quota monitoring, and sync health status.
   - Add observability (metrics/logging/alerts) for connectors and transformations.

### Phase 4 – Polish & Launch
1. **User Acceptance Testing**
   - Run pilot with representative clients; collect feedback and iterate on geo mappings and dashboards.
2. **Performance & Hardening**
   - Optimize queries, cache heavy dashboards, and simplify GeoJSON for faster rendering.
   - Conduct penetration testing and fix findings.
3. **Documentation & Training**
   - Produce runbooks, onboarding guides, privacy notices, and SLA definitions.
   - Provide training sessions for analysts and admins.

## Next Steps Checklist
- [x] Choose backend framework and initialize service.
- [x] Provision infrastructure scaffolds for Airbyte, dbt, and frontend shell.
- [ ] Configure Airbyte connections with production credentials and schedule hourly metric syncs.
- [ ] Extend dbt models beyond staging to deliver fact tables, metrics dictionary, and parish mapping logic.
- [ ] Secure secrets management integration (e.g., AWS Secrets Manager or Vault) for runtime keys.
- [ ] Stand up Metabase/Superset dashboards connected to the API once metrics are available.
- [ ] Use [`docs/task_breakdown.md`](docs/task_breakdown.md) to track sprint assignments and validation.

## Quick Start (Local Dev)

Use the steps below to run each component independently or orchestrate a quick end-to-end smoke
test. The project assumes `America/Jamaica` as the canonical timezone (no daylight saving), so keep
`TIME_ZONE=America/Jamaica` in your environment unless a tenant explicitly requires otherwise.

### Backend API (Django + DRF)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.sample .env  # adjust credentials as needed
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```
- Sample endpoints: `GET /api/health/`, `GET /api/health/airbyte/`, `GET /api/health/dbt/`,
  `GET /api/timezone/`, `POST /api/auth/login/`, `GET /api/me/`.
- For multi-tenant RLS policies run `python manage.py enable_rls` after your database is provisioned.
- Start Celery workers with `celery -A core worker -l info` and `celery -A core beat -l info` (run each
  in a separate terminal) once Redis is running.

### Frontend Shell (React + Vite)
```bash
cd frontend
npm install
npm run dev
```
The dev server runs on <http://localhost:5173>. The shell consumes mock data from
`public/sample_metrics.json` until backend APIs are wired in. Set `VITE_MOCK_MODE=false`
in your Vite environment to force the frontend to load data from the `/api/metrics/`
endpoint instead of the bundled sample payload.

### Airbyte Connectors
```bash
cd infrastructure/airbyte
docker compose up -d
```
Navigate to <http://localhost:8000> to configure sources. Use the `.example` files in `sources/` as
templates and follow the README for recommended sync cadences. Secrets are injected at runtime via
environment variables—export the following before running declarative configuration or the
bootstrap command:

| Connector | Environment variables |
| --- | --- |
| Google Ads | `AIRBYTE_GOOGLE_ADS_DEVELOPER_TOKEN`, `AIRBYTE_GOOGLE_ADS_CLIENT_ID`, `AIRBYTE_GOOGLE_ADS_CLIENT_SECRET`, `AIRBYTE_GOOGLE_ADS_REFRESH_TOKEN`, `AIRBYTE_GOOGLE_ADS_CUSTOMER_ID`, `AIRBYTE_GOOGLE_ADS_LOGIN_CUSTOMER_ID` |
| Meta Ads | `AIRBYTE_META_ACCESS_TOKEN`, `AIRBYTE_META_ACCOUNT_ID` |
| LinkedIn Transparency (stub) | `AIRBYTE_LINKEDIN_CLIENT_ID`, `AIRBYTE_LINKEDIN_CLIENT_SECRET`, `AIRBYTE_LINKEDIN_REFRESH_TOKEN` |
| TikTok Transparency (stub) | `AIRBYTE_TIKTOK_TRANSPARENCY_TOKEN`, `AIRBYTE_TIKTOK_ADVERTISER_ID` |

For scheduler access configure `AIRBYTE_API_URL` plus either `AIRBYTE_API_TOKEN` or the
`AIRBYTE_USERNAME`/`AIRBYTE_PASSWORD` pair for the Airbyte deployment.

Use `python manage.py sync_airbyte` (optionally via Celery beat) to trigger due syncs based on the
`integrations_airbyteconnection` schedule metadata stored per tenant.

### dbt Transformations
```bash
make dbt-deps
make dbt-build
```
The Makefile wraps common workflows (dependencies, seeds, builds, tests, and freshness checks). Use `DBT` overrides to pass `--vars` such as `enable_linkedin` or `enable_tiktok` when you want to incorporate optional connectors.
Run only the staging models for quick validation with:

```bash
dbt run --project-dir dbt --profiles-dir ~/.dbt --select staging
```

### Quick Smoke Test
1. Start the backend API and create a tenant/user via Django admin.
2. Launch a Celery worker (`celery -A core worker -l info`) and beat scheduler (`celery -A core beat -l info`) to ensure background jobs register correctly.
3. Run the frontend dev server and confirm the grid and map render with mock data.
4. Hit `GET /api/health/`, `GET /api/health/airbyte/`, and `GET /api/health/dbt/` to verify status JSON and HTTP codes match expectations; use `GET /api/timezone/` to confirm the Jamaica timezone is reported.
5. (Optional) Trigger `celery -A core call core.tasks.sync_meta_example --args='["<tenant_uuid>"]'`
   (optionally add a second argument with the triggering user UUID) from another terminal to see
   asynchronous task logging.

## Operations & Health

Health checks live in [`backend/core/urls.py`](backend/core/urls.py) and
[`backend/core/views.py`](backend/core/views.py) and drive synthetic monitoring and deployment
readiness probes:

- `GET /api/health/` returns `{"status": "ok"}` with HTTP 200 for a simple liveness signal.
- `GET /api/health/airbyte/` inspects the most recent `TenantAirbyteSyncStatus` record. A 200
  response marks the connector as healthy, while HTTP 503 denotes a misconfigured API credential,
  no completed syncs, or a sync older than the one-hour freshness threshold. The payload includes the
  last job metadata to help differentiate "stale" (sync overdue) from "misconfigured" (credentials or
  scheduler missing).
- `GET /api/health/dbt/` reads `dbt/target/run_results.json`. HTTP 200 indicates the latest run is
  within 24 hours and all models succeeded. HTTP 503 highlights missing or stale run results, and HTTP
  502 flags failing models in the most recent execution.
- `GET /api/timezone/` exposes the configured timezone so operators can ensure Jamaica-based
  scheduling is intact.

The Airbyte health route treats the lack of a recent sync as unhealthy to catch stale data before it
hits dashboards. dbt health follows a similar freshness heuristic but also checks for failed models to
avoid publishing incomplete aggregates.

## Background Tasks

Celery is integrated with Django for asynchronous ingestion and transformation hand-offs. Consult the
official "First steps with Django" guide for task routing, worker monitoring, and retries before
introducing new job types: <https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html>.

## Frontend Notes

The TanStack Table grid uses the v8 APIs for sorting and filtering. When wiring real endpoints, rely on
`getSortedRowModel()` (and its companion utilities) to keep client-side interactions consistent with the
official recommendations: <https://tanstack.com/table/v8/docs/guide/sorting>. The current grid still
loads mock data from `public/sample_metrics.json`; swap in real API calls by replacing the fetch layer
in the table provider once backend list routes are ready.

## Maps

Leaflet renders the parish choropleth via GeoJSON layers with hover tooltips, a legend, and drill-through
links to analyst grids. Follow the reference choropleth pattern in the Leaflet documentation when
extending interactivity or styling: <https://leafletjs.com/examples/choropleth/>.

## dbt Modeling

SCD Type-2 history for campaign, ad set, and ad dimensions will be captured through dbt snapshots and
the accompanying merge macros in this repo. Review the official dbt snapshot documentation before
adding new slowly changing dimensions or altering snapshot strategies:
<https://docs.getdbt.com/docs/build/snapshots>.

## CI Overview

GitHub Actions runs on Python 3.11 and Node 20 to mirror local tooling. The workflow installs backend
dependencies, executes `ruff check backend`, runs `pytest`, installs and tests the frontend (`npm test`
and `npm run build`), and finishes by seeding and running staging models with dbt (`make dbt-deps`,
`make dbt-seed`, and `dbt run --select staging`). This keeps API, UI, and transformation checks aligned
on every push and pull request.

## Security & Secrets

Environment variables back local development secrets today. Production hardening will shift sensitive
credentials to AWS KMS and Secrets Manager once the infrastructure workstreams land, so design new
integrations with that provider path in mind.

## Testing Matrix
- **Backend:** `pytest`, `ruff check backend`
- **Frontend:** `npm install && npm run build`
- **dbt:** `dbt seed`, `dbt run --select staging`
- **Infrastructure:** `docker compose ps` inside `infrastructure/airbyte/` to confirm containers are
  healthy.

Consider wiring these commands into CI once secrets management is settled.
