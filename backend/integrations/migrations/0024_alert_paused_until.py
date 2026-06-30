"""Add paused_until to AlertRuleDefinition for time-bounded pause/resume."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0023_clientsuggestionsnapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="alertruledefinition",
            name="paused_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
