# Golden Path Onboarding (v0.1)

Purpose: the single best starting point for any engineer (human or AI).
This is the minimal set of steps that will work for most people.

## Step 1: Read these docs (in order)
1) `AGENTS.md`
2) `docs/ops/doc-index.md`
3) `docs/workstreams.md`
4) `docs/project/feature-catalog.md`
5) `docs/project/phase1-execution-backlog.md`

## Step 2: Run the system (local)
Ensure Docker Desktop is running first.

```bash
scripts/dev-launch.sh
```
Note: first run can take several minutes while images pull/build.

Check health:
```bash
scripts/dev-healthcheck.sh
```
Note: this assumes backend services are already running.

If you need Airbyte/dbt health to be green, start those stacks separately:
- Airbyte:
  1) `cp infrastructure/airbyte/env.example infrastructure/airbyte/.env`
  2) `docker login ghcr.io` (token needs `read:packages`)
  3) `cd infrastructure/airbyte && docker compose up -d`
- dbt: run the dbt commands in `docs/ops/testing-cheat-sheet.md`

If Airbyte image tags fail to pull, check `infrastructure/airbyte/README.md` for the pinned version (`v1.8.0`) and GHCR auth notes.

## Step 3: Find your task
- Pick from `docs/project/phase1-execution-backlog.md`.
- Stay within one top-level folder.
- If you need multiple folders, stop and escalate (Raj/Mira).

## Step 4: Run tests before finishing
Use the quick reference: `docs/ops/testing-cheat-sheet.md`.

## Step 5: Update docs if behavior changed
- `docs/project/api-contract-changelog.md`
- `docs/project/feature-catalog.md`
- Runbooks under `docs/runbooks/`

## Common mistakes (avoid)
- Editing multiple top-level folders in one PR.
- Forgetting to update runbooks.
- Shipping without running the canonical tests.

---

## Iterative feedback loop (3 personas + manager)

### Persona 1: Extra‑Silly Engineer (low context, easily lost)
**Feedback**: “I ran `npm test` from the repo root and it yelled at me. Where do I even start?”  
**Observed confusion**: Tried `npm test` at root, didn’t know frontend lives in `frontend/`.  
**Fix**: Explicitly say to `cd frontend` before running frontend tests (already in cheat sheet).

### Persona 2: Extra‑Professional Engineer (senior, precise)
**Feedback**: “I need to know the authoritative API route definitions and data contracts quickly.”  
**Observed confusion**: Looked in `backend/` but didn’t know which file defines URLs.  
**Fix**: Call out `backend/core/urls.py` and `backend/analytics/urls.py` as route sources, plus `docs/project/api-contract-changelog.md`.

### Persona 3: Extra‑Reasonable Engineer (mid-level, wants clarity)
**Feedback**: “I want to run the app once, verify health, and then pick a task without reading 10 docs.”  
**Observed confusion**: Didn’t know the fastest run path or where to find the backlog.  
**Fix**: Keep the 5-step order minimal and point directly to `scripts/dev-launch.sh` + `phase1-execution-backlog.md`.

### Manager Iteration (for all three)
**Revision summary**:
- Keep a strict 5-step path with explicit commands.
- Include exact route files and contract doc for API discovery.
- Emphasize “cd frontend” before UI tests to prevent common failure.

## Appendix: Key entry points
- Backend entry: `backend/manage.py`
- Frontend entry: `frontend/src/main.tsx`
- dbt entry: `dbt/dbt_project.yml`
- Airbyte stack: `infrastructure/airbyte/docker-compose.yml`
