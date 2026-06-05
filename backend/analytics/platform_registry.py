"""Platform registry for the Combined dashboard surface.

Sprint 6 of Client grouping:
    The Combined view aggregates metrics from multiple platforms (Meta Ads,
    Google Ads, GA4, Search Console, LinkedIn, TikTok). This registry
    describes which platforms a tenant has *configured* and which are
    *enabled* for the combined payload on a given request.

    The registry is intentionally decoupled from ``MetricsAdapter`` — an
    adapter describes *how* to fetch data, a platform describes *which*
    source that data comes from. A single adapter (e.g. the warehouse) can
    satisfy multiple platforms; a single platform can be served by multiple
    adapters (e.g. Meta via warehouse, meta_direct, or demo). This split
    lets the UI offer per-platform toggles ("include Google Ads in the
    combined view") without leaking adapter implementation details.

    Downstream (Sprint 8) the frontend will read the configured/enabled
    sets from ``dataset_status`` to render platform chips alongside the
    client selector. For MVP we only need the *shape* of the registry so
    the Combined serializer can validate incoming ``platforms=`` toggles
    and the view can attach a ``platforms`` key to the payload describing
    which contributed data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from integrations.models import ClientPlatformAccount


# ---- Platform keys ----------------------------------------------------------
# Kept aligned with ``ClientPlatformAccount.PLATFORM_*`` so resolver output
# and registry output can be compared without a translation table.

PLATFORM_META_ADS = ClientPlatformAccount.PLATFORM_META_ADS
PLATFORM_META_PAGE = ClientPlatformAccount.PLATFORM_META_PAGE
PLATFORM_GOOGLE_ADS = ClientPlatformAccount.PLATFORM_GOOGLE_ADS
PLATFORM_GA4 = ClientPlatformAccount.PLATFORM_GA4
PLATFORM_SEARCH_CONSOLE = ClientPlatformAccount.PLATFORM_SEARCH_CONSOLE
PLATFORM_LINKEDIN = ClientPlatformAccount.PLATFORM_LINKEDIN
PLATFORM_TIKTOK = ClientPlatformAccount.PLATFORM_TIKTOK


# Platforms that currently contribute spend/clicks/impressions to the
# combined payload. TikTok is wired through the dbt performance lineage
# (stg_tiktok_ads_performance -> fact_performance) behind the enable_tiktok
# warehouse flag; it returns zeros until that data is present. GA4 / Search
# Console / LinkedIn remain reserved for Phase 2 pilot contracts.
COMBINED_SUPPORTED: frozenset[str] = frozenset(
    {PLATFORM_META_ADS, PLATFORM_GOOGLE_ADS, PLATFORM_TIKTOK}
)


# Ordered for stable UI rendering (matches the order used in the client
# detail drawer and combined toggle group).
COMBINED_ORDER: tuple[str, ...] = (
    PLATFORM_META_ADS,
    PLATFORM_GOOGLE_ADS,
    PLATFORM_GA4,
    PLATFORM_SEARCH_CONSOLE,
    PLATFORM_META_PAGE,
    PLATFORM_LINKEDIN,
    PLATFORM_TIKTOK,
)


@dataclass(frozen=True)
class PlatformEntry:
    """Describe one platform's status on the Combined surface."""

    key: str
    label: str
    combined_supported: bool
    configured: bool = False
    enabled: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "combined_supported": self.combined_supported,
            "configured": self.configured,
            "enabled": self.enabled,
        }


_LABELS: dict[str, str] = {
    PLATFORM_META_ADS: "Meta Ads",
    PLATFORM_META_PAGE: "Meta Page Insights",
    PLATFORM_GOOGLE_ADS: "Google Ads",
    PLATFORM_GA4: "Google Analytics 4",
    PLATFORM_SEARCH_CONSOLE: "Search Console",
    PLATFORM_LINKEDIN: "LinkedIn Ads",
    PLATFORM_TIKTOK: "TikTok Ads",
}


@dataclass
class PlatformRegistry:
    """Enumerate the platform contributions available for a request.

    ``configured_platforms`` is the set the *tenant* has OAuth-authorised
    (determined from ``ClientPlatformAccount`` rows at resolve time).
    ``enabled_platforms`` is the subset the *request* wants to include
    (driven by the UI toggles — defaults to everything configured).
    """

    configured_platforms: frozenset[str] = field(default_factory=frozenset)
    enabled_platforms: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_configured(
        cls,
        configured: Iterable[str],
        *,
        enabled: Iterable[str] | None = None,
    ) -> "PlatformRegistry":
        configured_set = frozenset(configured)
        if enabled is None:
            enabled_set = configured_set & COMBINED_SUPPORTED
        else:
            enabled_set = frozenset(enabled) & configured_set & COMBINED_SUPPORTED
        return cls(
            configured_platforms=configured_set,
            enabled_platforms=enabled_set,
        )

    def entries(self) -> list[PlatformEntry]:
        out: list[PlatformEntry] = []
        for key in COMBINED_ORDER:
            out.append(
                PlatformEntry(
                    key=key,
                    label=_LABELS.get(key, key),
                    combined_supported=key in COMBINED_SUPPORTED,
                    configured=key in self.configured_platforms,
                    enabled=key in self.enabled_platforms,
                )
            )
        return out

    def to_dict(self) -> dict[str, object]:
        return {
            "configured": sorted(self.configured_platforms),
            "enabled": sorted(self.enabled_platforms),
            "combined_supported": sorted(COMBINED_SUPPORTED),
            "entries": [entry.to_dict() for entry in self.entries()],
        }

    def is_enabled(self, platform: str) -> bool:
        return platform in self.enabled_platforms


def parse_enabled_param(raw: str | None) -> list[str] | None:
    """Parse the ``platforms=`` query param: comma-separated platform keys.

    Returns ``None`` when absent (caller should default to "everything
    configured"), an empty list when present-but-empty (explicit "nothing"),
    or a list of known platform keys. Unknown keys are silently dropped to
    keep the API resilient to frontend/backend deploy skew.
    """

    if raw is None:
        return None
    candidate = (raw or "").strip()
    if not candidate:
        return []
    known = set(COMBINED_ORDER)
    out: list[str] = []
    for part in candidate.split(","):
        trimmed = part.strip()
        if trimmed and trimmed in known and trimmed not in out:
            out.append(trimmed)
    return out
