from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_alter_role_name"),
        ("analytics", "0005_googleadsexportjob_googleadssavedview"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DashboardDefinition",
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
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "template_key",
                    models.CharField(
                        choices=[
                            ("meta_executive_overview", "Meta executive overview"),
                            ("meta_campaign_performance", "Meta campaign performance"),
                            ("meta_creative_insights", "Meta creative insights"),
                            ("meta_budget_pacing", "Meta budget pacing"),
                            ("meta_parish_map", "Meta parish map"),
                        ],
                        default="meta_campaign_performance",
                        max_length=64,
                    ),
                ),
                ("filters", models.JSONField(blank=True, default=dict)),
                ("layout", models.JSONField(blank=True, default=dict)),
                (
                    "default_metric",
                    models.CharField(
                        choices=[
                            ("spend", "Spend"),
                            ("impressions", "Impressions"),
                            ("reach", "Reach"),
                            ("clicks", "Clicks"),
                            ("conversions", "Conversions"),
                            ("roas", "ROAS"),
                            ("ctr", "CTR"),
                            ("cpc", "CPC"),
                            ("cpm", "CPM"),
                            ("cpa", "CPA"),
                            ("frequency", "Frequency"),
                        ],
                        default="spend",
                        max_length=32,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_dashboard_definitions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dashboard_definitions",
                        to="accounts.tenant",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_dashboard_definitions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-updated_at", "name"),
            },
        ),
        migrations.AddIndex(
            model_name="dashboarddefinition",
            index=models.Index(
                fields=["tenant", "template_key"], name="analytics_dash_tenant_tpl"
            ),
        ),
        migrations.AddIndex(
            model_name="dashboarddefinition",
            index=models.Index(
                fields=["tenant", "is_active"], name="analytics_dash_tenant_active"
            ),
        ),
    ]
