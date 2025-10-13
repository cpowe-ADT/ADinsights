# SLO & SLI Catalog

The service level objectives (SLOs) below ensure our delivery pipelines and supporting tooling meet stakeholder expectations. Each SLO is paired with a measurable service level indicator (SLI) sourced from CI/CD outputs or monitoring artifacts.

## Backend CI

* **SLO:** 99% of Backend CI runs on `main` complete successfully each rolling 30-day window.
  * **SLI source:** GitHub Actions workflow conclusion status aggregated via the `backend-ci-summary.json` artifact that our nightly job downloads and stores in BigQuery.
* **SLO:** Median runtime stays under 12 minutes for Backend CI during business hours.
  * **SLI source:** `ci-metrics.csv` artifact emitted by the `Publish backend timings` step, parsed by the metrics ETL.

## Frontend CI

* **SLO:** 98% of Frontend CI runs upload the `frontend-dist.zip` artifact without warnings.
  * **SLI source:** Artifact manifest recorded in the `frontend-ci-artifacts.json` output published in each run summary.
* **SLO:** P95 job duration remains under 18 minutes during peak PR hours (14:00–22:00 UTC).
  * **SLI source:** GitHub Actions usage export enriched by the `ci-usage-normalizer` script, ingested nightly.

## dbt CI

* **SLO:** All dbt workflow runs triggered by PRs produce the `dbt-staging-artifacts` bundle (target 100%).
  * **SLI source:** Presence flag in the `artifact-inventory.json` step output.
* **SLO:** No more than 3% of dbt CI runs fail due to schema drift within a 30-day window.
  * **SLI source:** Tagged failure reason in the `dbt-ci-summary.ndjson` log emitted at the end of each run.

## Docs & Auxiliary workflows

* **SLO:** Docs CI maintains a 99.5% success rate for lint-only runs on `main`.
  * **SLI source:** Workflow conclusion field collected via the nightly GitHub Actions export and filtered by workflow name.
* **SLO:** Observability smoke tests finish in under 8 minutes 95% of the time.
  * **SLI source:** Duration column in the `observability-health.csv` artifact produced by the monitoring job.
