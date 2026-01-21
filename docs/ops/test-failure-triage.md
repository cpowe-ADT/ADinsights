# Test Failure Triage (v0.1)

Purpose: quick steps when tests fail in AI sessions.

## Steps
1) Identify failing suite (frontend/backend/dbt/airbyte).
2) Read error stack and locate file/line.
3) Check for recent changes in the failing area.
4) Fix root cause (not just the test).
5) Re-run the smallest failing test set.
6) Re-run full suite for that folder.

## Notes
- Avoid masking failures by loosening assertions.
- Update docs if behavior changed.
