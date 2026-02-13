# Backend Service

Django + Django REST Framework provides the tenant-aware API, credential vault, and Celery task
runners for the stack.

## Framework Decision

Django is the canonical backend for ADinsights. The earlier FastAPI prototype has been removed so
all tooling, docs, and deployment assets reference the Django stack exclusively. Use the commands
below for local development or containerized workflows.

## Requirements

- Python 3.11+
- PostgreSQL 14+ (or SQLite for smoke tests)
- Redis (for Celery broker/result backend)

## Setup

1. Create and activate a virtual environment.
2. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the sample environment file and tweak values as needed:
   ```bash
   cp .env.sample .env
   ```
4. Apply migrations and create a superuser:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```
5. (Optional) Auto-provision a local admin

   Add this to your `.env` to auto-create a default admin on startup:

   ```env
   ALLOW_DEFAULT_ADMIN=1
   DJANGO_DEFAULT_ADMIN_USERNAME=admin
   DJANGO_DEFAULT_ADMIN_EMAIL=admin@example.com
   DJANGO_DEFAULT_ADMIN_PASSWORD=admin1
   ```

6. Run the development server:

```bash
python manage.py runserver 0.0.0.0:8000
```

## KMS Configuration

In local development the service defaults to an in-process KMS provider (`KMS_PROVIDER=local`).
Keys are kept in memory and reset between test runs so you do not need real AWS credentials.

For staging/production environments, set `KMS_PROVIDER=aws` and supply a Key Management Service
customer managed key (CMK). Provision the key and expose its ARN to the backend via environment
variables:

1. Create the key and alias:
   ```bash
   aws kms create-key --description "ADinsights application key"
   aws kms create-alias --alias-name alias/adinsights/app --target-key-id <key-id>
   ```
2. Grant the IAM principal used by the backend the `kms:Encrypt`, `kms:Decrypt`, and
   `kms:ReEncrypt*` permissions on the key.
3. Configure the service with the key identifier and region:
   ```bash
   export KMS_KEY_ID=alias/adinsights-prod
   export AWS_REGION=us-east-1
   ```
4. When running outside AWS or without an instance profile, also export `AWS_ACCESS_KEY_ID`,
   `AWS_SECRET_ACCESS_KEY`, and optionally `AWS_SESSION_TOKEN`.

The `.env.sample` file lists these variables. Leaving the credential values blank allows the
default AWS credential provider chain (instance profiles, `~/.aws/credentials`, etc.) to supply
them.

At startup the backend validates the configured KMS key identifier; placeholder ARNs or region
mismatches raise a configuration error to prevent accidental non-production usage.

## CORS & Rate Limiting

API edge controls are configured via environment variables:

- `CORS_ALLOWED_ORIGINS` (comma-separated explicit origins)
- `CORS_ALLOW_ALL_ORIGINS` (keep `0` in production)
- `CORS_ALLOWED_METHODS`, `CORS_ALLOWED_HEADERS`, `CORS_ALLOW_CREDENTIALS`
- `DRF_THROTTLE_AUTH_BURST`, `DRF_THROTTLE_AUTH_SUSTAINED`, `DRF_THROTTLE_PUBLIC`

Rate limiting is enforced for unauthenticated/auth flows:

- `POST /api/token/`
- `POST /api/token/refresh/`
- `POST /api/auth/login/`
- `POST /api/auth/password-reset/`
- `POST /api/auth/password-reset/confirm/`
- `POST /api/tenants/`
- `POST /api/users/accept-invite/`

When thresholds are exceeded these endpoints return HTTP `429`.

## Meta (Facebook) Page Connect

The Data Sources page supports a Meta OAuth flow to connect Facebook pages without manually pasting
tokens. Configure:

- `META_APP_ID`
- `META_APP_SECRET`
- `META_OAUTH_REDIRECT_URI` (optional; defaults to `${FRONTEND_BASE_URL}/dashboards/data-sources`)
- `META_OAUTH_SCOPES` (comma-separated)
- `META_GRAPH_API_VERSION` (defaults to `v20.0`)

The backend exchanges the OAuth code server-side, caches selectable page tokens for a short window,
and persists only the selected page token as an encrypted tenant-scoped platform credential.

## Google Connector OAuth (Ads + GA4 + Search Console)

Google-family connectors use OAuth plus tenant-scoped credential storage. Configure:

- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REDIRECT_URI`
- `GOOGLE_OAUTH_SCOPES_GOOGLE_ADS`
- `GOOGLE_OAUTH_SCOPES_GA4`
- `GOOGLE_OAUTH_SCOPES_SEARCH_CONSOLE`

Optional Airbyte defaults for auto-provisioning from the Data Sources UI:

