DBT_PROJECT_DIR ?= dbt
DBT_PROFILES_DIR ?= $(DBT_PROJECT_DIR)
DBT ?= dbt
DBT_WRAPPER := ./scripts/dbt-wrapper.sh

define RUN_DBT
$(DBT_WRAPPER) '$(DBT)' '$(DBT_PROJECT_DIR)' '$(DBT_PROFILES_DIR)' $(1)
endef

.PHONY: dbt-deps dbt-seed dbt-build dbt-test dbt-freshness dbt-docs dbt-build-full

dbt-deps:
	$(call RUN_DBT,deps)

dbt-seed:
	$(call RUN_DBT,seed)

dbt-build:
	$(call RUN_DBT,build)

dbt-test:
	$(call RUN_DBT,test)

dbt-freshness:
	$(call RUN_DBT,source freshness --select source:raw)

dbt-docs:
	$(call RUN_DBT,docs generate)

dbt-build-full:
	$(call RUN_DBT,build --full-refresh)
