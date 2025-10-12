# Superset BI Project

This directory contains declarative exports compatible with Apache Superset's [import/export](https://superset.apache.org/docs/administration/importing-exporting-datasources/) features. Import these YAML files through the Superset UI (Settings → Import/Export) or via the Superset CLI in CI/CD pipelines.

## Contents

- `datasets/` contains definitions for the warehouse models that power pacing dashboards.
- `dashboards/` includes curated dashboards for campaign pacing, creative effectiveness, and budget health.
- `subscriptions/` stores alert & report schedules for email and Slack delivery.

All exports were generated using Superset 3.1's native export tool with the `yaml` format enabled.
