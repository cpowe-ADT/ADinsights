from __future__ import annotations

from django.contrib import admin

from .models import PlatformCredential


@admin.register(PlatformCredential)
class PlatformCredentialAdmin(admin.ModelAdmin):
    list_display = ("tenant", "provider", "account_id", "expires_at", "updated_at")
    list_filter = ("provider", "tenant")
    search_fields = ("account_id",)
