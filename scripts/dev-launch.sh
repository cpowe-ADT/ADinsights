#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker-compose.dev.yml"
ACTIVE_ENV_FILE="$REPO_ROOT/.dev-launch.active.env"

DEFAULT_POSTGRES_PORT=5432
DEFAULT_REDIS_PORT=6379
DEFAULT_BACKEND_PORT=8000
DEFAULT_FRONTEND_PORT=5173

DETACH="${DEV_DETACH:-1}"
AUTO_UPDATE="${DEV_AUTO_UPDATE:-1}"
PULL_IMAGES="${DEV_PULL_IMAGES:-1}"
OPEN_BROWSER="${DEV_OPEN_BROWSER:-1}"
RUN_HEALTHCHECK="${DEV_RUN_HEALTHCHECK:-1}"
AUTO_SEED="${DEV_AUTO_SEED:-1}"
VERIFY_DEMO_DATA="${DEV_VERIFY_DEMO_DATA:-1}"

REQUESTED_PROFILE=""
PROFILE_FROM_ENV="${DEV_PORT_PROFILE:-}"
SELECTED_PROFILE=""
SELECTED_PROFILE_SOURCE=""
STRICT_PROFILE=0
NON_INTERACTIVE=0
LIST_PROFILES=0

EXPLICIT_POSTGRES=0
EXPLICIT_REDIS=0
EXPLICIT_BACKEND=0
EXPLICIT_FRONTEND=0

POSTGRES_PORT="$DEFAULT_POSTGRES_PORT"
REDIS_PORT="$DEFAULT_REDIS_PORT"
BACKEND_PORT="$DEFAULT_BACKEND_PORT"
FRONTEND_PORT="$DEFAULT_FRONTEND_PORT"

usage() {
  cat <<'USAGE'
Usage: scripts/dev-launch.sh [options]

Options:
  --foreground        Run docker compose in the foreground (default: detached)
  --no-update         Skip git auto-update
  --no-pull           Skip pulling base images (postgres/redis)
  --no-open           Do not open the frontend URL in a browser
  --no-healthcheck    Skip health checks after startup
  --no-seed           Skip creating/updating the dev admin user after startup
  --no-demo-check     Skip demo adapter verification after startup
  --profile <1-4>     Select a fixed launcher profile
  --list-profiles     Print the 4 port profiles and exit
  --strict-profile    Fail if the selected profile has port conflicts
  --non-interactive   Do not prompt; use env/default profile selection
  -h, --help          Show this help message

Environment overrides:
  DEV_AUTO_UPDATE=0
  DEV_PULL_IMAGES=0
  DEV_OPEN_BROWSER=0
  DEV_RUN_HEALTHCHECK=0
  DEV_AUTO_SEED=0
  DEV_VERIFY_DEMO_DATA=0
  DEV_DETACH=0
  DEV_PORT_PROFILE=1
  DEV_POSTGRES_PORT=5432
  DEV_REDIS_PORT=6379
  DEV_BACKEND_PORT=8000
  DEV_FRONTEND_PORT=5173
USAGE
}

print_profiles() {
  cat <<'PROFILES'
Available launcher profiles:
  1) profile-1 (default): postgres 5432, redis 6379, backend 8000, frontend 5173
  2) profile-2 (alt):     postgres 5433, redis 6380, backend 8001, frontend 5174
  3) profile-3 (alt):     postgres 5434, redis 6381, backend 8002, frontend 5175
  4) profile-4 (high):    postgres 15432, redis 16379, backend 18000, frontend 15173
PROFILES
}

validate_profile() {
  case "$1" in
    1|2|3|4) return 0 ;;
    *) return 1 ;;
  esac
}

validate_port() {
  local name="$1"
  local value="$2"
  if ! [[ "$value" =~ ^[0-9]+$ ]]; then
    echo "Invalid $name '$value' (must be a number)."
    exit 1
  fi
  if (( value < 1 || value > 65535 )); then
    echo "Invalid $name '$value' (must be between 1 and 65535)."
    exit 1
  fi
}

profile_values() {
  local profile="$1"
  case "$profile" in
    1) echo "5432 6379 8000 5173" ;;
    2) echo "5433 6380 8001 5174" ;;
    3) echo "5434 6381 8002 5175" ;;
    4) echo "15432 16379 18000 15173" ;;
    *)
      echo "Unknown profile '$profile'."
      exit 1
      ;;
  esac
}

load_profile_ports() {
  local profile="$1"
  local values
  local psql redis backend frontend
  values="$(profile_values "$profile")"
  IFS=' ' read -r psql redis backend frontend <<<"$values"
  PROFILE_POSTGRES_PORT="$psql"
  PROFILE_REDIS_PORT="$redis"
  PROFILE_BACKEND_PORT="$backend"
  PROFILE_FRONTEND_PORT="$frontend"
}

