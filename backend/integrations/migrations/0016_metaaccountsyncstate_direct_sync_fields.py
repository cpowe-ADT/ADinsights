from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0015_alter_airbyteconnection_provider_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="metaaccountsyncstate",
            name="last_data_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="metaaccountsyncstate",
            name="last_error_category",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="metaaccountsyncstate",
            name="last_rows_synced",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="metaaccountsyncstate",
            name="last_sync_engine",
            field=models.CharField(
                blank=True,
                choices=[("airbyte", "Airbyte"), ("direct", "Direct")],
                default="airbyte",
                max_length=16,
            ),
        ),
    ]
