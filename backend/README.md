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
