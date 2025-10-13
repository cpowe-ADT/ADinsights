from __future__ import annotations

from django.contrib import admin

from .models import AlertRuleDefinition, CampaignBudget, PlatformCredential


@admin.register(PlatformCredential)
class PlatformCredentialAdmin(admin.ModelAdmin):
    list_display = ("tenant", "provider", "account_id", "expires_at", "updated_at")
    list_filter = ("provider", "tenant")
    search_fields = ("account_id",)


@admin.register(CampaignBudget)
class CampaignBudgetAdmin(admin.ModelAdmin):
    list_display = ("tenant", "name", "monthly_target", "currency", "is_active")
    list_filter = ("tenant", "currency", "is_active")
    search_fields = ("name",)


@admin.register(AlertRuleDefinition)
class AlertRuleDefinitionAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "name",
        "metric",
        "comparison_operator",
        "threshold",
        "lookback_hours",
        "severity",
        "is_active",
    )
    list_filter = ("tenant", "metric", "comparison_operator", "severity", "is_active")
    search_fields = ("name", "metric")
