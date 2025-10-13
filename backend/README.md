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
5. Run the development server:
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```

## AWS KMS Configuration

Data encryption keys (DEKs) are wrapped by AWS Key Management Service. Provision a symmetric
customer managed key (CMK) and expose its ARN to the backend via environment variables:

1. Create the key and alias:
   ```bash
   aws kms create-key --description "ADinsights application key"
   aws kms create-alias --alias-name alias/adinsights/app --target-key-id <key-id>
   ```
2. Grant the IAM principal used by the backend the `kms:Encrypt`, `kms:Decrypt`, and
   `kms:ReEncrypt*` permissions on the key.
3. Configure the service with the key identifier and region:
   ```bash
   export KMS_KEY_ID=arn:aws:kms:us-east-1:123456789012:key/abcd-1234
   export AWS_REGION=us-east-1
   ```
4. When running outside AWS or without an instance profile, also export `AWS_ACCESS_KEY_ID`,
   `AWS_SECRET_ACCESS_KEY`, and optionally `AWS_SESSION_TOKEN`.

The `.env.sample` file lists these variables. Leaving the credential values blank allows the
default AWS credential provider chain (instance profiles, `~/.aws/credentials`, etc.) to supply
them.

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

## Row-Level Security

After provisioning the database, enable Postgres row-level security policies:

```bash
python manage.py enable_rls
```

The command prints the SQL used to set policies on tenant-scoped tables.

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
