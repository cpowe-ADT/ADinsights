# Backend Service

Django + Django REST Framework provides the tenant-aware API, credential vault, and Celery task
runners for the stack.

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

## Useful Endpoints
- `POST /api/auth/login/` — retrieve JWT pair.
- `GET /api/me/` — return the authenticated user profile with tenant context.
- `GET /api/health/` — simple health probe.
- `GET /api/timezone/` — returns `America/Jamaica`, verifying configuration.

Hook these endpoints into the frontend or external tools once additional resources are exposed.
