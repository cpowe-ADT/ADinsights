from __future__ import annotations

import logging

from celery import shared_task

from core.crypto.dek_manager import rotate_all_tenant_deks

logger = logging.getLogger(__name__)


@shared_task
def rotate_deks() -> str:
    rotated = rotate_all_tenant_deks()
    return f"rotated {rotated} tenant keys"


@shared_task
def sync_meta_example() -> str:
    logger.info("Simulating Meta sync")
    return "meta_sync_triggered"


@shared_task
def sync_google_example() -> str:
    logger.info("Simulating Google sync")
    return "google_sync_triggered"
