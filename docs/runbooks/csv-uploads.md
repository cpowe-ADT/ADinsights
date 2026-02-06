# CSV Uploads Runbook

## Purpose

Document the CSV formats accepted by `/api/uploads/metrics/` and how they power dashboards.

## Endpoints

- `POST /api/uploads/metrics/` (multipart form)
  - `campaign_csv` (required)
  - `parish_csv` (optional)
  - `budget_csv` (optional)
- `GET /api/uploads/metrics/` (status + counts)
- `DELETE /api/uploads/metrics/` (clear)
- `GET /api/metrics/combined/?source=upload` (dashboard payload)

## CSV formats

### Daily campaign metrics (required)

Required columns:

- `date` (YYYY-MM-DD)
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
- `start_date` (YYYY-MM-DD)
- `end_date` (YYYY-MM-DD)
- `currency` (e.g., JMD, USD)

Example:

```csv
date,campaign_id,campaign_name,platform,parish,spend,impressions,clicks,conversions,revenue,roas,status
2024-10-01,cmp-1,Launch,Meta,Kingston,120,12000,420,33,480,4.0,Active
2024-10-02,cmp-1,Launch,Meta,Kingston,80,8000,210,20,320,4.0,Active
```

### Parish metrics (optional)

Required columns:

- `parish`
- `spend`
- `impressions`
- `clicks`
- `conversions`

Optional columns:

- `date` (YYYY-MM-DD)
- `revenue`
- `roas`
- `campaign_count`
- `currency`

Example:

```csv
parish,spend,impressions,clicks,conversions,roas,campaign_count
Kingston,200,20000,630,53,4.0,2
St Andrew,50,4000,90,7,2.0,1
```

### Monthly budgets (optional)

Required columns:

- `month` (YYYY-MM or YYYY-MM-DD)
- `campaign_name`
- `planned_budget`

Optional columns:

- `spend_to_date`
- `projected_spend`
- `pacing_percent`
- `parishes` (comma-separated)
- `platform`

Example:

```csv
month,campaign_name,planned_budget,parishes,platform
2024-10,Launch,1200,"Kingston,St Andrew",Meta
```

## Notes

- If parish metrics are omitted, parish totals are derived from campaign rows.
- Currency defaults to `JMD` unless provided in campaign/parish rows.
- The upload adapter only returns data when a tenant has uploaded CSVs.
- Downloadable templates live in `frontend/public/templates/`.

## Troubleshooting

- 400 "CSV validation failed": check required columns, date formats, and numeric fields.
- Dashboards still show live/demo data: toggle "Use uploaded data" in the UI.

## See also

- `docs/runbooks/quick-demo.md`
- `docs/runbooks/demo-data.md`
