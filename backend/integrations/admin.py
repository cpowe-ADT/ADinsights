from __future__ import annotations

from django.contrib import admin

from .models import (
    APIErrorLog,
    AlertRuleDefinition,
    CampaignBudget,
    MetaAccountSyncState,
    PlatformCredential,
)


@admin.register(PlatformCredential)
class PlatformCredentialAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "provider",
        "account_id",
        "auth_mode",
        "token_status",
        "expires_at",
        "updated_at",
    )
    list_filter = ("provider", "tenant", "auth_mode", "token_status")
    search_fields = ("account_id",)


@admin.register(MetaAccountSyncState)
class MetaAccountSyncStateAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "account_id",
        "last_job_status",
        "last_success_at",
        "updated_at",
    )
    list_filter = ("tenant", "last_job_status")
    search_fields = ("account_id",)


@admin.register(APIErrorLog)
class APIErrorLogAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "provider",
        "account_id",
        "endpoint",
        "status_code",
        "is_retryable",
        "created_at",
    )
    list_filter = ("tenant", "provider", "status_code", "is_retryable")
    search_fields = ("account_id", "endpoint", "error_code", "correlation_id")


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
