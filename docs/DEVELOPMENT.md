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

## Ports

The launcher auto-picks free ports if defaults are taken.
Check the active mappings with:

```bash
docker compose -f docker-compose.dev.yml ps
```

Default ports:
- Postgres: 5432
- Redis: 6379
- Backend: 8000
- Frontend: 5173

Override ports:

```bash
DEV_BACKEND_PORT=8005 DEV_FRONTEND_PORT=5175 scripts/dev-launch.sh
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
- If ports are busy, the launcher selects new ones and prints them.
