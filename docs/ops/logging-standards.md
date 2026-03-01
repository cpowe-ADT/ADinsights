# Logging Standards

Our operational logs must stay machine-parseable and privacy-safe while still giving responders the context they need to debug incidents quickly. This document sets the JSON logging rules that apply to backend services, scheduled jobs, and CI utilities.

## Required structure

- Emit newline-delimited JSON (`NDJSON`) where each entry is a single JSON object.
- Include the following top-level keys on every log event:
  - `timestamp` — ISO-8601 string in UTC with millisecond precision.
  - `level` — One of `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`.
  - `message` — Human-readable summary of the event.
  - `tenant_id` — Current tenant scope or `null` for global/system events.
  - `correlation_id` — Request, job, or workflow identifier that ties related entries together.
  - `component` — Logical owner such as `backend.api`, `airbyte.sync`, or `ci.runner`.
- Preserve structured context in nested objects instead of flattening into strings (for example, `{"http": {"status_code": 502, "method": "GET"}}`).

## Log schema reference

| Field            | Type        | Required | Notes                                                                 |
| ---------------- | ----------- | -------- | --------------------------------------------------------------------- |
| `timestamp`      | string      | Yes      | ISO-8601 UTC with milliseconds.                                       |
| `level`          | string      | Yes      | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.                      |
| `message`        | string      | Yes      | Short, action-oriented summary.                                       |
| `tenant_id`      | string/null | Yes      | Use `null` for global/system tasks.                                   |
| `correlation_id` | string      | Yes      | Request ID or task ID for traceability.                               |
| `task_id`        | string/null | No       | Celery task ID when available.                                        |
| `component`      | string      | Yes      | Logical service owner.                                                |
| `event`          | string      | No       | Stable, machine-friendly event name (e.g., `airbyte.sync.completed`). |
| `duration_ms`    | number      | No       | Execution time for the event.                                         |
| `http`           | object      | No       | Nested HTTP context (`method`, `path`, `status_code`).                |
| `error`          | object      | No       | Error summary with `type`, `message`, `stack` (redacted).             |

## Redaction and safety

- Never log plaintext secrets, OAuth tokens, or personally identifiable information.
- Mask identifiers by hashing when raw values are needed for deduplication.
- Treat third-party API responses as sensitive; log only status codes, request identifiers, and summarized error categories.

## Sampling and volume controls

- Sample high-volume `INFO` events at the caller before emitting when rate exceeds 50 events per second.
- Always emit full detail for `ERROR` and `CRITICAL` levels.
- Use the `suppress_logging` flag in Celery tasks when running large backfills and attach a summary log upon completion.

## Cardinality review checklist

- Avoid unbounded labels or fields (raw URLs, user agents, or record IDs).
- Bucket or hash high-cardinality attributes before logging.
- Prefer enums for `event`, `component`, and error categories.
- Sample high-volume informational events to avoid log ingestion cost spikes.
- Review new fields with ops when adding multi-tenant identifiers.

## Quality gates

- CI jobs run `scripts/ci/validate-logs-schema.py` against captured test output. Pull requests fail if new log fields break the schema contract.
- Observability dashboards alert when the ingestion pipeline sees malformed JSON (non-object payloads or missing `timestamp`).
- Teams must provide log field documentation when introducing new structured keys to ensure downstream parsers stay up to date.
