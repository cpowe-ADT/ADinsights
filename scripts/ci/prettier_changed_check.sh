#!/usr/bin/env bash
set -euo pipefail

if ! command -v npx >/dev/null 2>&1; then
  echo "npx is required to run Prettier checks." >&2
  exit 1
fi

resolve_pr_range() {
  local base_sha head_sha
  base_sha="${GITHUB_BASE_SHA:-}"
  head_sha="${GITHUB_HEAD_SHA:-}"

  if [[ -n "${GITHUB_EVENT_PATH:-}" && -f "${GITHUB_EVENT_PATH:-}" ]]; then
    if command -v jq >/dev/null 2>&1; then
      if [[ -z "$base_sha" ]]; then
        base_sha="$(jq -r '.pull_request.base.sha // empty' "$GITHUB_EVENT_PATH")"
      fi
      if [[ -z "$head_sha" ]]; then
        head_sha="$(jq -r '.pull_request.head.sha // empty' "$GITHUB_EVENT_PATH")"
      fi
    fi
  fi

  if [[ -z "$base_sha" ]]; then
    base_sha="$(git merge-base origin/main HEAD 2>/dev/null || true)"
  fi

  if [[ -z "$base_sha" ]]; then
    echo "Unable to resolve PR base SHA for Prettier changed-files check." >&2
    exit 1
  fi

  if [[ -n "$head_sha" ]]; then
    echo "${base_sha}...${head_sha}"
    return
  fi

  echo "${base_sha}...HEAD"
}

resolve_push_range() {
  local sha
  sha="${GITHUB_SHA:-}"

  if [[ -n "$sha" ]]; then
    echo "${sha}^..${sha}"
    return
  fi

  echo "HEAD^..HEAD"
}

if [[ "${GITHUB_EVENT_NAME:-}" == "pull_request" ]]; then
  diff_range="$(resolve_pr_range)"
else
  diff_range="$(resolve_push_range)"
fi

changed_files=()
while IFS= read -r file; do
  [[ -n "$file" ]] || continue
  changed_files+=("$file")
done < <(git diff --name-only --diff-filter=ACMR "$diff_range")

if [[ ${#changed_files[@]} -eq 0 ]]; then
  echo "No changed files detected for range ${diff_range}; skipping Prettier check."
  exit 0
fi

prettier_files=()
while IFS= read -r file; do
  [[ -n "$file" ]] || continue
  prettier_files+=("$file")
done < <(
  printf '%s\n' "${changed_files[@]}" \
    | rg -N '\.(cjs|css|html|js|json|jsx|md|mjs|scss|ts|tsx|yaml|yml)$' || true
)

if [[ ${#prettier_files[@]} -eq 0 ]]; then
  echo "No Prettier-supported changed files detected; skipping Prettier check."
  exit 0
fi

echo "Running Prettier check on ${#prettier_files[@]} changed file(s)."
npx prettier --check --ignore-unknown "${prettier_files[@]}"
