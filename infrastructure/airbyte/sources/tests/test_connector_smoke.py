"""Cross-connector smoke tests for the custom Airbyte sources.

These tests guard the connector *contract* against Airbyte CDK / pydantic drift.
They would have caught the divergence where the Microsoft Ads connector was
migrated off the removed ``AirbyteLogger`` import and the legacy
``parse_obj`` / ``supportsNamespaces`` spec shape, while the TikTok and
LinkedIn connectors were left on the old (now broken) API.

Every custom connector must, under the installed CDK:
  * import and instantiate,
  * produce a valid ``ConnectorSpecification`` from spec.json,
  * discover exactly one incremental stream keyed on ``(ad_id, date)``,
  * expose the shared canonical normalized schema, and
  * validate required credentials in ``check()``.
"""
from __future__ import annotations

import logging
from typing import Dict, List

import pytest

from airbyte_cdk.models import ConnectorSpecification, Status

from infrastructure.airbyte.sources.linkedin_ads import SourceLinkedinAds
from infrastructure.airbyte.sources.microsoft_ads import SourceMicrosoftAds
from infrastructure.airbyte.sources.tiktok_ads import SourceTiktokAds


LOGGER = logging.getLogger("test.connector_smoke")

# The normalized output schema every connector must emit so that downstream
# (dbt staging -> warehouse adapter -> /api/metrics/combined/) stays uniform.
CANONICAL_FIELDS = {
    "platform",
    "date",
    "account_id",
    "campaign_id",
    "ad_group_id",
    "ad_id",
    "region",
    "device",
    "spend",
    "impressions",
    "clicks",
    "conversions",
    "conversion_value",
    "currency",
}


class _Case:
    def __init__(self, source_cls, config: Dict[str, object], required: List[str]):
        self.source_cls = source_cls
        self.config = config
        self.required = required

    def __repr__(self) -> str:  # nice pytest ids
        return self.source_cls.__name__


CASES = [
    _Case(
        SourceMicrosoftAds,
        {
            "account_id": "12345",
            "developer_token": "developer-token",
            "access_token": "test-token",
            "start_date": "2024-07-01",
        },
        ["account_id", "developer_token", "access_token", "start_date"],
    ),
    _Case(
        SourceTiktokAds,
        {
            "advertiser_id": "67890",
            "access_token": "test-token",
            "start_date": "2024-07-01",
        },
        ["advertiser_id", "access_token", "start_date"],
    ),
    _Case(
        SourceLinkedinAds,
        {
            "account_id": "12345",
            "access_token": "test-token",
            "start_date": "2024-07-01",
        },
        ["account_id", "access_token", "start_date"],
    ),
]


@pytest.mark.parametrize("case", CASES, ids=repr)
def test_spec_loads_under_installed_cdk(case: _Case) -> None:
    spec = case.source_cls().spec(LOGGER)
    assert isinstance(spec, ConnectorSpecification)
    assert spec.connectionSpecification  # non-empty connection schema


@pytest.mark.parametrize("case", CASES, ids=repr)
def test_discover_exposes_canonical_incremental_stream(case: _Case) -> None:
    catalog = case.source_cls().discover(LOGGER, case.config)
    assert len(catalog.streams) == 1
    stream = catalog.streams[0]
    assert stream.default_cursor_field == ["date"]
    assert stream.source_defined_primary_key == [["ad_id"], ["date"]]
    assert CANONICAL_FIELDS <= set(stream.json_schema["properties"])


@pytest.mark.parametrize("case", CASES, ids=repr)
def test_check_passes_with_full_config(case: _Case) -> None:
    status = case.source_cls().check(LOGGER, case.config)
    assert status.status == Status.SUCCEEDED


@pytest.mark.parametrize("case", CASES, ids=repr)
def test_check_fails_when_credential_missing(case: _Case) -> None:
    source = case.source_cls()
    for field in case.required:
        broken = {k: v for k, v in case.config.items() if k != field}
        status = source.check(LOGGER, broken)
        assert status.status == Status.FAILED, f"{case} should fail without {field}"
        assert field in (status.message or "")
