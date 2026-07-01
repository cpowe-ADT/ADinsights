"""Provision Content Ops publishing identities from connected Meta pages.

This bridges the existing Meta *connection* data (managed by the ``integrations``
app) into the ``content_ops`` publishing surface: every connected Facebook Page
becomes a :class:`PublishingIdentity` that the composer and scheduler can target,
without anyone hand-creating identities through the API.

Scope notes:

* Integrations models are read **read-only** here; only ``content_ops`` rows are
  written.
* Pages with a persisted linked Instagram professional account
  (``MetaPage.instagram_business_account_id``) also get an Instagram identity, so
  the composer can target Instagram once publishing scopes are granted.
"""

from __future__ import annotations

from dataclasses import dataclass

from integrations.models import MetaPage, PlatformCredential

from .models import PublishingIdentity

# Meta page ``tasks``/``perms`` entries that imply the page can publish content.
PUBLISHABLE_PAGE_CAPABILITIES = {"CREATE_CONTENT", "MANAGE"}


@dataclass(frozen=True)
class IdentitySyncResult:
    total_pages: int = 0
    created: int = 0
    updated: int = 0
    selected: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "total_pages": self.total_pages,
            "created": self.created,
            "updated": self.updated,
            "selected": self.selected,
        }


def _page_capabilities(page: MetaPage) -> set[str]:
    capabilities: set[str] = set()
    for source in (page.tasks, page.perms):
        if isinstance(source, list):
            capabilities.update(str(item).strip().upper() for item in source if item)
    return capabilities


def _page_is_publishable(page: MetaPage) -> bool:
    return page.is_default or bool(
        _page_capabilities(page) & PUBLISHABLE_PAGE_CAPABILITIES
    )


def _active_meta_credential(*, tenant) -> PlatformCredential | None:
    return (
        PlatformCredential.all_objects.filter(
            tenant=tenant,
            provider=PlatformCredential.META,
            token_status__in=[
                PlatformCredential.TOKEN_STATUS_VALID,
                PlatformCredential.TOKEN_STATUS_EXPIRING,
            ],
        )
        .order_by("-updated_at")
        .first()
    )


def _upsert_publishing_identity(
    *,
    tenant,
    platform: str,
    meta_page_id: str,
    ig_user_id: str,
    display_name: str,
    credential: PlatformCredential | None,
    publishable: bool,
) -> tuple[int, int, int]:
    """Create or refresh one publishing identity.

    Returns ``(created, updated, selected)`` deltas. Idempotent, and never
    overrides an explicit user revoke.
    """

    identity, was_created = PublishingIdentity.all_objects.get_or_create(
        tenant=tenant,
        platform=platform,
        meta_page_id=meta_page_id,
        ig_user_id=ig_user_id,
        defaults={
            "display_name": display_name,
            "credential_ref": credential,
            "selection_state": (
                PublishingIdentity.SELECTION_SELECTED
                if publishable
                else PublishingIdentity.SELECTION_NOT_SELECTED
            ),
            "publish_readiness_state": PublishingIdentity.READINESS_READY,
        },
    )
    if was_created:
        was_selected = identity.selection_state == PublishingIdentity.SELECTION_SELECTED
        return (1, 0, 1 if was_selected else 0)

    changed_fields: list[str] = []
    if display_name and identity.display_name != display_name:
        identity.display_name = display_name
        changed_fields.append("display_name")
    if credential is not None and identity.credential_ref_id != credential.id:
        identity.credential_ref = credential
        changed_fields.append("credential_ref")
    selected_delta = 0
    # Promote a never-decided destination, but respect an explicit revoke.
    if publishable and identity.selection_state == PublishingIdentity.SELECTION_NOT_SELECTED:
        identity.selection_state = PublishingIdentity.SELECTION_SELECTED
        changed_fields.append("selection_state")
        selected_delta = 1
    if changed_fields:
        changed_fields.append("updated_at")
        identity.save(update_fields=changed_fields)
        return (0, 1, selected_delta)
    return (0, 0, selected_delta)


def sync_publishing_identities_for_tenant(*, tenant) -> IdentitySyncResult:
    """Upsert Facebook Page and linked Instagram publishing identities for a tenant.

    Every connected Page becomes a Facebook Page identity; Pages with a persisted
    linked Instagram professional account also get an Instagram identity.
    Idempotent: re-running refreshes the display name and credential link and
    promotes never-decided destinations to selected, but it never overrides a
    destination a user has explicitly revoked.
    """

    credential = _active_meta_credential(tenant=tenant)
    pages = list(
        MetaPage.all_objects.filter(tenant=tenant).order_by("-is_default", "name")
    )
    created = 0
    updated = 0
    selected = 0
    for page in pages:
        publishable = _page_is_publishable(page)
        page_created, page_updated, page_selected = _upsert_publishing_identity(
            tenant=tenant,
            platform=PublishingIdentity.PLATFORM_FACEBOOK_PAGE,
            meta_page_id=page.page_id,
            ig_user_id="",
            display_name=page.name,
            credential=credential,
            publishable=publishable,
        )
        created += page_created
        updated += page_updated
        selected += page_selected

        ig_user_id = str(getattr(page, "instagram_business_account_id", "") or "").strip()
        if ig_user_id:
            ig_name = str(getattr(page, "instagram_username", "") or "").strip() or page.name
            ig_created, ig_updated, ig_selected = _upsert_publishing_identity(
                tenant=tenant,
                platform=PublishingIdentity.PLATFORM_INSTAGRAM,
                meta_page_id=page.page_id,
                ig_user_id=ig_user_id,
                display_name=ig_name,
                credential=credential,
                publishable=publishable,
            )
            created += ig_created
            updated += ig_updated
            selected += ig_selected

    return IdentitySyncResult(
        total_pages=len(pages),
        created=created,
        updated=updated,
        selected=selected,
    )
