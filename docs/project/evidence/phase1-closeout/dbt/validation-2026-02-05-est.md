# dbt Validation Evidence

Timestamp: 2026-02-05 23:15 EST (America/Jamaica)

## Commands executed

```bash
make dbt-deps
DBT_PROFILES_DIR=dbt dbt run --project-dir dbt --select staging
DBT_PROFILES_DIR=dbt dbt snapshot --project-dir dbt
DBT_PROFILES_DIR=dbt dbt run --project-dir dbt --select marts
```

## Result

- Status: PASS
- `deps`: PASS (no package dependencies declared).
- `staging`: PASS.
- `snapshot`: PASS.
- `marts`: PASS.

## Fix applied during validation

- File: `dbt/models/marts/demo/vw_demo_dashboard_snapshot.sql`
- Change: `parish_rows_json` grouping updated from `group by 1, 2` to `group by 1`.
- Reason: DuckDB rejected ordinal `2` because it resolves to an aggregate expression.

## Notes

- The canonical repo gate command (`dbt --project-dir dbt run ...`) is not compatible with dbt 1.11 CLI syntax in this environment; equivalent successful command sequence is recorded above.