- `AIRBYTE_DEFAULT_WORKSPACE_ID`
- `AIRBYTE_DEFAULT_DESTINATION_ID`
- `AIRBYTE_SOURCE_DEFINITION_GA4`
- `AIRBYTE_SOURCE_DEFINITION_SEARCH_CONSOLE`
- `AIRBYTE_GOOGLE_ADS_DEVELOPER_TOKEN`
- `AIRBYTE_GOOGLE_ADS_LOGIN_CUSTOMER_ID`

Connector lifecycle APIs:

- `POST /api/integrations/{provider}/oauth/start/`
- `POST /api/integrations/{provider}/oauth/callback/`
- `POST /api/integrations/{provider}/reconnect/`
- `POST /api/integrations/{provider}/disconnect/`
- `POST /api/integrations/{provider}/provision/`
- `POST /api/integrations/{provider}/sync/`
- `GET /api/integrations/{provider}/status/`
- `GET /api/integrations/{provider}/jobs/`

Supported provider slugs: `facebook_pages`, `meta_ads`, `google_ads`, `ga4`, `search_console`.

## Containers

Dockerfiles are provided for parity with the deploy stack.

```bash
# API
docker build -t adinsights-backend .
docker run --rm -p 8000:8000 --env-file .env adinsights-backend

# Celery beat scheduler
docker build -t adinsights-backend-scheduler -f Dockerfile.scheduler .
docker run --rm --env-file .env adinsights-backend-scheduler
```

Ensure Redis and PostgreSQL are reachable from the container environment before launching workers.

## Celery

Start workers once Redis is running:

```bash
celery -A core worker -l info
celery -A core beat -l info
```

Sample tasks live in `core/tasks.py` and can be invoked from the Django shell for testing.

Celery beat ships with a weekly `rotate_deks` schedule (Sundays at 01:30 Jamaica time) so tenant
data-encryption keys are re-wrapped via the configured KMS provider. Adjust `CELERY_BEAT_SCHEDULE`
if your operations cadence differs.

## Row-Level Security

After provisioning the database, enable Postgres row-level security policies:

```bash
python manage.py enable_rls
```

The command prints the SQL used to set policies on tenant-scoped tables.

## Dev Data Utilities

For local-only bootstrapping (guarded by `DEBUG=True` or `ALLOW_DEFAULT_ADMIN=1`):

```bash
python manage.py seed_dev_data
python manage.py ingest_sample_metrics --reset
```

The sample ingest command reads `backend/fixtures/sample_ingest.csv` by default.

## Testing & Linting

```bash
pytest
ruff check
```

Pytest spins up an in-memory settings module and validates JWT auth, credential encryption, and
management commands.

## Account & Tenant APIs

- `POST /api/tenants/` — create a tenant and bootstrap its first administrator. Returns the
  tenant payload and the admin's user ID so provisioning scripts can assign secrets or analytics
  workspaces.
- `GET /api/tenants/` — list the tenants visible to the authenticated caller. Non-superusers only
  ever see their current tenant to enforce strict scoping.
- `GET /api/users/` — list users within the caller's tenant. Responses include the role names that
  have been granted.
- `POST /api/users/` — create a user directly under the authenticated tenant (admin-only).
- `POST /api/tenants/{tenant_id}/invite/` — tenant-scoped invitation endpoint that enforces admin
  permissions before delegating to the same invitation flow. This path is preferred for
  integrations that already know the tenant identifier.
- `POST /api/users/invite/` — legacy path retained for backward compatibility. Requests accept an
  optional `role` (e.g., `ADMIN`, `ANALYST`, `VIEWER`) to pre-seed RBAC, but new clients should
  migrate to the tenant-scoped endpoint above.
- `POST /api/users/accept-invite/` — exchange an invitation token for a password and profile
  details. Successful acceptances mark the invite as redeemed and assign the requested role.
- `GET /api/user-roles/` — inspect RBAC assignments scoped to the caller's tenant.
- `POST /api/roles/assign/` — grant a role to a tenant user (admin-only) while emitting an
  audit log entry.
- `DELETE /api/user-roles/{id}/` — revoke a role assignment (admin-only).

Legacy health/authentication endpoints remain available for integrations:

- `POST /api/auth/login/` — retrieve JWT pair.
- `GET /api/me/` — return the authenticated user profile with tenant context.
- `GET /api/health/` — simple health probe.
- `GET /api/timezone/` — returns `America/Jamaica`, verifying configuration.

Hook these endpoints into the frontend or external tools once additional resources are exposed.

## SES Production Notes

For SES delivery, set:

- `EMAIL_PROVIDER=ses`
- `EMAIL_FROM_ADDRESS=<approved>@adtelligent.net`
- `SES_EXPECTED_FROM_DOMAIN=adtelligent.net`
- `SES_CONFIGURATION_SET=<optional-config-set>`

The backend skips SES sends when the from-address domain does not match
`SES_EXPECTED_FROM_DOMAIN`.
