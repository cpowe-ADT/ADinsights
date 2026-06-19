"""Readiness composition for Content Operations publishing surfaces."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from analytics.dataset_status import build_dataset_status_payload
from integrations.models import MetaConnection, MetaPage, PlatformCredential

from .models import PublishingIdentity

FACEBOOK_PAGE_PUBLISHING_SCOPES = ("pages_manage_posts",)
INSTAGRAM_PUBLISHING_SCOPES = ("instagram_basic", "instagram_content_publish")


def build_content_ops_readiness_payload(*, tenant) -> dict[str, Any]:
    """Compose publishing readiness without mutating OAuth/setup/reporting state."""

    now = timezone.now()
    credentials = list(
        PlatformCredential.all_objects.filter(
            tenant=tenant,
            provider=PlatformCredential.META,
        ).order_by("-updated_at")
    )
    active_page_connection_count = MetaConnection.all_objects.filter(
        tenant=tenant,
        is_active=True,
    ).count()
    pages = list(
        MetaPage.all_objects.filter(tenant=tenant).order_by("-is_default", "name")
    )
    publishing_identities = list(
        PublishingIdentity.all_objects.filter(tenant=tenant).order_by(
            "platform", "display_name"
        )
    )
    granted_scopes = _granted_meta_scopes(credentials)
    dataset_status = build_dataset_status_payload(tenant=tenant)

    meta_auth = _meta_auth_axis(
        credentials=credentials,
        active_page_connection_count=active_page_connection_count,
    )
    page_selection = _page_selection_axis(pages=pages, meta_auth_state=meta_auth["state"])
    instagram_linkage = _instagram_linkage_axis(
        publishing_identities=publishing_identities,
        meta_auth_state=meta_auth["state"],
    )
    facebook_page_publishing = _publishing_axis(
        channel=PublishingIdentity.PLATFORM_FACEBOOK_PAGE,
        identities=publishing_identities,
        required_scopes=FACEBOOK_PAGE_PUBLISHING_SCOPES,
        granted_scopes=granted_scopes,
        upstream_axes=[meta_auth, page_selection],
    )
    instagram_publishing = _publishing_axis(
        channel=PublishingIdentity.PLATFORM_INSTAGRAM,
        identities=publishing_identities,
        required_scopes=INSTAGRAM_PUBLISHING_SCOPES,
        granted_scopes=granted_scopes,
        upstream_axes=[meta_auth, instagram_linkage],
    )
    reporting_readiness = _reporting_axis(dataset_status)

    return {
        "generated_at": now.isoformat(),
        "meta_auth": meta_auth,
        "page_selection": page_selection,
        "instagram_linkage": instagram_linkage,
        "facebook_page_publishing": facebook_page_publishing,
        "instagram_publishing": instagram_publishing,
        "reporting_readiness": reporting_readiness,
    }


def _meta_auth_axis(
    *,
    credentials: list[PlatformCredential],
    active_page_connection_count: int,
) -> dict[str, Any]:
    usable_credentials = [
        credential
        for credential in credentials
        if credential.token_status
        in {
            PlatformCredential.TOKEN_STATUS_VALID,
            PlatformCredential.TOKEN_STATUS_EXPIRING,
        }
    ]
    invalid_credentials = [
        credential
        for credential in credentials
        if credential.token_status
        in {
            PlatformCredential.TOKEN_STATUS_INVALID,
            PlatformCredential.TOKEN_STATUS_REAUTH_REQUIRED,
        }
    ]
    if usable_credentials:
        state = "connected"
        reason = None
    elif invalid_credentials:
        state = "needs_reauth"
        reason = "meta_token_invalid"
    elif active_page_connection_count:
        state = "page_insights_only"
        reason = "no_marketing_credential"
    else:
        state = "not_connected"
        reason = "missing_meta_auth"

    return {
        "state": state,
        "reason": reason,
        "credential_count": len(credentials),
        "usable_credential_count": len(usable_credentials),
        "active_page_connection_count": active_page_connection_count,
    }


def _page_selection_axis(
    *, pages: list[MetaPage], meta_auth_state: str
) -> dict[str, Any]:
    selected_pages = [page for page in pages if page.is_default or page.can_analyze]
    if selected_pages:
        state = "complete"
        reason = None
    elif meta_auth_state == "not_connected":
        state = "blocked"
        reason = "meta_auth_required"
    else:
        state = "blocked"
        reason = "facebook_page_not_selected"
    default_page = next((page for page in pages if page.is_default), None)
    return {
        "state": state,
        "reason": reason,
        "page_count": len(pages),
        "selected_page_count": len(selected_pages),
        "default_page_id": default_page.page_id if default_page else None,
    }


def _instagram_linkage_axis(
    *,
    publishing_identities: list[PublishingIdentity],
    meta_auth_state: str,
) -> dict[str, Any]:
    linked = [
        identity
        for identity in publishing_identities
        if identity.platform == PublishingIdentity.PLATFORM_INSTAGRAM
        and identity.selection_state == PublishingIdentity.SELECTION_SELECTED
        and identity.ig_user_id
    ]
    if linked:
        state = "complete"
        reason = None
    elif meta_auth_state == "not_connected":
        state = "blocked"
        reason = "meta_auth_required"
    else:
        state = "blocked"
        reason = "instagram_not_linked"
    return {
        "state": state,
        "reason": reason,
        "linked_count": len(linked),
    }


def _publishing_axis(
    *,
    channel: str,
    identities: list[PublishingIdentity],
    required_scopes: tuple[str, ...],
    granted_scopes: set[str],
    upstream_axes: list[dict[str, Any]],
) -> dict[str, Any]:
    selected_identities = [
        identity
        for identity in identities
        if identity.platform == channel
        and identity.selection_state == PublishingIdentity.SELECTION_SELECTED
    ]
    missing_permissions = [
        scope for scope in required_scopes if scope not in granted_scopes
    ]
    upstream_blockers = [
        axis["reason"] or axis["state"]
        for axis in upstream_axes
        if axis.get("state") not in {"connected", "complete"}
    ]
    identity_blockers = [
        identity.publish_readiness_reason or identity.publish_readiness_state
        for identity in selected_identities
        if identity.publish_readiness_state != PublishingIdentity.READINESS_READY
    ]

    if not selected_identities:
        state = "blocked"
        reason = "publishing_identity_missing"
    elif upstream_blockers:
        state = "blocked"
        reason = "upstream_readiness_blocked"
    elif missing_permissions:
        state = "blocked"
        reason = "missing_publishing_permissions"
    elif identity_blockers:
        state = "blocked"
        reason = "publishing_identity_blocked"
    else:
        state = "ready"
        reason = None

    return {
        "state": state,
        "reason": reason,
        "identity_count": len(selected_identities),
        "missing_permissions": missing_permissions,
        "required_permissions": list(required_scopes),
        "upstream_blockers": upstream_blockers,
        "identity_blockers": identity_blockers,
    }


def _reporting_axis(dataset_status: dict[str, Any]) -> dict[str, Any]:
    live = dataset_status.get("live") if isinstance(dataset_status, dict) else {}
    live_enabled = bool(live.get("enabled")) if isinstance(live, dict) else False
    live_reason = live.get("reason") if isinstance(live, dict) else "unknown"
    return {
        "state": "ready" if live_enabled else "blocked",
        "reason": None if live_enabled else live_reason,
        "dataset_live_reason": live_reason,
        "dataset_status": dataset_status,
    }


def _granted_meta_scopes(credentials: list[PlatformCredential]) -> set[str]:
    scopes: set[str] = set()
    for credential in credentials:
        granted = credential.granted_scopes
        if isinstance(granted, list):
            scopes.update(
                str(scope).strip() for scope in granted if str(scope).strip()
            )
    return scopes
