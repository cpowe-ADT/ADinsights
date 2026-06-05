"""Sprint 9a: persisted snapshot of the latest suggest_clients() run per tenant."""

import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_alter_role_name"),
        ("integrations", "0022_client_clientplatformaccount_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ClientSuggestionSnapshot",
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
                (
                    "trigger_reason",
                    models.CharField(
                        choices=[
                            ("meta_sync", "Meta sync"),
                            ("google_sync", "Google sync"),
                            ("manual", "Manual refresh"),
                        ],
                        default="manual",
                        max_length=32,
                    ),
                ),
                ("threshold", models.FloatField(default=0.7)),
                ("suggestion_count", models.PositiveIntegerField(default=0)),
                ("payload", models.JSONField(blank=True, default=list)),
                (
                    "generated_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                ("acknowledged_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="client_suggestion_snapshot",
                        to="accounts.tenant",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["tenant", "acknowledged_at"],
                        name="client_sugg_tenant_ack",
                    ),
                ],
            },
        ),
    ]
