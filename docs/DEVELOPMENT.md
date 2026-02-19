# ADinsights Development

## Quick Start (one click)

1. Ensure Docker Desktop is running.
2. Click the Dock icon "ADinsights Dev" (or double-click `~/Desktop/ADinsights Dev.command`).
3. The launcher auto-updates (when the repo is clean), starts the stack, and opens the frontend.

## Quick Start (terminal)

```bash
scripts/dev-launch.sh
```

Run in the foreground (single terminal, logs streaming):

```bash
scripts/dev-launch.sh --foreground
```

## Launcher Profiles (4 options)

Use fixed profile matrices so you can run multiple local stacks without manually picking ports.

| Profile | Postgres | Redis | Backend | Frontend |
| --- | ---: | ---: | ---: | ---: |
| `profile-1` (default) | 5432 | 6379 | 8000 | 5173 |
| `profile-2` | 5433 | 6380 | 8001 | 5174 |
| `profile-3` | 5434 | 6381 | 8002 | 5175 |
| `profile-4` (high-range) | 15432 | 16379 | 18000 | 15173 |

Show available profiles:

```bash
scripts/dev-launch.sh --list-profiles
```

Select a profile explicitly:

```bash
scripts/dev-launch.sh --profile 2
```

Non-interactive selection (useful for scripts):

```bash
scripts/dev-launch.sh --profile 3 --non-interactive
```

### Selection precedence

The launcher resolves ports in this order:

1. Explicit port env vars (`DEV_POSTGRES_PORT`, `DEV_REDIS_PORT`, `DEV_BACKEND_PORT`, `DEV_FRONTEND_PORT`)
2. `--profile <1|2|3|4>`
3. `DEV_PORT_PROFILE=<1|2|3|4>`
4. Interactive profile prompt (TTY only)
5. `profile-1` default

## Port-conflict backup behavior

- The selected profile is validated as a full bundle.
- If any non-explicit profile port is busy, launcher falls back cyclically to the next profiles.
  - Example: profile-2 fallback order is `3 -> 4 -> 1`.
- If all four profiles are busy, launcher falls back to per-port incremental search.
- Use strict mode to fail instead of fallback:

```bash
scripts/dev-launch.sh --profile 1 --strict-profile
```

## Active runtime state file

Each launcher run writes resolved ports/URLs to:

```bash
.dev-launch.active.env
```

Inspect the active mappings:

```bash
cat .dev-launch.active.env
```

This file includes:
- `DEV_ACTIVE_PROFILE`
- `POSTGRES_PORT`, `REDIS_PORT`, `BACKEND_PORT`, `FRONTEND_PORT`
- `DEV_BACKEND_URL`, `DEV_FRONTEND_URL`
- generation timestamp

`dev-healthcheck.sh` now auto-loads this file when explicit `DEV_BACKEND_URL` / `DEV_FRONTEND_URL` are not provided.

## Where to set up + how to check

Launcher path:

```bash
scripts/dev-launch.sh
```

By default, launcher now does two post-start safety checks:
- Ensures a dev admin user exists (`seed_dev_data --skip-fixture`).
- Verifies `/api/adapters/` includes a demo-capable adapter (`demo` or `fake`).

If demo verification fails, launcher exits with an actionable error instead of silently starting in a broken state.
You can skip these checks when needed:

```bash
scripts/dev-launch.sh --no-seed --no-demo-check
```

Health check:

```bash
scripts/dev-healthcheck.sh
```

Check active compose mappings:

```bash
docker compose -f docker-compose.dev.yml ps
```

Check common launcher ports in use:

```bash
lsof -nP -iTCP -sTCP:LISTEN | rg ':(5173|5174|5175|15173|8000|8001|8002|18000|5432|5433|5434|15432|6379|6380|6381|16379)'
```

## Manual run parity (without launcher)

Use matching profile pairs when you run services manually.

Backend:

```bash
cd backend
python manage.py runserver 0.0.0.0:<backend_port>
```

Frontend:

```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port <frontend_port>
```

## Login

Use these dev credentials (auto-created on startup):
- Email: `devadmin@local.test`
- Password: `devadmin1`

If you need to recreate the admin user:

```bash
make dev-seed
```

## Stop / Reset

Stop services:

```bash
docker compose -f docker-compose.dev.yml down
```

Reset everything (including volumes):

```bash
make dev-reset
```

## Mock Mode

If the API is unavailable, you can force mock data in the frontend:

```bash
# frontend/.env
VITE_MOCK_MODE=true
VITE_MOCK_ASSETS=true
```

## Troubleshooting

- Check health:
  ```bash
  scripts/dev-healthcheck.sh
  ```
- View logs:
  ```bash
  make dev-logs
  ```
- If ports are busy, the launcher prints the selected fallback profile/ports and writes `.dev-launch.active.env`.
