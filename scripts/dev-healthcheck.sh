#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ACTIVE_ENV_FILE="$REPO_ROOT/.dev-launch.active.env"

BACKEND_URL="${DEV_BACKEND_URL:-}"
FRONTEND_URL="${DEV_FRONTEND_URL:-}"
AIRBYTE_DESTINATION_ID="${ADI_HEALTHCHECK_AIRBYTE_DESTINATION_ID:-}"
AIRBYTE_CONNECTION_ID="${ADI_HEALTHCHECK_AIRBYTE_CONNECTION_ID:-}"
AIRBYTE_BASE_URL="${AIRBYTE_BASE_URL:-}"
RUN_AIRBYTE_DESTINATION_CHECK=0

usage() {
  cat <<'EOF'
Usage: scripts/dev-healthcheck.sh [options]

Options:
  --airbyte-destination-id ID   Validate a local Airbyte destination after app health checks.
  --airbyte-connection-id ID    Resolve destination from an Airbyte connection before validation.
  --airbyte-base-url URL        Airbyte API base URL (default: http://localhost:18001/api/v1).
  --help                       Show this help.

Environment:
  DEV_BACKEND_URL, DEV_FRONTEND_URL
  ADI_HEALTHCHECK_AIRBYTE_DESTINATION_ID
  ADI_HEALTHCHECK_AIRBYTE_CONNECTION_ID
  AIRBYTE_BASE_URL
EOF
}

while (( $# > 0 )); do
  case "$1" in
    --airbyte-destination-id)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "--airbyte-destination-id requires a value."
        exit 1
      fi
      AIRBYTE_DESTINATION_ID="$2"
      RUN_AIRBYTE_DESTINATION_CHECK=1
      shift 2
      ;;
    --airbyte-connection-id)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "--airbyte-connection-id requires a value."
        exit 1
      fi
      AIRBYTE_CONNECTION_ID="$2"
      RUN_AIRBYTE_DESTINATION_CHECK=1
      shift 2
      ;;
    --airbyte-base-url)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "--airbyte-base-url requires a value."
        exit 1
      fi
      AIRBYTE_BASE_URL="$2"
      shift 2
      ;;
    --help|-h)
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

if [[ -n "$AIRBYTE_DESTINATION_ID" || -n "$AIRBYTE_CONNECTION_ID" ]]; then
  RUN_AIRBYTE_DESTINATION_CHECK=1
fi

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

frontend_curl_flags=(-fsS)
if [[ "$FRONTEND_URL" =~ ^https://(localhost|127\.0\.0\.1)(:|/) ]]; then
  frontend_curl_flags+=("--insecure")
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
    if curl "${frontend_curl_flags[@]}" "$FRONTEND_URL" >/dev/null; then
      if (( RUN_AIRBYTE_DESTINATION_CHECK )); then
        airbyte_args=("$REPO_ROOT/scripts/check_local_airbyte_destination.py" "--run-airbyte-check")
        if [[ -n "$AIRBYTE_DESTINATION_ID" ]]; then
          airbyte_args+=("--destination-id" "$AIRBYTE_DESTINATION_ID")
        fi
        if [[ -n "$AIRBYTE_CONNECTION_ID" ]]; then
          airbyte_args+=("--connection-id" "$AIRBYTE_CONNECTION_ID")
        fi
        if [[ -n "$AIRBYTE_BASE_URL" ]]; then
          airbyte_args+=("--base-url" "$AIRBYTE_BASE_URL")
        fi
        if ! python3 "${airbyte_args[@]}"; then
          echo "Health check failed (Airbyte destination check)."
          exit 1
        fi
      fi
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
