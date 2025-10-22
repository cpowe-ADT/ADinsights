#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 4 ]]; then
  cat >&2 <<'USAGE'
Usage: dbt-wrapper <dbt-command> <default-project-dir> <default-profiles-dir> <subcommand> [args...]
USAGE
  exit 2
fi

cmd_string="$1"
default_project="$2"
default_profiles="$3"
shift 3

project_dir="${DBT_PROJECT_DIR:-$default_project}"
profiles_dir="${DBT_PROFILES_DIR:-$default_profiles}"

read -r -a cmd_parts <<<"$cmd_string"
if [[ ${#cmd_parts[@]} -eq 0 ]]; then
  echo "dbt executable not provided" >&2
  exit 3
fi

clean_cmd=()
i=0
while [[ $i -lt ${#cmd_parts[@]} ]]; do
  token="${cmd_parts[$i]}"
  case "$token" in
    --project-dir)
      (( i += 1 ))
      if [[ $i -ge ${#cmd_parts[@]} ]]; then
        echo "--project-dir requires a value" >&2
        exit 4
      fi
      project_dir="${cmd_parts[$i]}"
      ;;
    --profiles-dir)
      (( i += 1 ))
      if [[ $i -ge ${#cmd_parts[@]} ]]; then
        echo "--profiles-dir requires a value" >&2
        exit 5
      fi
      profiles_dir="${cmd_parts[$i]}"
      ;;
    *)
      clean_cmd+=("$token")
      ;;
  esac
  (( i += 1 ))
done

args=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir)
      shift
      if [[ $# -eq 0 ]]; then
        echo "--project-dir requires a value" >&2
        exit 6
      fi
      project_dir="$1"
      ;;
    --profiles-dir)
      shift
      if [[ $# -eq 0 ]]; then
        echo "--profiles-dir requires a value" >&2
        exit 7
      fi
      profiles_dir="$1"
      ;;
    *)
      args+=("$1")
      ;;
  esac
  shift
done

if [[ ${#args[@]} -eq 0 ]]; then
  echo "dbt subcommand is required" >&2
  exit 8
fi

if [[ ${#clean_cmd[@]} -eq 0 ]]; then
  echo "dbt executable not provided" >&2
  exit 9
fi

dbt_exec="${clean_cmd[0]}"
dbt_path=""
if command -v -- "$dbt_exec" >/dev/null 2>&1; then
  dbt_path="$(command -v -- "$dbt_exec")"
fi

if [[ -z "$dbt_path" ]]; then
  repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
  candidate="$repo_root/.venv-dbt/bin/$dbt_exec"
  if [[ -x "$candidate" ]]; then
    dbt_path="$candidate"
  fi
fi

if [[ -z "$dbt_path" ]]; then
  cat >&2 <<'ERR'
dbt executable not found on PATH. Install dbt (e.g. via scripts/dbt-dev-setup.sh)
or set the DBT environment variable to the desired command before invoking make.
ERR
  exit 10
fi

if [[ -d "$dbt_path" ]]; then
  echo "dbt executable resolved to a directory: $dbt_path" >&2
  echo "Set DBT to a valid executable or run scripts/dbt-dev-setup.sh." >&2
  exit 11
fi

clean_cmd[0]="$dbt_path"

if [[ -n "$project_dir" ]]; then
  export DBT_PROJECT_DIR="$project_dir"
fi
if [[ -n "$profiles_dir" ]]; then
  export DBT_PROFILES_DIR="$profiles_dir"
fi

exec "${clean_cmd[@]}" "${args[@]}"
