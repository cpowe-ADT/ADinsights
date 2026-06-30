"""Provision Content Ops publishing identities from connected Meta pages.

This bridges the existing Meta *connection* data (managed by the ``integrations``
app) into the ``content_ops`` publishing surface: every connected Facebook Page
becomes a :class:`PublishingIdentity` that the composer and scheduler can target,
without anyone hand-creating identities through the API.

Scope notes:

* Integrations models are read **read-only** here; only ``content_ops`` rows are
  written, keeping this change within the ``content_ops`` folder boundary.
* Instagram identities require the linked IG business-account id, which is not
  yet persisted in the integrations layer (it is only fetched live from the
  Graph API). Until that linkage is stored, Instagram destinations are
  provisioned separately, so this sync covers Facebook Pages only.
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


def sync_publishing_identities_for_tenant(*, tenant) -> IdentitySyncResult:
    """Upsert Facebook Page publishing identities for one tenant.

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
        identity, was_created = PublishingIdentity.all_objects.get_or_create(
            tenant=tenant,
            platform=PublishingIdentity.PLATFORM_FACEBOOK_PAGE,
            meta_page_id=page.page_id,
            ig_user_id="",
            defaults={
                "display_name": page.name,
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
            created += 1
            if identity.selection_state == PublishingIdentity.SELECTION_SELECTED:
                selected += 1
            continue

        changed_fields: list[str] = []
        if identity.display_name != page.name:
            identity.display_name = page.name
            changed_fields.append("display_name")
        if credential is not None and identity.credential_ref_id != credential.id:
            identity.credential_ref = credential
            changed_fields.append("credential_ref")
        # Promote a never-decided destination, but respect an explicit revoke.
        if (
            publishable
            and identity.selection_state == PublishingIdentity.SELECTION_NOT_SELECTED
        ):
            identity.selection_state = PublishingIdentity.SELECTION_SELECTED
            changed_fields.append("selection_state")
            selected += 1
        if changed_fields:
            changed_fields.append("updated_at")
            identity.save(update_fields=changed_fields)
            updated += 1

    return IdentitySyncResult(
        total_pages=len(pages),
        created=created,
        updated=updated,
        selected=selected,
    )
