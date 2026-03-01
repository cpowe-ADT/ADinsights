#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ACTIVE_ENV_FILE="$REPO_ROOT/.dev-launch.active.env"

BACKEND_URL="${DEV_BACKEND_URL:-}"
FRONTEND_URL="${DEV_FRONTEND_URL:-}"

if [[ ( -z "$BACKEND_URL" || -z "$FRONTEND_URL" ) && -f "$ACTIVE_ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ACTIVE_ENV_FILE"
  if [[ -z "$BACKEND_URL" ]]; then
    BACKEND_URL="${DEV_BACKEND_URL:-}"
  fi
  if [[ -z "$FRONTEND_URL" ]]; then
    FRONTEND_URL="${DEV_FRONTEND_URL:-}"
  fi
fi

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:5173}"

if ! command -v curl >/dev/null 2>&1; then
  echo "curl not found. Install curl to run health checks."
  exit 1
fi

endpoints=(
  "$BACKEND_URL/api/health/"
  "$BACKEND_URL/api/timezone/"
)

attempt=1
delay=2

while (( attempt <= 5 )); do
  all_ok=1
  for url in "${endpoints[@]}"; do
    if ! curl -fsS "$url" >/dev/null; then
      all_ok=0
      break
    fi
  done

  if (( all_ok )); then
    if curl -fsS "$FRONTEND_URL" >/dev/null; then
      echo "Health check passed (backend + frontend reachable)."
      exit 0
    fi
    echo "Backend is up; waiting for frontend..."
    all_ok=0
  fi

  if (( attempt == 5 )); then
    echo "Health check failed after $attempt attempts."
    exit 1
  fi

  echo "Waiting for services (attempt $attempt/5)..."
  jitter=$((RANDOM % 2))
  sleep $((delay + jitter))
  delay=$((delay * 2))
  attempt=$((attempt + 1))
done
