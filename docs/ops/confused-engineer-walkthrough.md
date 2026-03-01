# Confused Engineer Walkthrough (v0.1)

Purpose: explain the codebase to a low-context, low-confidence engineer.
This is intentionally plain, redundant, and explicit.

## Step 0: Where am I?

- You are in the **ADinsights** repo.
- It is a multi-tenant analytics platform.
- If you are lost, open `AGENTS.md` and `docs/ops/doc-index.md`.

## Step 1: What runs this app?

- Backend API (Django): `backend/`
- Frontend UI (React): `frontend/`
- Data modeling (dbt): `dbt/`
- Ingestion (Airbyte): `infrastructure/airbyte/`

## Step 2: I can’t find the “main entry point”

That’s normal. There are multiple services.

- Backend entry: `backend/manage.py`
- Frontend entry: `frontend/src/main.tsx`
- dbt entry: `dbt/dbt_project.yml`
- Airbyte stack: `infrastructure/airbyte/docker-compose.yml`

## Step 3: “Where are the API endpoints?”

- URLs: `backend/core/urls.py`, `backend/analytics/urls.py`, `backend/health/views.py`
- Docs: `docs/project/api-contract-changelog.md`

## Step 4: “Where does the dashboard get data?”

Frontend fetches API data from:

- `frontend/src/lib/dataService.ts`
- Store logic: `frontend/src/state/useDashboardStore.ts`

If you are seeing mock data:

- `frontend/public/sample_*.json` are mock fixtures.
- Set `VITE_MOCK_MODE=false` to use live APIs.

## Step 5: “How do I run it?”

Use the dev launcher:

```bash
scripts/dev-launch.sh
```

Health check:

```bash
scripts/dev-healthcheck.sh
```

## Step 6: “I broke something, what tests do I run?”

Use the testing cheat sheet:
`docs/ops/testing-cheat-sheet.md`

## Step 7: “I need a task. Where do I look?”

Start with:

- `docs/project/feature-catalog.md`
- `docs/project/phase1-execution-backlog.md`

## Step 8: “I’m stuck.”

Check:

- `docs/ops/support-playbook.md`
- `docs/ops/escalation-rules.md`

## Most common silly mistakes

- Running backend tests from the wrong folder.
- Editing multiple top-level folders in one PR (not allowed).
- Forgetting to update runbooks after changes.
- Using mock data in production mode.

If that sounds like you, you are not alone. Just follow the doc index.
