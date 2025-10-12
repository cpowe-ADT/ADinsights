# ADinsights Backend

This FastAPI service exposes REST endpoints for dashboards, alert rules, and AI-generated insights. It also houses the SQL-driven alerting engine used by the schedulers.

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
```

Set environment variables in `.env` or via `ADINSIGHTS_` prefixed environment variables (for example `ADINSIGHTS_DATABASE_URL`).
This FastAPI backend provides multi-tenant onboarding, role-based access control (RBAC),
and OAuth integrations for advertising platforms such as Meta and Google Ads.

## Getting started

1. Install dependencies (using Poetry):

   ```bash
   cd backend
   poetry install
   ```

2. Configure environment variables in `.env` or export them in your shell:

   ```env
   DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/adinsights
   SECRET_KEY=super-secret-key
   META_CLIENT_ID=your-meta-client-id
   META_CLIENT_SECRET=your-meta-client-secret
   GOOGLE_ADS_CLIENT_ID=your-google-client-id
   GOOGLE_ADS_CLIENT_SECRET=your-google-client-secret
   OAUTH_REDIRECT_BASE_URL=https://your-domain.com
   ```

3. Run database migrations:

   ```bash
   alembic upgrade head
   ```

4. Launch the API:

   ```bash
   uvicorn app.main:app --reload
   ```

## Available endpoints

- `GET /health` – service health check
- `POST /rbac/tenants` – onboard a new tenant
- `POST /rbac/tenants/{tenant_id}/users` – add a user to a tenant and optionally assign a role
- `POST /rbac/roles` – create a reusable role
- `POST /rbac/users/{user_id}/role/{role_id}` – assign an existing role to a user
- `GET /oauth/{platform}/authorize` – start an OAuth flow for Meta or Google Ads
- `POST /oauth/{platform}/callback` – handle OAuth callbacks and persist encrypted refresh tokens

## Migrations

Alembic is configured in `backend/alembic.ini`. The first migration that creates the RBAC and credential tables lives in
`backend/migrations/versions/20240511_000001_initial.py`.
