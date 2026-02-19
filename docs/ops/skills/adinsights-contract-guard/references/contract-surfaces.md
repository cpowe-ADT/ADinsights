# Contract Surfaces

Canonical contract surfaces for ADinsights contract classification.

## API Contract Surface
- `backend/**/serializers.py`
- `backend/**/views.py`
- `backend/**/urls.py`
- `backend/**/schema*.py`
- Documentation anchor: `docs/project/api-contract-changelog.md`

## Data Contract Surface
- `dbt/models/**/*.sql`
- `dbt/models/**/*.yml`
- `dbt/snapshots/**/*.sql`
- `dbt/snapshots/**/*.yml`
- Documentation anchor: `docs/project/integration-data-contract-matrix.md`

## Integration Contract Surface
- `infrastructure/airbyte/**`
- `integrations/**`
- Validation script: `python3 infrastructure/airbyte/scripts/check_data_contracts.py`

## Rule of Use
- If any contract surface is touched, this skill must classify risk.
- Missing contract-doc updates promotes status to `ESCALATE_CONTRACT_CHANGE_REQUIRES_DOCS`.
- Breaking signals promote status to `ESCALATE_BREAKING_CHANGE`.
