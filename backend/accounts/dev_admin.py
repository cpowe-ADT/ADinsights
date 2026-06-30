from __future__ import annotations

import os
import uuid

from .models import Tenant


def _normalized_tenant_id(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    try:
        return str(uuid.UUID(candidate))
    except ValueError:
        return None


def resolve_default_tenant() -> Tenant:
    tenant_name = os.environ.get("DJANGO_DEFAULT_TENANT_NAME", "Default Tenant").strip() or "Default Tenant"
    tenant_id = _normalized_tenant_id(os.environ.get("DJANGO_DEFAULT_TENANT_ID"))
    if tenant_id:
        tenant, _ = Tenant.objects.update_or_create(
            id=tenant_id,
            defaults={"name": tenant_name},
        )
        return tenant
    tenant, _ = Tenant.objects.get_or_create(name=tenant_name)
    return tenant
