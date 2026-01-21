#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

usage() {
  cat <<'USAGE'
Usage: scripts/dev-launch.sh [options]

Options:
  --foreground        Run docker compose in the foreground (default: detached)
  --no-update         Skip git auto-update
  --no-pull           Skip pulling base images (postgres/redis)
  --no-open           Do not open the frontend URL in a browser
  --no-healthcheck    Skip health checks after startup
  -h, --help          Show this help message

Environment overrides:
  DEV_AUTO_UPDATE=0
  DEV_PULL_IMAGES=0
  DEV_OPEN_BROWSER=0
  DEV_RUN_HEALTHCHECK=0
  DEV_DETACH=0
  DEV_POSTGRES_PORT=5432
  DEV_REDIS_PORT=6379
  DEV_BACKEND_PORT=8000
  DEV_FRONTEND_PORT=5173
USAGE
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker-compose.dev.yml"

DETACH="${DEV_DETACH:-1}"
AUTO_UPDATE="${DEV_AUTO_UPDATE:-1}"
PULL_IMAGES="${DEV_PULL_IMAGES:-1}"
OPEN_BROWSER="${DEV_OPEN_BROWSER:-1}"
RUN_HEALTHCHECK="${DEV_RUN_HEALTHCHECK:-1}"
POSTGRES_PORT="${DEV_POSTGRES_PORT:-5432}"
REDIS_PORT="${DEV_REDIS_PORT:-6379}"
BACKEND_PORT="${DEV_BACKEND_PORT:-8000}"
FRONTEND_PORT="${DEV_FRONTEND_PORT:-5173}"

port_in_use() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
  elif command -v nc >/dev/null 2>&1; then
    nc -z localhost "$port" >/dev/null 2>&1
  else
    return 1
  fi
}

find_free_port() {
  local port="$1"
  local tries=0
  while (( tries < 10 )); do
    if ! port_in_use "$port"; then
      echo "$port"
      return 0
    fi
    port=$((port + 1))
    tries=$((tries + 1))
  done
  echo "$1"
  return 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --foreground)
      DETACH=0
      shift
      ;;
    --no-update)
      AUTO_UPDATE=0
      shift
      ;;
    --no-pull)
      PULL_IMAGES=0
      shift
      ;;
    --no-open)
      OPEN_BROWSER=0
      shift
      ;;
    --no-healthcheck)
      RUN_HEALTHCHECK=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Missing $COMPOSE_FILE. Did you pull the repo updates?"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker CLI not found. Install Docker Desktop first."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not running. Start Docker Desktop first."
  exit 1
fi

COMPOSE_CMD=()
if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "Docker Compose not found. Install the Compose plugin."
  exit 1
fi

if port_in_use "$POSTGRES_PORT"; then
  if [[ -z "${DEV_POSTGRES_PORT:-}" ]]; then
    POSTGRES_PORT="$(find_free_port "$POSTGRES_PORT")"
    echo "Port 5432 is in use; using $POSTGRES_PORT for Postgres."
  else
    echo "Port $POSTGRES_PORT is in use; DEV_POSTGRES_PORT is set so it will be used anyway."
  fi
fi

if port_in_use "$REDIS_PORT"; then
  if [[ -z "${DEV_REDIS_PORT:-}" ]]; then
    REDIS_PORT="$(find_free_port "$REDIS_PORT")"
    echo "Port 6379 is in use; using $REDIS_PORT for Redis."
  else
    echo "Port $REDIS_PORT is in use; DEV_REDIS_PORT is set so it will be used anyway."
  fi
fi

if port_in_use "$BACKEND_PORT"; then
  if [[ -z "${DEV_BACKEND_PORT:-}" ]]; then
    BACKEND_PORT="$(find_free_port "$BACKEND_PORT")"
    echo "Port 8000 is in use; using $BACKEND_PORT for the backend."
  else
    echo "Port $BACKEND_PORT is in use; DEV_BACKEND_PORT is set so it will be used anyway."
  fi
fi

if port_in_use "$FRONTEND_PORT"; then
  if [[ -z "${DEV_FRONTEND_PORT:-}" ]]; then
    FRONTEND_PORT="$(find_free_port "$FRONTEND_PORT")"
    echo "Port 5173 is in use; using $FRONTEND_PORT for the frontend."
  else
    echo "Port $FRONTEND_PORT is in use; DEV_FRONTEND_PORT is set so it will be used anyway."
  fi
fi

export POSTGRES_PORT REDIS_PORT BACKEND_PORT FRONTEND_PORT
export DEV_BACKEND_URL="http://localhost:${BACKEND_PORT}"
export DEV_FRONTEND_URL="http://localhost:${FRONTEND_PORT}"

if [[ "$AUTO_UPDATE" == "1" ]] && command -v git >/dev/null 2>&1; then
  if [[ -z "$(git -C "$REPO_ROOT" status --porcelain)" ]]; then
    if ! git -C "$REPO_ROOT" pull --ff-only; then
      echo "Auto-update failed; continuing with existing sources."
    fi
  else
    echo "Local changes detected; skipping git pull."
  fi
fi

if [[ "$PULL_IMAGES" == "1" ]]; then
  if ! "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" pull postgres redis; then
    echo "Image pull failed or skipped; continuing."
  fi
fi

if [[ "$DETACH" == "1" ]]; then
  "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" up -d --build

  if [[ "$RUN_HEALTHCHECK" == "1" ]]; then
    if ! "$SCRIPT_DIR/dev-healthcheck.sh"; then
      echo "Health check failed. Try: ${COMPOSE_CMD[*]} -f docker-compose.dev.yml logs -f"
      exit 1
    fi
  fi

  if [[ "$OPEN_BROWSER" == "1" ]] && command -v open >/dev/null 2>&1; then
    open "http://localhost:${FRONTEND_PORT}"
  fi

  echo "Login: devadmin@local.test / devadmin1"
  echo "Stack is running. Stop it with: ${COMPOSE_CMD[*]} -f docker-compose.dev.yml down"
else
  "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" up --build
fi
