# CSV Upload Runbook

Purpose: define the CSV contract used by the upload API and frontend parser so files are
validated consistently before they reach `/api/metrics/combined/`.

Timezone baseline: `America/Jamaica`.

## Endpoints

- `POST /api/uploads/metrics/`
- `GET /api/uploads/metrics/`
- `DELETE /api/uploads/metrics/`
- `GET /api/metrics/combined/?source=upload`

## Required files

1. `campaign_csv` (required)
2. `parish_csv` (optional)
3. `budget_csv` (optional)

## Campaign CSV

Required columns:

- `date`
- `campaign_id`
- `campaign_name`
- `platform`
- `spend`
- `impressions`
- `clicks`
- `conversions`

Optional columns:

- `parish`
- `revenue`
- `roas`
- `status`
- `objective`
- `start_date`
- `end_date`
- `currency`

## Parish CSV

Required columns:

- `parish`
- `spend`
- `impressions`
- `clicks`
- `conversions`

Optional columns:

- `date`
- `revenue`
- `roas`
- `campaign_count`
- `currency`

## Budget CSV

Required columns:

- `month`
- `campaign_name`
- `planned_budget`

Optional columns:

- `spend_to_date`
- `projected_spend`
- `pacing_percent`
- `parishes`
- `platform`

## Alias and parser parity

Source of truth aliases:

- Backend: `backend/analytics/uploads.py` (`COLUMN_ALIASES`)
- Frontend: `frontend/src/lib/uploadedMetrics.ts` (`COLUMN_ALIASES`)

Automated parity check:

```bash
python3 infrastructure/airbyte/scripts/check_data_contracts.py
```

## Validation behavior

1. Missing required columns return `400` with `CSV validation failed`.
2. Invalid numeric/date fields return row-level errors.
3. Missing optional parish on campaign rows is normalized to `"Unknown"` with warnings.
4. Successful uploads update `TenantMetricsSnapshot` for source `upload`.

## Smoke checks

```bash
ruff check backend
pytest -q backend/tests/test_upload_parsers.py backend/tests/test_metrics_upload_api.py
cd frontend && npm test -- --run
```

## Troubleshooting

1. `campaign_csv file is required`:
   Ensure multipart payload key is exactly `campaign_csv`.
2. `Missing required column`:
   Verify header aliases against parser maps before upload.
3. Empty combined payload:
   Confirm upload status endpoint returns `has_upload=true` and snapshot timestamp.
