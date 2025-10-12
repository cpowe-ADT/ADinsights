from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AuditLog, Role, Tenant, TenantKey, User, UserRole


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Tenant", {"fields": ("tenant", "timezone")}),)
    list_display = ("email", "tenant", "is_active", "is_staff")
    list_filter = ("tenant", "is_staff")


admin.site.register(Tenant)
admin.site.register(Role)
admin.site.register(UserRole)
admin.site.register(TenantKey)
admin.site.register(AuditLog)
