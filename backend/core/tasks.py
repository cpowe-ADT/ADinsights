from __future__ import annotations

import logging
from typing import Optional

from celery import shared_task

from core.crypto.dek_manager import rotate_all_tenant_deks
from accounts.audit import log_audit_event
from accounts.models import Tenant, User
from integrations.models import PlatformCredential

logger = logging.getLogger(__name__)


@shared_task
def rotate_deks() -> str:
    rotated = rotate_all_tenant_deks()
    return f"rotated {rotated} tenant keys"


def _resolve_user(user_id: Optional[str]) -> Optional[User]:
    if not user_id:
        return None
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None


@shared_task
def sync_meta_example(tenant_id: str, triggered_by_user_id: Optional[str] = None) -> str:
    logger.info("Simulating Meta sync")
    tenant = Tenant.objects.get(id=tenant_id)
    user = _resolve_user(triggered_by_user_id)
    log_audit_event(
        tenant=tenant,
        user=user,
        action="sync_triggered",
        resource_type="sync",
        resource_id=PlatformCredential.META,
        metadata={"provider": PlatformCredential.META},
    )
    return "meta_sync_triggered"


@shared_task
def sync_google_example(tenant_id: str, triggered_by_user_id: Optional[str] = None) -> str:
    logger.info("Simulating Google sync")
    tenant = Tenant.objects.get(id=tenant_id)
    user = _resolve_user(triggered_by_user_id)
    log_audit_event(
        tenant=tenant,
        user=user,
        action="sync_triggered",
        resource_type="sync",
        resource_id=PlatformCredential.GOOGLE,
        metadata={"provider": PlatformCredential.GOOGLE},
    )
    return "google_sync_triggered"
