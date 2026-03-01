from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from integrations.google_ads.field_reference import ingest_fields_reference_file


class Command(BaseCommand):
    help = (
        "Parse Google Ads segments/metrics field reference text and persist it as a "
        "normalized JSON file under backend/integrations/data/."
    )

    def add_arguments(self, parser):  # noqa: ANN001 - Django command signature
        parser.add_argument(
            "--input",
            required=True,
            help="Path to raw Google Ads segments/metrics field reference text.",
        )
        parser.add_argument(
            "--output",
            required=False,
            help="Optional output path for the normalized JSON payload.",
        )
        parser.add_argument(
            "--api-version",
            default="v23",
            help="Google Ads API version label for metadata (default: v23).",
        )

    def handle(self, *args, **options):  # noqa: ANN002, ANN003 - Django command signature
        input_path = Path(str(options["input"])).expanduser()
        if not input_path.exists():
            raise CommandError(f"Input file does not exist: {input_path}")
        if not input_path.is_file():
            raise CommandError(f"Input path must be a file: {input_path}")

        output_raw = options.get("output")
        output_path = Path(str(output_raw)).expanduser() if output_raw else None
        version = str(options.get("api_version") or "v23").strip() or "v23"

        payload = ingest_fields_reference_file(
            input_path=input_path,
            output_path=output_path,
            version=version,
        )
        counts = payload.get("counts", {})
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported Google Ads fields reference ({version}) with "
                f"{payload.get('total_fields', 0)} fields."
            )
        )
        self.stdout.write(f"- segments: {counts.get('segments', 0)}")
        self.stdout.write(f"- metrics: {counts.get('metrics', 0)}")
