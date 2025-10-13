from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_invitation"),
        ("integrations", "0002_airbyteconnection"),
    ]

    operations = [
        migrations.CreateModel(
            name="TenantAirbyteSyncStatus",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("last_job_id", models.CharField(blank=True, max_length=64)),
                ("last_job_status", models.CharField(blank=True, max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "last_connection",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="tenant_sync_statuses",
                        to="integrations.airbyteconnection",
                    ),
                ),
                (
                    "tenant",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="airbyte_sync_status",
                        to="accounts.tenant",
                    ),
                ),
            ],
            options={
                "verbose_name": "Tenant Airbyte sync status",
                "verbose_name_plural": "Tenant Airbyte sync statuses",
            },
        ),
    ]
