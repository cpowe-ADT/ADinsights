# Airbyte Configuration

This directory contains declarative configuration snippets for the ingestion layer.

- `meta_source.yaml` – Production-ready Meta Marketing API source configured for incremental syncs.
- `google_ads_source.yaml` – Google Ads source leveraging a custom query with incremental cursor on `segments.date`.
- `linkedin_transparency_stub.yaml` – HTTP-based placeholder for LinkedIn transparency data until a certified connector is available.
- `tiktok_transparency_stub.yaml` – HTTP-based placeholder for TikTok transparency data.

All files assume credentials are injected via a secrets manager templating system. Replace placeholders with the actual workspace UUIDs and connection IDs when provisioning resources.
