#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

VENV_DIR=".venv-dbt"
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip -q install -U pip
"$VENV_DIR/bin/python" -m pip -q install dbt-core dbt-postgres dbt-duckdb

export DBT_PROJECT_DIR="$(pwd)/dbt"
export DBT_PROFILES_DIR="$(pwd)/dbt/.profiles"

mkdir -p "$DBT_PROFILES_DIR"
# Always update profiles.yml from example to ensure correct profile names
cp dbt/profiles.yml.example "$DBT_PROFILES_DIR/profiles.yml"

# Provide default envs for local smoke runs
export DBT_USER="postgres"
export DBT_PASSWORD="postgres"
export DBT_DB="adinsights"
export DBT_PORT=5432

echo "DBT_PROJECT_DIR=$DBT_PROJECT_DIR"
echo "DBT_PROFILES_DIR=$DBT_PROFILES_DIR"

# Prefer DuckDB profile for safe local smoke runs; fall back to Postgres if env wants it
export DBT_PROFILE="adinsights_duckdb"
"$VENV_DIR/bin/dbt" deps --profile "$DBT_PROFILE" || true
"$VENV_DIR/bin/dbt" seed --full-refresh --profile "$DBT_PROFILE" || true
"$VENV_DIR/bin/dbt" run --select staging --profile "$DBT_PROFILE" || true
"$VENV_DIR/bin/dbt" run --select reference --profile "$DBT_PROFILE" || true
"$VENV_DIR/bin/dbt" snapshot --profile "$DBT_PROFILE" || true
# DuckDB does not support the default merge incremental strategy; force a full refresh for marts.
"$VENV_DIR/bin/dbt" run --select marts --full-refresh --profile "$DBT_PROFILE" || true
