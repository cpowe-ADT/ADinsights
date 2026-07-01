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
    instagram_business_account_id: str = "",
    instagram_username: str = "",
) -> MetaPage:
    page = MetaPage(
        tenant=tenant,
        page_id=page_id,
        name=name,
        can_analyze=True,
        is_default=is_default,
        perms=perms if perms is not None else [],
        tasks=tasks if tasks is not None else [],
        instagram_business_account_id=instagram_business_account_id,
        instagram_username=instagram_username,
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
    # No Instagram identities are invented for pages without a linked IG account.
    assert not PublishingIdentity.all_objects.filter(
        tenant=tenant, platform=PublishingIdentity.PLATFORM_INSTAGRAM
    ).exists()


@pytest.mark.django_db
def test_sync_creates_instagram_identity_for_linked_page(tenant):
    _meta_credential(tenant)
    _meta_page(
        tenant,
        page_id="page_ig",
        name="Linked Page",
        is_default=True,
        instagram_business_account_id="ig_17900000000000000",
        instagram_username="brand.jamaica",
    )

    result = sync_publishing_identities_for_tenant(tenant=tenant)

    # One page -> one Facebook identity + one Instagram identity.
    assert result.total_pages == 1
    assert result.created == 2
    fb = PublishingIdentity.all_objects.get(
        tenant=tenant, platform=PublishingIdentity.PLATFORM_FACEBOOK_PAGE
    )
    ig = PublishingIdentity.all_objects.get(
        tenant=tenant, platform=PublishingIdentity.PLATFORM_INSTAGRAM
    )
    assert fb.meta_page_id == "page_ig"
    assert ig.meta_page_id == "page_ig"
    assert ig.ig_user_id == "ig_17900000000000000"
    assert ig.display_name == "brand.jamaica"
    assert ig.selection_state == PublishingIdentity.SELECTION_SELECTED

    # Idempotent: re-running creates nothing new.
    rerun = sync_publishing_identities_for_tenant(tenant=tenant)
    assert rerun.created == 0
    assert PublishingIdentity.all_objects.filter(tenant=tenant).count() == 2


@pytest.mark.django_db
def test_sync_without_instagram_link_creates_no_instagram_identity(tenant):
    _meta_page(tenant, page_id="page_plain", name="Plain Page", is_default=True)

    sync_publishing_identities_for_tenant(tenant=tenant)

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
