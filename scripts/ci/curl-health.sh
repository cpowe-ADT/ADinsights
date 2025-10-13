#!/bin/sh
set -eu

MAX_ATTEMPTS=5
LOG_DIR="health-logs"
CSV_FILE="observability-health.csv"
ENDPOINTS="/api/health/ /api/health/airbyte/ /api/health/dbt/"
CURL_TIMEOUT=20

if [ "${STAGING_BASE_URL-}" = "" ]; then
  echo "STAGING_BASE_URL is not set" >&2
  exit 1
fi

mkdir -p "$LOG_DIR"
printf 'endpoint,status,attempts,total_duration_seconds,last_http_code\n' > "$CSV_FILE"

log_msg() {
  printf '%s\n' "$1" | tee -a "$LOG_DIR/summary.log"
}

now_seconds() {
  python3 -c 'import time; print(f"{time.time():.6f}")'
}

duration_seconds() {
  python3 - "$1" "$2" <<'PY'
import decimal
import sys

start = decimal.Decimal(sys.argv[1])
end = decimal.Decimal(sys.argv[2])
print(f"{end - start:.3f}")
PY
}

jitter_sleep() {
  base_seconds=$1
  total=$(python3 - "$base_seconds" <<'PY'
import random
import sys

base = float(sys.argv[1])
rng = random.SystemRandom()
print(f"{base + rng.uniform(0, base):.3f}")
PY
)
  sleep "$total"
}

run_check() {
  endpoint="$1"
  slug=$(printf '%s' "$endpoint" | sed 's#[^A-Za-z0-9]#_#g')
  attempt=1
  success=0
  total_start=$(now_seconds)
  last_http_code="000"
  while [ $attempt -le $MAX_ATTEMPTS ]; do
    body_file="$LOG_DIR/${slug}_attempt${attempt}.body"
    headers_file="$LOG_DIR/${slug}_attempt${attempt}.headers"
    status_file="$LOG_DIR/${slug}_attempt${attempt}.status"

    set +e
    http_code=$(curl \
      --silent \
      --show-error \
      --location \
      --write-out '%{http_code}' \
      --output "$body_file" \
      --dump-header "$headers_file" \
      --max-time "$CURL_TIMEOUT" \
      "$STAGING_BASE_URL$endpoint" 2>"$LOG_DIR/${slug}_attempt${attempt}.stderr")
    curl_status=$?
    set -e
    if [ $curl_status -ne 0 ]; then
      http_code="000"
    fi

    last_http_code="$http_code"

    printf '%s' "$http_code" > "$status_file"

    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
      log_msg "SUCCESS ${endpoint} (attempt ${attempt})"
      success=1
      break
    fi

    log_msg "FAIL ${endpoint} (attempt ${attempt}) status=${http_code}"

    if [ $attempt -lt $MAX_ATTEMPTS ]; then
      sleep_seconds=$((2 ** (attempt - 1)))
      jitter_sleep "$sleep_seconds"
    fi

    attempt=$((attempt + 1))
  done

  total_end=$(now_seconds)
  if [ $success -ne 1 ]; then
    log_msg "FINAL FAILURE ${endpoint}"
  fi

  if [ $success -eq 1 ]; then
    attempts_used=$attempt
  else
    attempts_used=$((attempt - 1))
  fi

  total_duration=$(duration_seconds "$total_start" "$total_end")
  if [ "$last_http_code" = "" ]; then
    last_http_code="000"
  fi

  printf '"%s","%s",%s,%s,"%s"\n' \
    "$endpoint" \
    "$([ $success -eq 1 ] && echo success || echo failure)" \
    "$attempts_used" \
    "$total_duration" \
    "$last_http_code" >> "$CSV_FILE"

  if [ $success -ne 1 ]; then
    return 1
  fi

  return 0
}

overall_status=0
for endpoint in $ENDPOINTS; do
  if ! run_check "$endpoint"; then
    overall_status=1
  fi
  log_msg "---"

done

exit $overall_status
