from __future__ import annotations

from typing import Any

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .audit import log_audit_event
from .models import Tenant, User


@receiver(user_logged_in)
def log_login(sender: Any, user: User, request, **kwargs):  # noqa: ANN401 - Django signal signature
    tenant: Tenant | None = getattr(user, "tenant", None)
    if tenant is None:
        return
    metadata: dict[str, Any] = {}
    if request is not None:
        ip_address = request.META.get("REMOTE_ADDR")
        if ip_address:
            metadata["ip_address"] = ip_address
    log_audit_event(
        tenant=tenant,
        user=user,
        action="login",
        resource_type="auth",
        resource_id=user.id,
        metadata=metadata,
    )
