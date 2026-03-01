from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum

from accounts.models import Tenant
from analytics.models import RawPerformanceRecord
from integrations.models import GoogleAdsParityRun, GoogleAdsSdkAdGroupAdDaily


@dataclass(frozen=True)
class ParityThresholds:
    spend_max_delta_pct: Decimal
    clicks_max_delta_pct: Decimal
    conversions_max_delta_pct: Decimal


@dataclass(frozen=True)
class ParityResult:
    passed: bool
    reasons: list[dict[str, str]]
    sdk_spend: Decimal
    sdk_clicks: Decimal
    sdk_conversions: Decimal
    baseline_spend: Decimal
    baseline_clicks: Decimal
    baseline_conversions: Decimal
    spend_delta_pct: Decimal | None
    clicks_delta_pct: Decimal | None
    conversions_delta_pct: Decimal | None


def _to_decimal(value) -> Decimal:  # type: ignore[no-untyped-def]
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _delta_pct(*, sdk_value: Decimal, baseline_value: Decimal) -> Decimal | None:
    if baseline_value == 0:
        if sdk_value == 0:
            return Decimal("0")
        return None
    return (abs(sdk_value - baseline_value) / baseline_value) * Decimal("100")


def evaluate_google_ads_parity(
    *,
    tenant: Tenant,
    account_id: str,
    window_start: date,
    window_end: date,
    thresholds: ParityThresholds,
) -> ParityResult:
    sdk_totals = GoogleAdsSdkAdGroupAdDaily.all_objects.filter(
        tenant=tenant,
        customer_id=account_id,
        date_day__gte=window_start,
        date_day__lte=window_end,
    ).aggregate(
        spend=Sum("cost_micros"),
        clicks=Sum("clicks"),
        conversions=Sum("conversions"),
    )

    baseline_totals = RawPerformanceRecord.all_objects.filter(
        tenant=tenant,
        source__in=["google_ads", "google_ads_airbyte", "airbyte_google_ads"],
        date__gte=window_start,
        date__lte=window_end,
    ).filter(
        Q(ad_account__account_id=account_id)
        | Q(ad_account__external_id=account_id)
        | Q(external_id=account_id)
    ).aggregate(
        spend=Sum("spend"),
        clicks=Sum("clicks"),
        conversions=Sum("conversions"),
    )

    sdk_spend = _to_decimal(sdk_totals["spend"]) / Decimal("1000000")
    sdk_clicks = _to_decimal(sdk_totals["clicks"])
    sdk_conversions = _to_decimal(sdk_totals["conversions"])
    baseline_spend = _to_decimal(baseline_totals["spend"])
    baseline_clicks = _to_decimal(baseline_totals["clicks"])
    baseline_conversions = _to_decimal(baseline_totals["conversions"])

    spend_delta_pct = _delta_pct(sdk_value=sdk_spend, baseline_value=baseline_spend)
    clicks_delta_pct = _delta_pct(sdk_value=sdk_clicks, baseline_value=baseline_clicks)
    conversions_delta_pct = _delta_pct(
        sdk_value=sdk_conversions,
        baseline_value=baseline_conversions,
    )

    reasons: list[dict[str, str]] = []
    passed = True

    if spend_delta_pct is None:
        passed = False
        reasons.append(
            {
                "metric": "spend",
                "code": "baseline_zero_nonzero_sdk",
                "message": "Baseline spend is zero while SDK spend is non-zero.",
            }
        )
    elif spend_delta_pct > thresholds.spend_max_delta_pct:
        passed = False
        reasons.append(
            {
                "metric": "spend",
                "code": "delta_exceeded",
                "message": (
                    f"Spend delta {spend_delta_pct:.4f}% exceeded max "
                    f"{thresholds.spend_max_delta_pct:.4f}%."
                ),
            }
        )

    if clicks_delta_pct is None:
        passed = False
        reasons.append(
            {
                "metric": "clicks",
                "code": "baseline_zero_nonzero_sdk",
                "message": "Baseline clicks are zero while SDK clicks are non-zero.",
            }
        )
    elif clicks_delta_pct > thresholds.clicks_max_delta_pct:
        passed = False
        reasons.append(
            {
                "metric": "clicks",
                "code": "delta_exceeded",
                "message": (
                    f"Clicks delta {clicks_delta_pct:.4f}% exceeded max "
                    f"{thresholds.clicks_max_delta_pct:.4f}%."
                ),
            }
        )

    if conversions_delta_pct is None:
        passed = False
        reasons.append(
            {
                "metric": "conversions",
                "code": "baseline_zero_nonzero_sdk",
                "message": "Baseline conversions are zero while SDK conversions are non-zero.",
            }
        )
    elif conversions_delta_pct > thresholds.conversions_max_delta_pct:
        passed = False
        reasons.append(
            {
                "metric": "conversions",
                "code": "delta_exceeded",
                "message": (
                    f"Conversions delta {conversions_delta_pct:.4f}% exceeded max "
                    f"{thresholds.conversions_max_delta_pct:.4f}%."
                ),
            }
        )

    return ParityResult(
        passed=passed,
        reasons=reasons,
        sdk_spend=sdk_spend,
        sdk_clicks=sdk_clicks,
        sdk_conversions=sdk_conversions,
        baseline_spend=baseline_spend,
        baseline_clicks=baseline_clicks,
        baseline_conversions=baseline_conversions,
        spend_delta_pct=spend_delta_pct,
        clicks_delta_pct=clicks_delta_pct,
        conversions_delta_pct=conversions_delta_pct,
    )


def persist_parity_run(
    *,
    tenant: Tenant,
    account_id: str,
    window_start: date,
    window_end: date,
    result: ParityResult,
) -> GoogleAdsParityRun:
    parity_run, _ = GoogleAdsParityRun.all_objects.update_or_create(
        tenant=tenant,
        account_id=account_id,
        window_start=window_start,
        window_end=window_end,
        defaults={
            "sdk_spend": result.sdk_spend,
            "sdk_clicks": result.sdk_clicks,
            "sdk_conversions": result.sdk_conversions,
            "baseline_spend": result.baseline_spend,
            "baseline_clicks": result.baseline_clicks,
            "baseline_conversions": result.baseline_conversions,
            "spend_delta_pct": result.spend_delta_pct,
            "clicks_delta_pct": result.clicks_delta_pct,
            "conversions_delta_pct": result.conversions_delta_pct,
            "passed": result.passed,
            "reasons": result.reasons,
        },
    )
    return parity_run