has_explicit_port_overrides() {
  (( EXPLICIT_POSTGRES == 1 || EXPLICIT_REDIS == 1 || EXPLICIT_BACKEND == 1 || EXPLICIT_FRONTEND == 1 ))
}

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
  while (( tries < 20 )); do
    if ! port_in_use "$port"; then
      echo "$port"
      return 0
    fi
    port=$((port + 1))
    tries=$((tries + 1))
  done
  echo "$1"
  return 0
}

profile_conflicts() {
  local profile="$1"
  local conflicts=()

  load_profile_ports "$profile"

  if (( EXPLICIT_POSTGRES == 0 )) && port_in_use "$PROFILE_POSTGRES_PORT"; then
    conflicts+=("postgres:$PROFILE_POSTGRES_PORT")
  fi
  if (( EXPLICIT_REDIS == 0 )) && port_in_use "$PROFILE_REDIS_PORT"; then
    conflicts+=("redis:$PROFILE_REDIS_PORT")
  fi
  if (( EXPLICIT_BACKEND == 0 )) && port_in_use "$PROFILE_BACKEND_PORT"; then
    conflicts+=("backend:$PROFILE_BACKEND_PORT")
  fi
  if (( EXPLICIT_FRONTEND == 0 )) && port_in_use "$PROFILE_FRONTEND_PORT"; then
    conflicts+=("frontend:$PROFILE_FRONTEND_PORT")
  fi

  if (( ${#conflicts[@]} > 0 )); then
    echo "${conflicts[*]}"
  else
    echo ""
  fi
}

apply_profile_ports_with_overrides() {
  local profile="$1"
  load_profile_ports "$profile"

  if (( EXPLICIT_POSTGRES == 1 )); then
    POSTGRES_PORT="$DEV_POSTGRES_PORT"
  else
    POSTGRES_PORT="$PROFILE_POSTGRES_PORT"
  fi

  if (( EXPLICIT_REDIS == 1 )); then
    REDIS_PORT="$DEV_REDIS_PORT"
  else
    REDIS_PORT="$PROFILE_REDIS_PORT"
  fi

  if (( EXPLICIT_BACKEND == 1 )); then
    BACKEND_PORT="$DEV_BACKEND_PORT"
  else
    BACKEND_PORT="$PROFILE_BACKEND_PORT"
  fi

  if (( EXPLICIT_FRONTEND == 1 )); then
    FRONTEND_PORT="$DEV_FRONTEND_PORT"
  else
    FRONTEND_PORT="$PROFILE_FRONTEND_PORT"
  fi
}

next_profile() {
  local current="$1"
  echo $(( (current % 4) + 1 ))
}

prompt_for_profile() {
  local choice=""
  print_profiles
  echo
  read -r -p "Choose a launcher profile [1-4] (default: 1): " choice
  if [[ -z "$choice" ]]; then
    echo "1"
    return 0
  fi
  if ! validate_profile "$choice"; then
    echo "Invalid profile '$choice'. Use 1, 2, 3, or 4."
    exit 1
  fi
  echo "$choice"
}

write_active_env() {
  local selected_profile="$1"
  local generated_at
  generated_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  cat > "$ACTIVE_ENV_FILE" <<ACTIVE_ENV
# Generated by scripts/dev-launch.sh
DEV_ACTIVE_PROFILE=$selected_profile
POSTGRES_PORT=$POSTGRES_PORT
REDIS_PORT=$REDIS_PORT
BACKEND_PORT=$BACKEND_PORT
FRONTEND_PORT=$FRONTEND_PORT
DEV_BACKEND_URL=http://localhost:$BACKEND_PORT
DEV_FRONTEND_URL=http://localhost:$FRONTEND_PORT
DEV_LAUNCH_GENERATED_AT=$generated_at
ACTIVE_ENV
}

extract_access_token() {
  python3 -c 'import json,sys
payload=sys.stdin.read().strip()
if not payload:
    print("")
    raise SystemExit(0)
try:
    print((json.loads(payload) or {}).get("access",""))
except Exception:
    print("")
'
}

ensure_dev_admin_user() {
  if [[ "$AUTO_SEED" != "1" ]]; then
    return 0
  fi

  echo "Ensuring dev admin account exists..."
  if ! "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" exec -T backend python manage.py seed_dev_data --skip-fixture >/dev/null 2>&1; then
    echo "Warning: could not auto-seed dev admin user. Continuing."
  fi
}

verify_demo_adapter() {
  if [[ "$VERIFY_DEMO_DATA" != "1" ]]; then
    return 0
  fi
  if ! command -v curl >/dev/null 2>&1; then
    echo "Warning: curl not available; skipping demo adapter verification."
    return 0
  fi

  local api_base login_response token adapters
  api_base="${DEV_BACKEND_URL}/api"

  login_response="$(
    # pragma: allowlist secret
    curl -sS -m 10 -H "Content-Type: application/json" -d '{"email":"devadmin@local.test","password":"devadmin1"}' "${api_base}/auth/login/" || true
  )"
  token="$(printf '%s' "$login_response" | extract_access_token)"

  if [[ -z "$token" ]]; then
    login_response="$(
      # pragma: allowlist secret
      curl -sS -m 10 -H "Content-Type: application/json" -d '{"email":"admin@example.com","password":"admin1"}' "${api_base}/auth/login/" || true
    )"
    token="$(printf '%s' "$login_response" | extract_access_token)"
  fi

  if [[ -z "$token" ]]; then
    echo "Warning: unable to authenticate for demo adapter verification."
    echo "         Try logging in manually, then call ${DEV_BACKEND_URL}/api/adapters/."
    return 0
  fi

  adapters="$(curl -sS -m 10 -H "Authorization: Bearer ${token}" "${api_base}/adapters/" || true)"
  if ! printf '%s' "$adapters" | python3 -c 'import json,sys
raw=sys.stdin.read().strip()
try:
    data=json.loads(raw)
except Exception:
    raise SystemExit(1)
if not isinstance(data,list):
    raise SystemExit(1)
keys={str(item.get("key","")) for item in data if isinstance(item,dict)}
raise SystemExit(0 if ("demo" in keys or "fake" in keys) else 1)
'; then
    echo "Launch check failed: demo adapter is not enabled for ${DEV_BACKEND_URL}."
    echo "Expected /api/adapters/ to include 'demo' or 'fake'."
    echo "Check backend flags: ENABLE_DEMO_ADAPTER=1 and/or ENABLE_FAKE_ADAPTER=1."
    exit 1
  fi

  echo "Demo adapter check passed."
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
    --no-seed)
      AUTO_SEED=0
      shift
      ;;
    --no-demo-check)
      VERIFY_DEMO_DATA=0
      shift
      ;;
    --profile)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --profile"
        exit 1
      fi
      REQUESTED_PROFILE="$2"
      shift 2
      ;;
    --profile=*)
      REQUESTED_PROFILE="${1#*=}"
      shift
      ;;
    --list-profiles)
      LIST_PROFILES=1
      shift
      ;;
    --strict-profile)
      STRICT_PROFILE=1
      shift
      ;;
    --non-interactive)
      NON_INTERACTIVE=1
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

