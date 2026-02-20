from __future__ import annotations

from typing import Iterable

from django.db import transaction
from django.utils import timezone

from integrations.meta_page_insights.meta_client import MetaPageInsightsClient
from integrations.models import MetaConnection, MetaPage, PlatformCredential

PAGE_ANALYZE_TASK = "ANALYZE"
PAGE_INSIGHTS_PERMISSION_FALLBACK = {"ADMINISTER", "BASIC_ADMIN", "CREATE_ADS"}


def sync_pages_for_connection(connection_id: str) -> list[MetaPage]:
    meta_connection = MetaConnection.all_objects.filter(pk=connection_id).select_related("tenant").first()
    if meta_connection is not None:
        return _sync_pages(
            tenant=meta_connection.tenant,
            user_token=meta_connection.decrypt_token(),
            connection=meta_connection,
        )

    platform_credential = (
        PlatformCredential.all_objects.filter(pk=connection_id, provider=PlatformCredential.META)
        .select_related("tenant")
        .first()
    )
    if platform_credential is None:
        return []

    return _sync_pages(
        tenant=platform_credential.tenant,
        user_token=platform_credential.decrypt_access_token(),
        connection=None,
    )


def _sync_pages(*, tenant, user_token: str | None, connection: MetaConnection | None) -> list[MetaPage]:
    if not user_token:
        return []

    with MetaPageInsightsClient.from_settings() as client:
        pages = client.fetch_pages_for_user(user_access_token=user_token)

    analyze_candidates = [
        page
        for page in pages
        if _has_page_insights_capability(tasks=page.tasks, perms=page.perms)
    ]
    if not analyze_candidates:
        return []

    default_exists = MetaPage.all_objects.filter(tenant=tenant, is_default=True).exists()
    saved_pages: list[MetaPage] = []
    now = timezone.now()
    with transaction.atomic():
        for index, page in enumerate(analyze_candidates):
            if not page.access_token:
                continue
            tasks = _clean_string_list(page.tasks)
            perms = _clean_string_list(page.perms)
            meta_page, _ = MetaPage.all_objects.select_for_update().get_or_create(
                tenant=tenant,
                page_id=page.id,
                defaults={
                    "name": page.name,
                    "category": page.category or "",
                    "connection": connection,
                    "can_analyze": True,
                    "tasks": tasks,
                    "perms": perms,
                    "is_default": (not default_exists and index == 0),
                },
            )
            meta_page.connection = connection
            meta_page.name = page.name
            meta_page.category = page.category or ""
            meta_page.can_analyze = True
            meta_page.tasks = tasks
            meta_page.perms = perms
            meta_page.page_token_expires_at = now
            if not default_exists and index == 0:
                meta_page.is_default = True
            meta_page.set_raw_page_token(page.access_token)
            meta_page.save()
            saved_pages.append(meta_page)
    return saved_pages


def _clean_string_list(values: Iterable[str] | None) -> list[str]:
    if not values:
        return []
    return [value for value in values if isinstance(value, str) and value.strip()]


def _has_page_insights_capability(*, tasks: Iterable[str] | None, perms: Iterable[str] | None) -> bool:
    task_set = {value.strip().upper() for value in (tasks or []) if isinstance(value, str) and value.strip()}
    if PAGE_ANALYZE_TASK in task_set:
        return True

    perm_set = {value.strip().upper() for value in (perms or []) if isinstance(value, str) and value.strip()}
    return bool(perm_set.intersection(PAGE_INSIGHTS_PERMISSION_FALLBACK))
