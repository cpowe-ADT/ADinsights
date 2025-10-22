from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0006_airbytejobtelemetry"),
    ]

    operations = [
        migrations.AddField(
            model_name="airbyteconnection",
            name="last_job_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="airbyteconnection",
            name="last_job_error",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="airbyteconnection",
            name="last_job_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tenantairbytesyncstatus",
            name="last_job_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tenantairbytesyncstatus",
            name="last_job_error",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="tenantairbytesyncstatus",
            name="last_job_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