if (( LIST_PROFILES == 1 )); then
  print_profiles
  exit 0
fi

if [[ -n "$REQUESTED_PROFILE" ]] && ! validate_profile "$REQUESTED_PROFILE"; then
  echo "Invalid --profile '$REQUESTED_PROFILE'. Use 1, 2, 3, or 4."
  exit 1
fi

if [[ -n "$PROFILE_FROM_ENV" ]] && ! validate_profile "$PROFILE_FROM_ENV"; then
  echo "Invalid DEV_PORT_PROFILE '$PROFILE_FROM_ENV'. Use 1, 2, 3, or 4."
  exit 1
fi

if [[ -n "${DEV_POSTGRES_PORT+x}" ]]; then
  EXPLICIT_POSTGRES=1
  validate_port "DEV_POSTGRES_PORT" "$DEV_POSTGRES_PORT"
fi
if [[ -n "${DEV_REDIS_PORT+x}" ]]; then
  EXPLICIT_REDIS=1
  validate_port "DEV_REDIS_PORT" "$DEV_REDIS_PORT"
fi
if [[ -n "${DEV_BACKEND_PORT+x}" ]]; then
  EXPLICIT_BACKEND=1
  validate_port "DEV_BACKEND_PORT" "$DEV_BACKEND_PORT"
fi
if [[ -n "${DEV_FRONTEND_PORT+x}" ]]; then
  EXPLICIT_FRONTEND=1
  validate_port "DEV_FRONTEND_PORT" "$DEV_FRONTEND_PORT"
fi

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

if [[ -n "$REQUESTED_PROFILE" ]]; then
  SELECTED_PROFILE="$REQUESTED_PROFILE"
  SELECTED_PROFILE_SOURCE="flag"
elif [[ -n "$PROFILE_FROM_ENV" ]]; then
  SELECTED_PROFILE="$PROFILE_FROM_ENV"
  SELECTED_PROFILE_SOURCE="env"
elif (( NON_INTERACTIVE == 0 )) && ! has_explicit_port_overrides && [[ -t 0 ]]; then
  SELECTED_PROFILE="$(prompt_for_profile)"
  SELECTED_PROFILE_SOURCE="interactive"
