# Alerting Workflow Runbook

## Overview

Alerting is driven by SQL thresholds defined in `backend/app/alerts.py`. Rules are evaluated every 15 minutes by the Celery beat scheduler and results are summarized by the LLM integration before being dispatched to Slack/email. Each evaluation is persisted to the `alerts_alertrun` table and exposed via `GET /api/alerts/runs/` for historical analysis.

## Manual Execution

```bash
curl -X POST https://api.<env>.adinsights.com/alerts/run
```

This triggers the `run_alert_cycle` task and posts results to the configured channels.

## Adding a New Rule

1. Create a new `AlertRule` entry in `backend/app/alerts.py` with SQL scoped to the relevant dataset.
2. Include a clear description, threshold, and channels.
3. Add supporting visualizations in Superset so analysts can investigate quickly.
4. Deploy and validate by running the manual execution command above.

## LLM Summaries

- Endpoint: `ADINSIGHTS_LLM_API_URL`
- Model: `gpt-5-codex`
- Prompt: Summaries capped at 120 words with tactical next steps.
- Fallback: If the LLM request fails, alerts still log the raw payload for manual review.

## Integration Points

- Slack webhook(s) managed in 1Password.
- Email distribution lists maintained in Google Workspace (`marketing-ops@example.com`).
- DB credentials rotate via Vault every 90 days.
