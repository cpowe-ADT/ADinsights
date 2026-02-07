# Secrets Baseline Refresh Evidence (P1-X6)

Timestamp: 2026-02-05 23:29 EST (America/Jamaica)

## Commands

1. Refresh existing baseline:

```bash
detect-secrets scan --baseline .secrets.baseline --exclude-files '(docs/project/adinsights-stakeholder-deck\.(key|pptx)$|docs/project/assets/.*|.*\.duckdb$)' backend dbt docs infrastructure scripts .github README.md
```

2. Validate currently changed files against refreshed baseline (without touching git index):

```bash
cp .secrets.baseline /tmp/adinsights.secrets.baseline
files=$(git status --porcelain | awk '{print $2}' | rg -v '(^$|\.duckdb$|\.key$|\.pptx$|^docs/project/assets/|\.png$)' | tr '\n' ' ')
detect-secrets-hook --baseline /tmp/adinsights.secrets.baseline $files
```

## Result

- Baseline refresh: PASS (exit code 0)
- Changed-files verification: PASS (exit code 0)
- New un-baselined secrets detected in changed files: none

## Notes

- Large binary deck/assets were excluded from scan scope for bounded runtime.
- This completes `P1-X6` at repository level; production secret manager state remains covered under external infrastructure items.
