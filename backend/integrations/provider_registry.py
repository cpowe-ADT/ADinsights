from __future__ import annotations

from dataclasses import dataclass

from .models import PlatformCredential


@dataclass(frozen=True)
class IntegrationProvider:
    slug: str
    label: str
    credential_provider: str
    oauth_family: str
    default_connection_name: str
    source_definition_id: str | None = None


PROVIDERS: dict[str, IntegrationProvider] = {
    "meta_ads": IntegrationProvider(
        slug="meta_ads",
        label="Meta Ads",
        credential_provider=PlatformCredential.META,
        oauth_family="meta",
        default_connection_name="Meta Ads Metrics",
        source_definition_id="778daa7c-feaf-4db6-96f3-70fd645acc77",
    ),
    "facebook_pages": IntegrationProvider(
        slug="facebook_pages",
        label="Facebook Pages",
        credential_provider=PlatformCredential.META,
        oauth_family="meta",
        default_connection_name="Facebook Page Metrics",
        source_definition_id="778daa7c-feaf-4db6-96f3-70fd645acc77",
    ),
    "google_ads": IntegrationProvider(
        slug="google_ads",
        label="Google Ads",
        credential_provider=PlatformCredential.GOOGLE,
        oauth_family="google",
        default_connection_name="Google Ads Metrics",
        source_definition_id="0b29e8f7-f64c-4a24-9e97-07c4603f8c04",
    ),
    "ga4": IntegrationProvider(
        slug="ga4",
        label="Google Analytics 4",
        credential_provider=PlatformCredential.GA4,
        oauth_family="google",
        default_connection_name="GA4 Reporting",
    ),
    "search_console": IntegrationProvider(
        slug="search_console",
        label="Google Search Console",
        credential_provider=PlatformCredential.SEARCH_CONSOLE,
        oauth_family="google",
        default_connection_name="Search Console Reporting",
    ),
}


def get_provider(slug: str) -> IntegrationProvider | None:
    return PROVIDERS.get((slug or "").strip().lower())

