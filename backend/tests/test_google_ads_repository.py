from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from integrations.google_ads.client import AdGroupAdDailyRow
from integrations.google_ads.repository import upsert_ad_group_ad_daily_rows
from integrations.models import GoogleAdsSdkAdGroupAdDaily

pytestmark = pytest.mark.django_db


def test_upsert_ad_group_ad_daily_rows_is_idempotent(tenant):
    row = AdGroupAdDailyRow(
        customer_id="123",
        campaign_id="10",
        ad_group_id="20",
        ad_id="30",
        campaign_name="Campaign",
        ad_name="Ad Name",
        ad_status="ENABLED",
        policy_approval_status="APPROVED",
        policy_review_status="REVIEWED",
        date_day=date(2026, 2, 20),
        currency_code="USD",
        impressions=100,
        clicks=10,
        conversions=Decimal("2"),
        conversions_value=Decimal("5"),
        cost_micros=1000000,
        request_id="req-1",
    )

    first = upsert_ad_group_ad_daily_rows(tenant=tenant, rows=[row])
    second = upsert_ad_group_ad_daily_rows(tenant=tenant, rows=[row])

    assert first == 1
    assert second == 1
    assert GoogleAdsSdkAdGroupAdDaily.objects.count() == 1

    stored = GoogleAdsSdkAdGroupAdDaily.objects.first()
    assert stored is not None
    assert stored.clicks == 10
    assert stored.cost_micros == 1000000
