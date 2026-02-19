# Evidence Sources

Release readiness synthesis should prioritize these evidence inputs:

1. Router packet (`adinsights-persona-router`): intent, ownership, escalation context.
2. Scope packet (`adinsights-scope-gatekeeper`): scope status, folder risk, reviewer routing.
3. Contract packet (`adinsights-contract-guard`): contract status, docs/tests/reviewers.
4. Required docs and runbooks:
   - `docs/runbooks/release-checklist.md`
   - `docs/runbooks/deployment.md`
   - `docs/runbooks/operations.md`
   - `docs/project/api-contract-changelog.md`
   - `docs/project/integration-data-contract-matrix.md`
5. Optional check commands from `release-gates.yaml` when `--run-checks` is requested.
