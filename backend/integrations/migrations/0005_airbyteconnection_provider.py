from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0004_alertruledefinition_campaignbudget"),
    ]

    operations = [
        migrations.AddField(
            model_name="airbyteconnection",
            name="provider",
            field=models.CharField(
                blank=True,
                choices=[
                    ("META", "Meta"),
                    ("GOOGLE", "Google Ads"),
                    ("LINKEDIN", "LinkedIn"),
                    ("TIKTOK", "TikTok"),
                ],
                max_length=16,
                null=True,
            ),
        ),
    ]
