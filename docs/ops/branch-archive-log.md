# Branch Consolidation Log

Tracking legacy branches that have been reviewed as part of the consolidation effort. Once a branch’s useful changes are replayed (or deemed obsolete), it is documented here and then deleted from the remote to minimise notification noise.

| Branch name | Action | Notes | Date |
| --- | --- | --- | --- |
| `codex/implement-metrics-csv-export-endpoint` | Replayed & deleted | Warehouse-backed CSV export reimplemented on `main` (`feat(analytics): export metrics from warehouse instead of fake fixture`) | 2025-10-17 |
| `codex/fix-high-priority-bug-in-airbyte-service` | Replayed & deleted | Millisecond timestamp handling folded into `_coerce_timestamp` (`fix(airbyte): normalise millisecond timestamps`) | 2025-10-17 |
