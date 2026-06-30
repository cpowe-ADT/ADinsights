"""Add dismissed_at + dismissed_by audit fields to GoogleAdsSdkRecommendation."""

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0024_alert_paused_until"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="googleadssdkrecommendation",
            name="dismissed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="googleadssdkrecommendation",
            name="dismissed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="google_ads_recommendation_dismissals",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