else
  SELECTED_PROFILE="1"
  SELECTED_PROFILE_SOURCE="default"
fi

initial_conflicts="$(profile_conflicts "$SELECTED_PROFILE")"
if [[ -n "$initial_conflicts" ]]; then
  if (( STRICT_PROFILE == 1 )); then
    echo "Selected profile-$SELECTED_PROFILE is not available: $initial_conflicts"
    echo "Run with a different profile, or remove --strict-profile to allow fallback."
    exit 1
  fi

  fallback_found=0
  candidate="$(next_profile "$SELECTED_PROFILE")"
  while [[ "$candidate" != "$SELECTED_PROFILE" ]]; do
    candidate_conflicts="$(profile_conflicts "$candidate")"
    if [[ -z "$candidate_conflicts" ]]; then
      echo "Selected profile-$SELECTED_PROFILE has conflicts ($initial_conflicts)."
      echo "Using profile-$candidate instead."
      SELECTED_PROFILE="$candidate"
      fallback_found=1
      break
    fi
    candidate="$(next_profile "$candidate")"
  done

  if (( fallback_found == 0 )); then
    echo "All 4 profiles have conflicts. Falling back to per-port incremental search."
  fi
fi

apply_profile_ports_with_overrides "$SELECTED_PROFILE"

if port_in_use "$POSTGRES_PORT"; then
  if (( EXPLICIT_POSTGRES == 1 )); then
    echo "Port $POSTGRES_PORT is in use; DEV_POSTGRES_PORT is set so it will be used anyway."
  else
    original_port="$POSTGRES_PORT"
    POSTGRES_PORT="$(find_free_port "$POSTGRES_PORT")"
    echo "Port $original_port is in use; using $POSTGRES_PORT for Postgres."
  fi
fi

if port_in_use "$REDIS_PORT"; then
  if (( EXPLICIT_REDIS == 1 )); then
    echo "Port $REDIS_PORT is in use; DEV_REDIS_PORT is set so it will be used anyway."
  else
    original_port="$REDIS_PORT"
    REDIS_PORT="$(find_free_port "$REDIS_PORT")"
    echo "Port $original_port is in use; using $REDIS_PORT for Redis."
  fi
fi

if port_in_use "$BACKEND_PORT"; then
  if (( EXPLICIT_BACKEND == 1 )); then
    echo "Port $BACKEND_PORT is in use; DEV_BACKEND_PORT is set so it will be used anyway."
  else
    original_port="$BACKEND_PORT"
    BACKEND_PORT="$(find_free_port "$BACKEND_PORT")"
    echo "Port $original_port is in use; using $BACKEND_PORT for the backend."
  fi
fi

if port_in_use "$FRONTEND_PORT"; then
  if (( EXPLICIT_FRONTEND == 1 )); then
    echo "Port $FRONTEND_PORT is in use; DEV_FRONTEND_PORT is set so it will be used anyway."
  else
    original_port="$FRONTEND_PORT"
    FRONTEND_PORT="$(find_free_port "$FRONTEND_PORT")"
    echo "Port $original_port is in use; using $FRONTEND_PORT for the frontend."
  fi
fi

export POSTGRES_PORT REDIS_PORT BACKEND_PORT FRONTEND_PORT
export DEV_BACKEND_URL="http://localhost:${BACKEND_PORT}"
export DEV_FRONTEND_URL="http://localhost:${FRONTEND_PORT}"
export DEV_ACTIVE_PROFILE="$SELECTED_PROFILE"
export FRONTEND_BASE_URL="$DEV_FRONTEND_URL"

write_active_env "$SELECTED_PROFILE"

echo "Resolved launcher profile: profile-$SELECTED_PROFILE (source: $SELECTED_PROFILE_SOURCE)"
echo "Resolved ports: postgres=$POSTGRES_PORT redis=$REDIS_PORT backend=$BACKEND_PORT frontend=$FRONTEND_PORT"
echo "Backend URL: $DEV_BACKEND_URL"
echo "Frontend URL: $DEV_FRONTEND_URL"
echo "Open this exact frontend URL (do not use bare http://127.0.0.1): $DEV_FRONTEND_URL"
echo "Active runtime file: $ACTIVE_ENV_FILE"

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

  ensure_dev_admin_user
  verify_demo_adapter

  if [[ "$OPEN_BROWSER" == "1" ]] && command -v open >/dev/null 2>&1; then
    open "$DEV_FRONTEND_URL"
  fi

  echo "Login: devadmin@local.test / devadmin1"
  echo "Stack is running. Stop it with: ${COMPOSE_CMD[*]} -f docker-compose.dev.yml down"
else
  "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" up --build
fi
