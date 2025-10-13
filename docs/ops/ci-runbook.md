# CI Operations Runbook

This runbook explains how to triage and remediate failures in the repository's GitHub Actions pipelines. It covers the four path-scoped workflows that guard changes to the backend, frontend, dbt models, and documentation.

## Workflow reference

| Workflow | Trigger | Purpose |
| --- | --- | --- |
| **Backend CI** | Pull requests to `main` touching `backend/**` | Lint the Django project with Ruff and run the backend test suite. |
| **Frontend CI** | Pull requests to `main` touching `frontend/**` | Install npm dependencies, execute unit tests, and build the production bundle. |
| **dbt CI** | Pull requests to `main` touching `dbt/**` | Validate dbt dependencies and execute staging model builds against Postgres. |
| **Docs CI** | Pull requests that modify docs or the root README | Run lightweight Markdown sanity checks. |

## Inspecting workflow runs

1. Navigate to **GitHub → Actions** and filter by the workflow name that corresponds to the failing PR.
2. Open the most recent run and review the **Summary** tab first. The summary shows which jobs were skipped, which completed, and any outputs published by workflow commands.
3. Select the red ❌ job to drill in further.
4. Expand the failing step to review console output. Look for the command that exited with a non-zero code and copy any stack traces or error messages.

> Tip: Use the "Download log archive" link from the job summary when sharing logs in Slack or in incident tickets.

## Retrieving artifacts

* From the workflow **Summary** tab, scroll to the **Artifacts** section to download bundles such as `frontend-dist.zip`, `dbt-staging-artifacts`, or `backend-ci-summary.json`.
* The `dbt-staging-artifacts` bundle now includes compiled SQL (`dbt/target/compiled`), run logs (`dbt/logs/dbt.log`), docs metadata (`catalog.json`, `graph_summary.json`, and `semantic_manifest.json`), the standard `manifest.json`, `run_results.json`, `graph.gpickle`, `partial_parse.msgpack`, and the machine-readable `artifact-inventory.json` manifest generated in CI.
* Artifact names map to the validation steps in the logs. For example, the `Publish backend timings` step uploads `ci-metrics.csv`; confirm the upload succeeded before debugging runtime regressions.
* Inspect `artifact-inventory.json` to quickly list which staging models and schema tests ran in CI along with their statuses. This is useful when validating that optional connectors executed or when triaging flaky tests.
* If an artifact is missing, cross-check the job logs for `upload-artifact` failures (often due to size limits) and re-run the job once the issue is addressed.

## Rerunning jobs

* Use **Re-run failed jobs** when a transient error (network blip, GitHub outage, flaky dependency download) caused the failure. This preserves the same commit and executes only the failed jobs. In the run view, choose **Re-run jobs → Re-run failed jobs** so GitHub scopes the rerun to red steps only.
* Use **Re-run all jobs** after fixing a pipeline script, caching issue, or updating secrets so that you can confirm every step completes cleanly.
* If the workflow definition itself changed, push the fix and re-open the pull request to trigger a fresh run. Re-running a job does not load the new YAML.

## Common failure patterns

### Python or Node cache drift

Pip and npm caches speed up CI but occasionally hold on to corrupt or outdated artifacts. Bust the cache by incrementing the dependency hash:

1. Modify the relevant lockfile (`backend/requirements.txt` or `frontend/package-lock.json`) in a follow-up commit. Adding a blank comment at the end is sufficient.
2. Push the commit and re-run the workflow. The cache key will change and force a clean install.

Alternatively, set a temporary override in the workflow dispatch screen (use the `CI_DISABLE_CACHE=1` environment field) and re-run.

### Lockfile drift

When local lockfiles diverge from what CI expects, npm or pip will fail with hash mismatch errors.

1. Run the install command locally (`pip install -r backend/requirements.txt` or `npm ci` in `frontend/`).
2. Commit the regenerated lockfile and push to the PR.
3. Re-run the affected workflow to verify the new lockfile resolves.

### Backend test or lint failures

1. Reproduce locally with the same commands CI runs: `ruff check backend` and `pytest -q backend`.
2. Ensure that required environment variables are set. You can list them with `scripts/ci/print-env-keys.sh`.
3. Fix the failing tests or lint violations, commit, and push. The backend workflow will re-run automatically.

### dbt failures in staging builds

1. Download the dbt run logs from the job summary for context. Look for model names ending in `stg_*`.
2. Confirm the Postgres service is healthy by reviewing the `Wait for Postgres` step output.
3. Re-run the workflow. If it keeps failing, reproduce locally with `make dbt-deps && dbt --project-dir dbt run --select staging`.
4. Coordinate with the data team if source tables or credentials were changed.

### Markdown checker errors

* The Markdown sanity script flags headings without a space (e.g. `##Heading`) and empty links (for example, `[Example](missing-url)`). Edit the file to fix the syntax and rerun the Docs workflow.

## Escalation

* **Business hours:** notify the owning squad in `#adinsights-dev` and post a short summary with a link to the failing run.
* **Off hours:** create an incident in PagerDuty under "CI/CD" and include log excerpts plus the PR URL.

Record root cause and remediation notes in the associated ticket once the run completes successfully.
