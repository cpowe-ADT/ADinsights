DBT_PROJECT_DIR ?= dbt
DBT_PROFILES_DIR ?= $(DBT_PROJECT_DIR)
DBT ?= dbt --project-dir $(DBT_PROJECT_DIR) --profiles-dir $(DBT_PROFILES_DIR)

.PHONY: dbt-deps dbt-seed dbt-build dbt-test dbt-freshness dbt-docs dbt-build-full

dbt-deps:
	$(DBT) deps

dbt-seed:
	$(DBT) seed

dbt-build:
	$(DBT) build

dbt-test:
	$(DBT) test

dbt-freshness:
	$(DBT) source freshness --select source:raw

dbt-docs:
	$(DBT) docs generate

dbt-build-full:
	$(DBT) build --full-refresh
