#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CODEX_HOME_DIR="${CODEX_HOME:-${HOME}/.codex}"
TARGET_SKILL_DIR="${CODEX_HOME_DIR}/skills/adinsights-scope-gatekeeper"

mkdir -p "$(dirname "${TARGET_SKILL_DIR}")"

if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete \
    --exclude "__pycache__/" \
    --exclude ".DS_Store" \
    "${SOURCE_SKILL_DIR}/" "${TARGET_SKILL_DIR}/"
else
  rm -rf "${TARGET_SKILL_DIR}"
  mkdir -p "${TARGET_SKILL_DIR}"
  cp -R "${SOURCE_SKILL_DIR}/." "${TARGET_SKILL_DIR}/"
fi

echo "Synced skill to ${TARGET_SKILL_DIR}"
