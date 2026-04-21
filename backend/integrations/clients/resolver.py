"""Resolver: given a Client, return the platform-native identifiers to query.

Design notes
------------
* **Transparent MCC expansion.** If a Client is linked to a Google Ads manager
  (MCC) customer_id, the resolver returns every non-manager descendant of that
  MCC alongside any directly-linked leaf customer_ids. The ``MCCExpansion`` side
  channel records which leaves came from which MCC so the UI can show
  "via MCC 8406755766 (3 accounts)".
* **Platform filtering.** Callers pass ``platforms`` to skip DB hits for
  platforms they do not care about — the Google dashboard asks for
  ``{"google_ads"}`` and gets empty Meta lists without touching Meta tables.
* **Tenant scope.** Every query goes through ``all_objects.filter(tenant_id=...)``
  — this function is safe to call outside a request's ``tenant_context``
  because it pins the tenant explicitly. Callers that are inside a request
  context still get the right answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from integrations.models import (
    Client,
    ClientPlatformAccount,
    GoogleAdsAccountMapping,
)


@dataclass(frozen=True)
class MCCExpansion:
    """Record of one MCC → children expansion for UI transparency."""

    manager_customer_id: str
    child_customer_ids: tuple[str, ...]


@dataclass
class ClientAccountBundle:
    """All platform-native identifiers linked to a Client, grouped by platform."""

    client_id: str
    google_customer_ids: list[str] = field(default_factory=list)
    meta_ad_account_ids: list[str] = field(default_factory=list)
    meta_page_ids: list[str] = field(default_factory=list)
    ga4_property_ids: list[str] = field(default_factory=list)
    search_console_site_urls: list[str] = field(default_factory=list)
    linkedin_account_ids: list[str] = field(default_factory=list)
    tiktok_account_ids: list[str] = field(default_factory=list)
    mcc_expansions: list[MCCExpansion] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not any(
            (
                self.google_customer_ids,
                self.meta_ad_account_ids,
                self.meta_page_ids,
                self.ga4_property_ids,
                self.search_console_site_urls,
                self.linkedin_account_ids,
                self.tiktok_account_ids,
            )
        )

    def for_platform(self, platform: str) -> list[str]:
        """Return the id list for a platform key (raises KeyError for unknown)."""

        mapping = {
            ClientPlatformAccount.PLATFORM_GOOGLE_ADS: self.google_customer_ids,
            ClientPlatformAccount.PLATFORM_META_ADS: self.meta_ad_account_ids,
            ClientPlatformAccount.PLATFORM_META_PAGE: self.meta_page_ids,
            ClientPlatformAccount.PLATFORM_GA4: self.ga4_property_ids,
            ClientPlatformAccount.PLATFORM_SEARCH_CONSOLE: self.search_console_site_urls,
            ClientPlatformAccount.PLATFORM_LINKEDIN: self.linkedin_account_ids,
            ClientPlatformAccount.PLATFORM_TIKTOK: self.tiktok_account_ids,
        }
        return mapping[platform]


_ALL_PLATFORMS: frozenset[str] = frozenset(
    key for key, _ in ClientPlatformAccount.PLATFORM_CHOICES
)


def _normalize_platforms(platforms: Optional[Iterable[str]]) -> frozenset[str]:
    if platforms is None:
        return _ALL_PLATFORMS
    requested = frozenset(platforms)
    unknown = requested - _ALL_PLATFORMS
    if unknown:
        raise ValueError(f"Unknown platform keys: {sorted(unknown)}")
    return requested


def _normalize_customer_id(raw: str) -> str:
    return (raw or "").replace("-", "").strip()


def _expand_google_mcc(
    tenant_id: str, linked_customer_ids: list[str]
) -> tuple[list[str], list[MCCExpansion]]:
    """Expand MCC entries into their non-manager descendants.

    ``linked_customer_ids`` is the set of Google customer_ids directly linked
    to the Client via ``ClientPlatformAccount``. For each one that is an MCC
    (``is_manager=True`` in the account mapping table), we pull all non-manager
    children that list it in ``manager_customer_id``.
    """

    if not linked_customer_ids:
        return [], []

    normalized = [_normalize_customer_id(cid) for cid in linked_customer_ids]
    mappings = list(
        GoogleAdsAccountMapping.all_objects.filter(
            tenant_id=tenant_id, customer_id__in=normalized
        )
    )

    mgr_ids = [m.customer_id for m in mappings if m.is_manager]
    leaf_ids = [m.customer_id for m in mappings if not m.is_manager]

    # Any ids the user linked but we have no mapping row for — treat as leaves
    # so they still get queried (the sync just hasn't populated mappings yet).
    known_ids = {m.customer_id for m in mappings}
    unmapped = [cid for cid in normalized if cid not in known_ids]
    leaf_ids.extend(unmapped)

    expansions: list[MCCExpansion] = []
    for mgr_id in mgr_ids:
        children = list(
            GoogleAdsAccountMapping.all_objects.filter(
                tenant_id=tenant_id,
                manager_customer_id=mgr_id,
                is_manager=False,
            ).values_list("customer_id", flat=True)
        )
        if children:
            expansions.append(
                MCCExpansion(
                    manager_customer_id=mgr_id,
                    child_customer_ids=tuple(sorted(children)),
                )
            )
            leaf_ids.extend(children)

    # Deduplicate while preserving first-seen order for stable output.
    seen: set[str] = set()
    deduped: list[str] = []
    for cid in leaf_ids:
        if cid and cid not in seen:
            seen.add(cid)
            deduped.append(cid)
    return deduped, expansions


def resolve_client_accounts(
    tenant_id: str,
    client_id: str,
    *,
    platforms: Optional[Iterable[str]] = None,
) -> ClientAccountBundle:
    """Return every platform-native id linked to a Client.

    Parameters
    ----------
    tenant_id
        UUID string for the tenant. Required even inside a tenant_context —
        being explicit here keeps the resolver safe to call from Celery tasks.
    client_id
        UUID string for the Client.
    platforms
        Optional iterable of platform keys (``ClientPlatformAccount.PLATFORM_*``).
        If omitted, all platforms are resolved. Unknown keys raise ValueError.

    Raises
    ------
    Client.DoesNotExist
        If no Client with that id exists for the tenant.
    """

    requested = _normalize_platforms(platforms)

    # Verify the Client exists for this tenant — no cross-tenant leakage even
    # if the caller passes a client_id they should not see.
    client = Client.all_objects.get(id=client_id, tenant_id=tenant_id)

    bundle = ClientAccountBundle(client_id=str(client.id))

    links = ClientPlatformAccount.all_objects.filter(
        tenant_id=tenant_id, client_id=client.id, platform__in=requested
    ).values_list("platform", "external_id")

    per_platform: dict[str, list[str]] = {}
    for platform, ext in links:
        per_platform.setdefault(platform, []).append(ext)

    # Google Ads — expand MCCs into their non-manager descendants.
    if ClientPlatformAccount.PLATFORM_GOOGLE_ADS in requested:
        linked = per_platform.get(ClientPlatformAccount.PLATFORM_GOOGLE_ADS, [])
        expanded, expansions = _expand_google_mcc(tenant_id, linked)
        bundle.google_customer_ids = expanded
        bundle.mcc_expansions = expansions

    if ClientPlatformAccount.PLATFORM_META_ADS in requested:
        bundle.meta_ad_account_ids = sorted(
            set(per_platform.get(ClientPlatformAccount.PLATFORM_META_ADS, []))
        )
    if ClientPlatformAccount.PLATFORM_META_PAGE in requested:
        bundle.meta_page_ids = sorted(
            set(per_platform.get(ClientPlatformAccount.PLATFORM_META_PAGE, []))
        )
    if ClientPlatformAccount.PLATFORM_GA4 in requested:
        bundle.ga4_property_ids = sorted(
            set(per_platform.get(ClientPlatformAccount.PLATFORM_GA4, []))
        )
    if ClientPlatformAccount.PLATFORM_SEARCH_CONSOLE in requested:
        bundle.search_console_site_urls = sorted(
            set(per_platform.get(ClientPlatformAccount.PLATFORM_SEARCH_CONSOLE, []))
        )
    if ClientPlatformAccount.PLATFORM_LINKEDIN in requested:
        bundle.linkedin_account_ids = sorted(
            set(per_platform.get(ClientPlatformAccount.PLATFORM_LINKEDIN, []))
        )
    if ClientPlatformAccount.PLATFORM_TIKTOK in requested:
        bundle.tiktok_account_ids = sorted(
            set(per_platform.get(ClientPlatformAccount.PLATFORM_TIKTOK, []))
        )

    return bundle


def resolve_client_for_external(
    tenant_id: str, platform: str, external_id: str
) -> Optional[Client]:
    """Reverse lookup: which Client (if any) owns this platform account?

    Used by sync tasks to attribute a newly-seen account to an existing Client
    and by Sprint 9's post-OAuth auto-suggest loop.
    """

    if platform not in _ALL_PLATFORMS:
        raise ValueError(f"Unknown platform key: {platform!r}")

    try:
        link = ClientPlatformAccount.all_objects.select_related("client").get(
            tenant_id=tenant_id, platform=platform, external_id=external_id
        )
    except ClientPlatformAccount.DoesNotExist:
        return None
    return link.client
