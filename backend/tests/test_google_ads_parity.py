from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from analytics.models import AdAccount, RawPerformanceRecord
from integrations.google_ads.parity import (
    ParityThresholds,
    evaluate_google_ads_parity,
    persist_parity_run,
)
from integrations.models import GoogleAdsParityRun, GoogleAdsSdkAdGroupAdDaily

pytestmark = pytest.mark.django_db


def test_evaluate_google_ads_parity_passes_within_thresholds(tenant):
    AdAccount.objects.create(
        tenant=tenant,
        external_id="act_123",
        account_id="123",
        name="Google Account",
    )
    GoogleAdsSdkAdGroupAdDaily.objects.create(
        tenant=tenant,
        customer_id="123",
        campaign_id="1",
        ad_group_id="2",
        ad_id="3",
        date_day=date(2026, 2, 20),
        cost_micros=1000000,
        clicks=100,
        conversions=Decimal("10"),
    )
    RawPerformanceRecord.objects.create(
        tenant=tenant,
        source="google_ads",
        external_id="123",
        date=date(2026, 2, 20),
        spend=Decimal("1"),
        clicks=100,
        conversions=10,
    )
    thresholds = ParityThresholds(
        spend_max_delta_pct=Decimal("1.0"),
        clicks_max_delta_pct=Decimal("2.0"),
        conversions_max_delta_pct=Decimal("2.0"),
    )

    result = evaluate_google_ads_parity(
        tenant=tenant,
        account_id="123",
        window_start=date(2026, 2, 20),
        window_end=date(2026, 2, 20),
        thresholds=thresholds,
    )
    assert result.passed is True
    assert result.reasons == []

    persisted = persist_parity_run(
        tenant=tenant,
        account_id="123",
        window_start=date(2026, 2, 20),
        window_end=date(2026, 2, 20),
        result=result,
    )
    assert isinstance(persisted, GoogleAdsParityRun)
    assert GoogleAdsParityRun.objects.count() == 1
