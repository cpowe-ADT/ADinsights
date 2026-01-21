# Cold Start Walkthrough (Actual Attempt) (v0.1)

Purpose: real, command-by-command onboarding attempt using only docs.

## Steps Taken
1) Read `AGENTS.md` for guardrails.
2) Opened `docs/ops/doc-index.md` and followed the recontext order.
3) Opened:
   - `docs/workstreams.md`
   - `docs/project/feature-catalog.md`
   - `docs/project/phase1-execution-backlog.md`
   - `docs/task_breakdown.md`
   - `docs/project/vertical_slice_plan.md`

## Attempted to run locally
Command:
```bash
scripts/dev-launch.sh --foreground
```
Result:
```
Docker daemon is not running. Start Docker Desktop first.
```

Then tried health check:
```bash
scripts/dev-healthcheck.sh
```
Result:
```
curl: (7) Failed to connect to localhost port 8000...
Waiting for services (attempt 1/5)...
```

## Confusions / Friction Points
- The Golden Path does not mention “Start Docker Desktop” before `scripts/dev-launch.sh`.
- `scripts/dev-healthcheck.sh` loops when services aren’t running; needs a clearer “Docker not running” hint.

## Suggested Doc Fixes
- Add “Ensure Docker Desktop is running” to `docs/ops/golden-path-onboarding.md`.
- Add a short note in `docs/ops/golden-path-onboarding.md` that healthcheck expects backend running.

## Status
Local run blocked due to Docker not running. No code changes required.

## Attempt 2
Command:
```bash
scripts/dev-launch.sh --foreground
```
Result:
```
Docker daemon is not running. Start Docker Desktop first.
```

Then tried health check:
```bash
scripts/dev-healthcheck.sh
```
Result:
```
curl: (7) Failed to connect to localhost port 8000...
Waiting for services (attempt 1/5)...
```

## Status (Attempt 2)
Still blocked by Docker Desktop not running.

## Attempt 3
Command:
```bash
for i in {1..12}; do if docker info >/dev/null 2>&1; then echo "docker ready"; exit 0; else echo "waiting for docker ($i/12)"; sleep 5; fi; done; exit 1
```
Result:
```
waiting for docker (1/12)
...
waiting for docker (12/12)
```

## Status (Attempt 3)
Docker Desktop processes exist, but Docker daemon did not become ready within ~60s.

## Attempt 4 (Docker ready)
Steps:
1) Start Docker Desktop.
2) Run `scripts/dev-launch.sh --foreground`.

Result:
- `scripts/dev-launch.sh` pulled images and began building, but timed out in this session.
- Health check failed because frontend wasn’t running.

Manual recovery:
```bash
docker compose -f docker-compose.dev.yml up -d backend
docker compose -f docker-compose.dev.yml up -d frontend
scripts/dev-healthcheck.sh
```
Result:
```
Health check passed (backend + frontend reachable).
```

## Friction Notes
- `scripts/dev-launch.sh --foreground` can take >20s on first run (image pulls/builds). The cold start guide should mention longer waits.
- Healthcheck expects frontend to be running; backend-only is not enough.

## Attempt 5 (Service checks)
Commands:
```bash
curl -sSf http://localhost:8000/api/health/
curl -sSf http://localhost:8000/api/health/airbyte/
curl -sSf http://localhost:8000/api/health/dbt/
curl -sSf http://localhost:8000/api/timezone/
curl -sSf http://localhost:5173/ | head -n 5
```

Results:
- `/api/health/` ✅
- `/api/timezone/` ✅
- `/api/health/airbyte/` ❌ (503)
- `/api/health/dbt/` ❌ (503)
- Frontend dev server ✅ (HTML returned)

## Friction Notes (Attempt 5)
- Airbyte/dbt health endpoints return 503 when those services are not running.
- Docs should mention that these health checks depend on the Airbyte/dbt stacks.

## Attempt 6 (Airbyte stack)
Commands:
```bash
docker compose -f infrastructure/airbyte/docker-compose.yml up -d
```
Result:
- `.env` file missing for Airbyte stack.
- After copying `env.example` to `.env`, compose failed because image tag `airbyte/airbyte-webapp:0.50.22` was not found.

Commands used:
```bash
cp infrastructure/airbyte/env.example infrastructure/airbyte/.env
docker compose -f infrastructure/airbyte/docker-compose.yml up -d
```

## Friction Notes (Attempt 6)
- Airbyte stack requires a local `.env` file; this needs to be explicit in the golden path.
- Airbyte image tag mismatch blocks startup; doc should note how to resolve or which tags are valid.

## Attempt 7 (Airbyte tag update)
Change applied:
- Updated Airbyte images to `ghcr.io/airbytehq/*:v1.8.0` in `infrastructure/airbyte/docker-compose.yml`.

Follow-up required before retrying:
- Authenticate to GHCR with a token that has `read:packages`:
  ```bash
  docker login ghcr.io
  ```

Open items:
- Re-run `docker compose -f infrastructure/airbyte/docker-compose.yml up -d` and capture whether the GHCR pulls succeed.
