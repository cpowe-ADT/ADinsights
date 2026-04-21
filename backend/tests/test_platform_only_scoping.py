"""Sprint 10 polish: ``platforms=`` is honoured even without a ``client_id``.

Before the fix, sending ``?platforms=meta_ads`` without a ``client_id`` was
silently dropped by ``resolve_client_scoping``, so the Meta workspace's
combined payload still included Google Ads rows (and vice versa). This
defeated the purpose of the per-route platform scoping in the frontend.

These tests pin the behaviour of the new ``_resolve_platform_only_scoping``
path: it reads every tenant-owned account id for the enabled platforms and
injects the same ``client_scoped_*`` keys the warehouse adapter already
understands.
"""

from __future__ import annotations

import pytest

from analytics.combined_metrics_service import resolve_client_scoping
from analytics.models import AdAccount
from integrations.models import GoogleAdsAccountMapping


def _seed_meta(tenant, external_ids: list[str]) -> None:
    for ext in external_ids:
        AdAccount.all_objects.create(tenant=tenant, external_id=ext)


def _seed_google(tenant, customer_ids: list[str]) -> None:
    for cid in customer_ids:
        GoogleAdsAccountMapping.all_objects.create(
            tenant=tenant, customer_id=cid, is_manager=False
        )


class _Params(dict):
    """Minimal ``query_params``-shaped object (only ``.get`` is used)."""


@pytest.mark.django_db
def test_platforms_meta_only_without_client_scopes_to_meta(tenant):
    _seed_meta(tenant, ["act_111", "act_222"])
    _seed_google(tenant, ["1234567890"])

    scoping, registry, meta = resolve_client_scoping(
        tenant_id=str(tenant.id),
        query_params=_Params(platforms="meta_ads"),
    )

    assert scoping is not None
    assert sorted(scoping["client_scoped_meta_ad_account_ids"]) == [
        "111",
        "222",
        "act_111",
        "act_222",
    ]
    # Google disabled by the toggle: the scoping list is empty.
    assert scoping["client_scoped_google_customer_ids"] == []
    assert scoping["client_scope_requested"] is True
    assert registry is not None
    assert registry.is_enabled("meta_ads")
    assert not registry.is_enabled("google_ads")
    assert meta["scope"] == "platforms_only"
    assert meta["reason"] is None


@pytest.mark.django_db
def test_platforms_google_only_without_client_scopes_to_google(tenant):
    _seed_meta(tenant, ["act_111"])
    _seed_google(tenant, ["1234567890", "9876543210"])

    scoping, registry, meta = resolve_client_scoping(
        tenant_id=str(tenant.id),
        query_params=_Params(platforms="google_ads"),
    )

    assert scoping is not None
    assert sorted(scoping["client_scoped_google_customer_ids"]) == [
        "1234567890",
        "9876543210",
    ]
    assert scoping["client_scoped_meta_ad_account_ids"] == []
    assert registry is not None
    assert registry.is_enabled("google_ads")
    assert not registry.is_enabled("meta_ads")
    assert meta["scope"] == "platforms_only"


@pytest.mark.django_db
def test_platforms_omitted_without_client_returns_legacy_none(tenant):
    """No ``platforms=`` and no ``client_id`` keeps the legacy "no scoping"
    behaviour so existing callers (reports, unfiltered dashboards) are
    unaffected."""

    _seed_meta(tenant, ["act_111"])
    scoping, registry, meta = resolve_client_scoping(
        tenant_id=str(tenant.id),
        query_params=_Params(),
    )
    assert scoping is None
    assert registry is None
    assert meta is None


@pytest.mark.django_db
def test_platforms_meta_with_no_tenant_accounts_surfaces_empty_reason(tenant):
    """Requesting meta when the tenant has zero Meta accounts yields
    ``client_scope_requested=True`` with empty lists — the adapter then
    returns an empty payload instead of leaking other-platform data."""

    _seed_google(tenant, ["1234567890"])
    scoping, registry, meta = resolve_client_scoping(
        tenant_id=str(tenant.id),
        query_params=_Params(platforms="meta_ads"),
    )
    assert scoping is not None
    assert scoping["client_scoped_meta_ad_account_ids"] == []
    assert scoping["client_scoped_google_customer_ids"] == []
    assert scoping["client_scope_requested"] is True
    # Meta is not in configured → registry shows it un-configured.
    assert registry is not None
    assert meta["reason"] in {"all_platforms_disabled", "no_enabled_platforms"}


@pytest.mark.django_db
def test_platforms_both_without_client_includes_all_tenant_accounts(tenant):
    """``platforms=meta_ads,google_ads`` acts like "no scope" for data,
    but still forces ``client_scope_requested=True`` so the adapter keeps
    the explicit filter (rather than falling through to the unfiltered
    tenant payload, which would bypass the route's scoping intent)."""

    _seed_meta(tenant, ["act_111"])
    _seed_google(tenant, ["1234567890"])
    scoping, registry, meta = resolve_client_scoping(
        tenant_id=str(tenant.id),
        query_params=_Params(platforms="meta_ads,google_ads"),
    )
    assert scoping is not None
    assert "act_111" in scoping["client_scoped_meta_ad_account_ids"]
    assert "1234567890" in scoping["client_scoped_google_customer_ids"]
    assert registry is not None
    assert registry.is_enabled("meta_ads")
    assert registry.is_enabled("google_ads")
    assert meta["scope"] == "platforms_only"


@pytest.mark.django_db
def test_platforms_with_account_id_skips_tenant_wide_expansion(tenant):
    """If the caller already passed a narrower ``account_id`` we must not
    fold the whole tenant's platform account set into the scoping — the
    warehouse adapter unions ``account_id`` with the scoped list, so
    injecting all tenant Meta accounts would widen the filter past the
    user's single-account selection. Falling through to "no scoping"
    keeps the account_id filter authoritative.
    """

    _seed_meta(tenant, ["act_111", "act_222"])
    _seed_google(tenant, ["1234567890"])

    scoping, registry, meta = resolve_client_scoping(
        tenant_id=str(tenant.id),
        query_params=_Params(platforms="meta_ads", account_id="act_111"),
    )
    assert scoping is None
    assert registry is None
    assert meta is None


@pytest.mark.django_db
def test_platforms_ignores_manager_google_accounts(tenant):
    """MCC/manager accounts are not spend-owning customers; excluding them
    from the scoping list prevents the adapter from matching parent-manager
    rows that shouldn't flow into the combined payload."""

    _seed_google(tenant, ["1234567890"])
    GoogleAdsAccountMapping.all_objects.create(
        tenant=tenant, customer_id="9999999999", is_manager=True
    )

    scoping, _registry, _meta = resolve_client_scoping(
        tenant_id=str(tenant.id),
        query_params=_Params(platforms="google_ads"),
    )
    assert scoping is not None
    assert scoping["client_scoped_google_customer_ids"] == ["1234567890"]
