from __future__ import annotations

import pytest
from django.core.management import call_command

from accounts.models import Tenant
from content_ops.identity_sync import sync_publishing_identities_for_tenant
from content_ops.models import PublishingIdentity
from integrations.models import MetaPage, PlatformCredential


def _meta_credential(tenant, scopes=None) -> PlatformCredential:
    credential = PlatformCredential(
        tenant=tenant,
        provider=PlatformCredential.META,
        account_id="act_123",
        granted_scopes=scopes if scopes is not None else ["pages_manage_posts"],
    )
    credential.set_raw_tokens("meta-access-token", None)
    credential.save()
    return credential


def _meta_page(
    tenant,
    *,
    page_id: str,
    name: str,
    is_default: bool = False,
    perms=None,
    tasks=None,
) -> MetaPage:
    page = MetaPage(
        tenant=tenant,
        page_id=page_id,
        name=name,
        can_analyze=True,
        is_default=is_default,
        perms=perms if perms is not None else [],
        tasks=tasks if tasks is not None else [],
    )
    page.set_raw_page_token("page-access-token")
    page.save()
    return page


@pytest.mark.django_db
def test_sync_creates_selected_facebook_identities_for_publishable_pages(tenant):
    credential = _meta_credential(tenant)
    _meta_page(tenant, page_id="page_default", name="Default Page", is_default=True)
    _meta_page(
        tenant, page_id="page_creator", name="Creator Page", perms=["CREATE_CONTENT"]
    )
    _meta_page(tenant, page_id="page_readonly", name="Readonly Page", perms=["ANALYZE"])

    result = sync_publishing_identities_for_tenant(tenant=tenant)

    assert result.total_pages == 3
    assert result.created == 3
    assert result.selected == 2  # default + create_content capable

    identities = {
        identity.meta_page_id: identity
        for identity in PublishingIdentity.all_objects.filter(tenant=tenant)
    }
    assert set(identities) == {"page_default", "page_creator", "page_readonly"}
    assert (
        identities["page_default"].selection_state
        == PublishingIdentity.SELECTION_SELECTED
    )
    assert (
        identities["page_creator"].selection_state
        == PublishingIdentity.SELECTION_SELECTED
    )
    assert (
        identities["page_readonly"].selection_state
        == PublishingIdentity.SELECTION_NOT_SELECTED
    )
    assert identities["page_default"].credential_ref_id == credential.id
    assert identities["page_default"].display_name == "Default Page"
    # Facebook only — Instagram identities are not invented without a linked id.
    assert not PublishingIdentity.all_objects.filter(
        tenant=tenant, platform=PublishingIdentity.PLATFORM_INSTAGRAM
    ).exists()


@pytest.mark.django_db
def test_sync_is_idempotent_and_refreshes_display_name(tenant):
    _meta_credential(tenant)
    page = _meta_page(tenant, page_id="page_1", name="Original Name", is_default=True)

    first = sync_publishing_identities_for_tenant(tenant=tenant)
    assert first.created == 1

    MetaPage.all_objects.filter(id=page.id).update(name="Renamed Page")
    second = sync_publishing_identities_for_tenant(tenant=tenant)

    assert second.created == 0
    assert second.updated == 1
    assert PublishingIdentity.all_objects.filter(tenant=tenant).count() == 1
    identity = PublishingIdentity.all_objects.get(tenant=tenant)
    assert identity.display_name == "Renamed Page"


@pytest.mark.django_db
def test_sync_respects_explicit_revoke(tenant):
    _meta_page(tenant, page_id="page_1", name="Page", is_default=True)
    sync_publishing_identities_for_tenant(tenant=tenant)
    PublishingIdentity.all_objects.filter(tenant=tenant).update(
        selection_state=PublishingIdentity.SELECTION_REVOKED
    )

    sync_publishing_identities_for_tenant(tenant=tenant)

    identity = PublishingIdentity.all_objects.get(tenant=tenant)
    assert identity.selection_state == PublishingIdentity.SELECTION_REVOKED


@pytest.mark.django_db
def test_sync_is_tenant_scoped(tenant):
    other_tenant = Tenant.objects.create(name="Other Tenant")
    _meta_page(tenant, page_id="page_mine", name="Mine", is_default=True)
    _meta_page(other_tenant, page_id="page_theirs", name="Theirs", is_default=True)

    sync_publishing_identities_for_tenant(tenant=tenant)

    assert PublishingIdentity.all_objects.filter(tenant=tenant).count() == 1
    assert not PublishingIdentity.all_objects.filter(tenant=other_tenant).exists()


@pytest.mark.django_db
def test_command_syncs_single_tenant(tenant):
    _meta_page(tenant, page_id="page_1", name="Page", is_default=True)

    call_command("sync_publishing_identities", "--tenant", str(tenant.id))

    assert PublishingIdentity.all_objects.filter(
        tenant=tenant, meta_page_id="page_1"
    ).exists()
