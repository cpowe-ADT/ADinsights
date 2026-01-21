#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

BACKEND_URL="${DEV_BACKEND_URL:-http://localhost:8000}"
FRONTEND_URL="${DEV_FRONTEND_URL:-http://localhost:5173}"

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
