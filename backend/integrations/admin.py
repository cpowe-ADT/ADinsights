from __future__ import annotations

from django.contrib import admin

from .models import (
    APIErrorLog,
    AlertRuleDefinition,
    CampaignBudget,
    Client,
    ClientPlatformAccount,
    MetaConnection,
    MetaInsightPoint,
    MetaMetricRegistry,
    MetaMetricSupportStatus,
    MetaAccountSyncState,
    MetaPage,
    MetaPost,
    MetaPostInsightPoint,
    PlatformCredential,
)


class ClientPlatformAccountInline(admin.TabularInline):
    model = ClientPlatformAccount
    fk_name = "client"
    extra = 0
    fields = ("platform", "external_id", "display_name", "is_primary")
    ordering = ("platform", "external_id")


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "tenant", "industry", "parish", "is_active", "updated_at")
    list_filter = ("tenant", "is_active", "industry", "parish")
    search_fields = ("name", "slug", "industry")
    ordering = ("tenant", "name")
    inlines = [ClientPlatformAccountInline]


@admin.register(ClientPlatformAccount)
class ClientPlatformAccountAdmin(admin.ModelAdmin):
    list_display = (
        "platform",
        "external_id",
        "display_name",
        "client",
        "tenant",
        "is_primary",
        "updated_at",
    )
    list_filter = ("platform", "tenant", "is_primary")
    search_fields = ("external_id", "display_name", "client__name", "client__slug")
    ordering = ("tenant", "client", "platform", "external_id")


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


@admin.register(MetaConnection)
class MetaConnectionAdmin(admin.ModelAdmin):
    list_display = ("tenant", "user", "app_scoped_user_id", "token_expires_at", "is_active")
    list_filter = ("tenant", "is_active")
    search_fields = ("app_scoped_user_id", "user__email")


@admin.register(MetaPage)
class MetaPageAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "page_id",
        "name",
        "category",
        "can_analyze",
        "is_default",
        "last_synced_at",
        "updated_at",
    )
    list_filter = ("tenant", "can_analyze", "is_default")
    search_fields = ("page_id", "name")


@admin.register(MetaMetricRegistry)
class MetaMetricRegistryAdmin(admin.ModelAdmin):
    list_display = ("level", "metric_key", "status", "replacement_metric_key", "is_default")
    list_filter = ("level", "status", "is_default")
    search_fields = ("metric_key", "replacement_metric_key")


@admin.register(MetaMetricSupportStatus)
class MetaMetricSupportStatusAdmin(admin.ModelAdmin):
    list_display = ("tenant", "page", "level", "metric_key", "supported", "last_checked_at")
    list_filter = ("level", "supported")
    search_fields = ("metric_key", "page__page_id")


@admin.register(MetaInsightPoint)
class MetaInsightPointAdmin(admin.ModelAdmin):
    list_display = ("tenant", "page", "metric_key", "period", "end_time", "breakdown_key")
    list_filter = ("period", "metric_key")
    search_fields = ("metric_key", "page__page_id")


@admin.register(MetaPost)
class MetaPostAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "page",
        "post_id",
        "media_type",
        "created_time",
        "updated_time",
        "last_synced_at",
    )
    list_filter = ("tenant",)
    search_fields = ("post_id", "page__page_id")


@admin.register(MetaPostInsightPoint)
class MetaPostInsightPointAdmin(admin.ModelAdmin):
    list_display = ("tenant", "post", "metric_key", "period", "end_time", "breakdown_key")
    list_filter = ("period", "metric_key")
    search_fields = ("metric_key", "post__post_id")


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
