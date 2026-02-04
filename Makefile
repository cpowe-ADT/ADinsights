DBT_PROJECT_DIR ?= dbt
DBT_PROFILES_DIR ?= $(DBT_PROJECT_DIR)
DBT ?= dbt
DBT_WRAPPER := ./scripts/dbt-wrapper.sh
DEMO_SEED_DIR ?= dbt/seeds/demo
COMPOSE_ENV_FILE := $(if $(wildcard .env.dev.compose),--env-file .env.dev.compose,)
COMPOSE_CMD := docker compose $(COMPOSE_ENV_FILE) -f docker-compose.dev.yml

define RUN_DBT
$(DBT_WRAPPER) '$(DBT)' '$(DBT_PROJECT_DIR)' '$(DBT_PROFILES_DIR)' $(1)
endef

.PHONY: dbt-deps dbt-seed dbt-build dbt-test dbt-freshness dbt-docs dbt-build-full demo-data dbt-seed-demo demo-smoke

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

demo-data:
	python3 scripts/generate_demo_data.py --out $(DEMO_SEED_DIR) --days 90 --seed 42 --validate

dbt-seed-demo:
	$(call RUN_DBT,seed --select path:seeds/demo)

demo-smoke:
	python3 scripts/generate_demo_data.py --out $(DEMO_SEED_DIR) --days 30 --seed 42 --validate
	$(call RUN_DBT,seed --select path:seeds/demo)

.PHONY: dev dev-up dev-down dev-reset dev-seed dev-logs seed dev-bootstrap dev-ready dev-data dev-session

dev:
	$(COMPOSE_CMD) up

dev-up:
	$(COMPOSE_CMD) up -d --build

dev-down:
	$(COMPOSE_CMD) down --remove-orphans

dev-reset:
	$(COMPOSE_CMD) down -v --remove-orphans && $(COMPOSE_CMD) up --build

dev-seed:
	$(COMPOSE_CMD) exec -T backend python manage.py seed_dev_data

dev-logs:
	$(COMPOSE_CMD) logs -f

seed: dev-seed

dev-bootstrap: dev-down dev-up
	$(COMPOSE_CMD) exec -T backend python manage.py migrate --noinput
	$(COMPOSE_CMD) exec -T backend python manage.py seed_dev_data

dev-data:
	$(COMPOSE_CMD) exec -T backend python /app/scripts/generate_dev_data.py --days 21 --reset

dev-session:
	$(COMPOSE_CMD) exec -T backend python /app/scripts/create_dev_session.py --username devadmin@local.test --cookie

dev-ready: dev-bootstrap dev-data dev-session
