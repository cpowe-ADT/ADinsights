from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from integrations.models import MetaMetricRegistry
from integrations.services.meta_metric_catalog import (
    load_metric_catalog,
    metric_catalog_doc_path,
    render_metric_catalog_markdown,
)


class Command(BaseCommand):
    help = "Sync Meta metric catalog definitions into MetaMetricRegistry."

    def add_arguments(self, parser):  # noqa: ANN001
        parser.add_argument(
            "--write-docs",
            action="store_true",
            help="Also regenerate docs/project/meta-page-insights-metric-catalog.md",
        )

    def handle(self, *args, **options):  # noqa: ANN001, ANN002
        catalog = load_metric_catalog()
        created_count = 0
        updated_count = 0

        for definition in catalog:
            metadata: dict[str, Any] = {}
            deprecated_on = str(definition.get("deprecated_on", "")).strip()
            if deprecated_on:
                metadata["deprecated_on"] = deprecated_on

            _, created = MetaMetricRegistry.objects.update_or_create(
                metric_key=definition["metric_key"],
                level=definition["level"],
                defaults={
                    "supported_periods": definition["supported_periods"],
                    "supports_breakdowns": definition["supports_breakdowns"],
                    "status": definition["status"],
                    "replacement_metric_key": definition["replacement_metric_key"],
                    "is_default": definition["is_default"],
                    "metadata": metadata,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        if bool(options.get("write_docs")):
            output_path = metric_catalog_doc_path()
            output_path.write_text(render_metric_catalog_markdown(catalog))
            self.stdout.write(self.style.SUCCESS(f"Regenerated metric catalog doc: {output_path}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Synced {len(catalog)} metric definitions (created={created_count}, updated={updated_count})."
            )
        )
