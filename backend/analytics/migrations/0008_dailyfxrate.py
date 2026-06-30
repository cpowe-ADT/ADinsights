"""Sprint 6 of Client grouping: daily FX rate table for combined-view conversion."""

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0007_reportdefinition_delivery_emails_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="DailyFxRate",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("rate_date", models.DateField()),
                ("base_currency", models.CharField(max_length=8)),
                ("quote_currency", models.CharField(max_length=8)),
                ("rate", models.DecimalField(decimal_places=8, max_digits=18)),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("manual", "Manual"),
                            ("openexchangerates", "Open Exchange Rates"),
                            ("ecb", "European Central Bank"),
                            ("boj", "Bank of Jamaica"),
                        ],
                        default="manual",
                        max_length=32,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("-rate_date", "base_currency", "quote_currency"),
                "unique_together": {("rate_date", "base_currency", "quote_currency")},
            },
        ),
        migrations.AddIndex(
            model_name="dailyfxrate",
            index=models.Index(
                fields=["base_currency", "quote_currency", "-rate_date"],
                name="analytics_fx_pair_date",
            ),
        ),
    ]
