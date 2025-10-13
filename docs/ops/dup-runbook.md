# Duplicate dbt Artifact Runbook

This runbook documents how to detect and remediate duplicate dbt artifacts that can cause merge conflicts or compilation failures. The `scripts/ci/check-duplications.sh` helper surfaces three classes of conflicts:

* dbt model files that share the same filename (for example, `dim_campaign.sql` defined in two folders)
* Macro definitions that reuse an existing macro name
* Schema test definitions (`name:` fields under `tests:` blocks) that collide across schema YAML files

## Running the duplication check locally

1. Ensure you are in the repository root.
2. Run the CI helper script:
   ```sh
   bash scripts/ci/check-duplications.sh
   ```
3. The script exits with status `0` when the tree is clean and prints the summary `No duplicate dbt models, macros, or schema test names detected.`.
4. If duplicates exist, the script exits `1` and prints each conflicting name together with the files (and line numbers for macros/tests) that must be resolved.

> The script uses only POSIX-friendly tooling and Python, so it runs anywhere our dbt project does.

## Remediating failures

When the duplication checker fails:

1. **Review the output** to understand the type of conflict.
   * *Model filename conflicts*: Rename one of the models or consolidate the logic into a single definition. Update downstream `ref()` calls if the model name changes.
   * *Macro name conflicts*: Rename the macro or delete the redundant definition. Remember to update any `{{ macro(...) }}` invocations if you rename it.
   * *Schema test name conflicts*: Adjust the `name:` field of the data test so that it is unique across the project. If the test is obsolete, remove it instead.
2. **Re-run the checker** (`bash scripts/ci/check-duplications.sh`) to confirm the conflict is resolved.
3. **Commit and push** the fix so the Docs workflow (and any pre-commit hooks) pass without manual intervention.

Escalate in `#adinsights-data` if you are unsure whether a duplicated artifact can be safely removed. Document the resolution in the associated incident or PR description for future reference.
