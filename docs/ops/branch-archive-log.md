# Branch Consolidation Log

Tracking legacy branches that have been reviewed as part of the consolidation effort. Once a branch’s useful changes are replayed (or deemed obsolete), it is documented here and then deleted from the remote to minimise notification noise.

| Branch name | Action | Notes | Date |
| --- | --- | --- | --- |
| `codex/implement-metrics-csv-export-endpoint` | Replayed & deleted | Warehouse-backed CSV export reimplemented on `main` (`feat(analytics): export metrics from warehouse instead of fake fixture`) | 2025-10-17 |
| `codex/fix-high-priority-bug-in-airbyte-service` | Replayed & deleted | Millisecond timestamp handling folded into `_coerce_timestamp` (`fix(airbyte): normalise millisecond timestamps`) | 2025-10-17 |
| `feat/frontend-admin-bootstrap` | Deleted (obsolete) | Branch removed harness scripts and broke health endpoints; existing `main` already includes frontend GeoJSON/loading fixes. No salvageable additions beyond current state. | 2025-10-17 |
| `codex/fix-test-failures-and-code-issues-fuzx8j` | Deleted (obsolete) | Branch reverted a large portion of the modern backend/frontend/infra stack; conflicts with current health endpoint and harness architecture. | 2025-10-17 |
| `codex/configure-prettier-and-update-ci` | Deleted (obsolete) | Applied sweeping repo reformatting and removed current tooling; not compatible with today’s structure. | 2025-10-17 |
| `codex/upgrade-to-chatgpt-plus-for-codex-access` | Deleted (obsolete) | Contained mass deletions of backend authentication/export code; no unique forward-looking changes. | 2025-10-17 |
