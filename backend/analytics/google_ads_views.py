from __future__ import annotations

import csv
import hashlib
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Max, Q, Sum
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.audit import log_audit_event
from accounts.models import Role
from analytics.google_ads_serializers import (
    GoogleAdsAccountAssignmentSerializer,
    GoogleAdsBreakdownQuerySerializer,
    GoogleAdsDateRangeQuerySerializer,
    GoogleAdsExecutiveQuerySerializer,
    GoogleAdsExportCreateSerializer,
    GoogleAdsExportJobSerializer,
    GoogleAdsListQuerySerializer,
    GoogleAdsSavedViewSerializer,
)
from analytics.models import GoogleAdsExportJob, GoogleAdsSavedView
from integrations.models import (
    CampaignBudget,
    GoogleAdsAccountAssignment,
    GoogleAdsSdkAdGroupAdDaily,
    GoogleAdsSdkAssetGroupDaily,
    GoogleAdsSdkCampaignDaily,
    GoogleAdsSdkChangeEvent,
    GoogleAdsSdkConversionActionDaily,
    GoogleAdsSdkGeographicDaily,
    GoogleAdsSdkKeywordDaily,
    GoogleAdsSdkRecommendation,
    GoogleAdsSdkSearchTermDaily,
    GoogleAdsSyncState,
)


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _safe_div(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return Decimal("0")
    return numerator / denominator


def _micros_to_currency(value: Decimal | int | None) -> Decimal:
    micros = _to_decimal(value)
    return micros / Decimal("1000000")


def _is_admin(user) -> bool:  # noqa: ANN001
    if getattr(user, "is_superuser", False):
        return True
    tenant_id = getattr(user, "tenant_id", None)
    if tenant_id is None:
        return False
    return user.user_roles.filter(tenant_id=tenant_id, role__name=Role.ADMIN).exists()


def _accessible_customer_ids(user) -> set[str] | None:  # noqa: ANN001
    if _is_admin(user):
        return None
    rows = GoogleAdsAccountAssignment.objects.filter(
        tenant_id=user.tenant_id,
        user_id=user.id,
        is_active=True,
    ).values_list("customer_id", flat=True)
    return {str(row) for row in rows}


def _apply_customer_scope(queryset, user, field_name: str = "customer_id"):
    allowed = _accessible_customer_ids(user)
    if allowed is None:
        return queryset
    if not allowed:
        return queryset.none()
    return queryset.filter(**{f"{field_name}__in": list(allowed)})


def _apply_date_and_common_filters(queryset, validated: dict[str, Any], *, customer_field: str = "customer_id"):
    scoped = queryset.filter(date_day__gte=validated["start_date"], date_day__lte=validated["end_date"])
    customer_id = (validated.get("customer_id") or "").strip()
    if customer_id:
        scoped = scoped.filter(**{customer_field: customer_id})
    campaign_id = (validated.get("campaign_id") or "").strip()
    if campaign_id:
        scoped = scoped.filter(campaign_id=campaign_id)
    return scoped


def _period_compare_window(start_date: date, end_date: date) -> tuple[date, date]:
    delta_days = (end_date - start_date).days + 1
    compare_end = start_date - timedelta(days=1)
    compare_start = compare_end - timedelta(days=delta_days - 1)
    return compare_start, compare_end


def _source_engine_for_tenant(tenant_id: str) -> str:
    has_fallback = GoogleAdsSyncState.all_objects.filter(
        tenant_id=tenant_id,
        fallback_active=True,
    ).exists()
    return "airbyte_fallback" if has_fallback else "sdk"


def _metric_payload(*, spend: Decimal, impressions: Decimal, clicks: Decimal, conversions: Decimal, conv_value: Decimal) -> dict[str, float]:
    ctr = _safe_div(clicks, impressions)
    avg_cpc = _safe_div(spend, clicks)
    conv_rate = _safe_div(conversions, clicks)
    cpa = _safe_div(spend, conversions)
    roas = _safe_div(conv_value, spend)
    return {
        "spend": float(spend),
        "impressions": float(impressions),
        "clicks": float(clicks),
        "ctr": float(ctr),
        "avg_cpc": float(avg_cpc),
        "conversions": float(conversions),
        "conversion_rate": float(conv_rate),
        "cpa": float(cpa),
        "conversion_value": float(conv_value),
        "roas": float(roas),
    }


def _build_executive_payload(*, user, validated: dict[str, Any], cache_key_prefix: str) -> dict[str, Any]:
    cache_ttl = int(getattr(settings, "GOOGLE_ADS_TODAY_CACHE_TTL_SECONDS", 300) or 300)
    cache_key_src = f"{user.tenant_id}:{validated}"
    cache_key = f"{cache_key_prefix}:{hashlib.sha256(cache_key_src.encode('utf-8')).hexdigest()}"
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return cached

    qs = GoogleAdsSdkCampaignDaily.objects.filter(tenant_id=user.tenant_id)
    qs = _apply_customer_scope(qs, user)
    qs = _apply_date_and_common_filters(qs, validated)

    current = qs.aggregate(
        spend_micros=Sum("cost_micros"),
        impressions_total=Sum("impressions"),
        clicks_total=Sum("clicks"),
        conversions_total=Sum("conversions"),
        conversion_value_total=Sum("conversions_value"),
        updated_at=Max("updated_at"),
    )
    spend = _micros_to_currency(current["spend_micros"])
    impressions = _to_decimal(current["impressions_total"])
    clicks = _to_decimal(current["clicks_total"])
    conversions = _to_decimal(current["conversions_total"])
    conversion_value = _to_decimal(current["conversion_value_total"])

    compare_start, compare_end = _period_compare_window(validated["start_date"], validated["end_date"])
    prev_qs = GoogleAdsSdkCampaignDaily.objects.filter(
        tenant_id=user.tenant_id,
        date_day__gte=compare_start,
        date_day__lte=compare_end,
    )
    prev_qs = _apply_customer_scope(prev_qs, user)
    customer_id = (validated.get("customer_id") or "").strip()
    if customer_id:
        prev_qs = prev_qs.filter(customer_id=customer_id)
    campaign_id = (validated.get("campaign_id") or "").strip()
    if campaign_id:
        prev_qs = prev_qs.filter(campaign_id=campaign_id)
    previous = prev_qs.aggregate(
        spend_micros=Sum("cost_micros"),
        impressions_total=Sum("impressions"),
        clicks_total=Sum("clicks"),
        conversions_total=Sum("conversions"),
        conversion_value_total=Sum("conversions_value"),
    )
    prev_payload = _metric_payload(
        spend=_micros_to_currency(previous["spend_micros"]),
        impressions=_to_decimal(previous["impressions_total"]),
        clicks=_to_decimal(previous["clicks_total"]),
        conversions=_to_decimal(previous["conversions_total"]),
        conv_value=_to_decimal(previous["conversion_value_total"]),
    )

    trend_rows = (
        qs.values("date_day")
        .annotate(
            spend_micros=Sum("cost_micros"),
            conversions_total=Sum("conversions"),
            conversion_value_total=Sum("conversions_value"),
        )
        .order_by("date_day")
    )
    trend = []
    for row in trend_rows:
        spend_day = _micros_to_currency(row["spend_micros"])
        conv_day = _to_decimal(row["conversions_total"])
        conv_value_day = _to_decimal(row["conversion_value_total"])
        trend.append(
            {
                "date": row["date_day"].isoformat(),
                "spend": float(spend_day),
                "conversions": float(conv_day),
                "roas": float(_safe_div(conv_value_day, spend_day)),
            }
        )

    mover_rows = (
        qs.values("campaign_id", "campaign_name")
        .annotate(
            spend_micros=Sum("cost_micros"),
            conversion_value_total=Sum("conversions_value"),
        )
        .order_by("-spend_micros")[:10]
    )
    movers = []
    for row in mover_rows:
        mover_spend = _micros_to_currency(row["spend_micros"])
        mover_conv_value = _to_decimal(row["conversion_value_total"])
        movers.append(
            {
                "campaign_id": row["campaign_id"],
                "campaign_name": row["campaign_name"],
                "spend": float(mover_spend),
                "conversion_value": float(mover_conv_value),
                "roas": float(_safe_div(mover_conv_value, mover_spend)),
            }
        )

    month_start = validated["end_date"].replace(day=1)
    month_qs = GoogleAdsSdkCampaignDaily.objects.filter(
        tenant_id=user.tenant_id,
        date_day__gte=month_start,
        date_day__lte=validated["end_date"],
    )
    month_qs = _apply_customer_scope(month_qs, user)
    spend_mtd = _micros_to_currency(month_qs.aggregate(spend_micros=Sum("cost_micros"))["spend_micros"])
    budget_total = _to_decimal(
        CampaignBudget.objects.filter(tenant_id=user.tenant_id, is_active=True).aggregate(
            total=Sum("monthly_target")
        )["total"]
    )
    elapsed_days = max(validated["end_date"].day, 1)
    _, month_days = monthrange(validated["end_date"].year, validated["end_date"].month)
    forecast = spend_mtd / Decimal(elapsed_days) * Decimal(month_days)
    pacing_pct = _safe_div(spend_mtd, budget_total)

    payload = {
        "window": {
            "start_date": validated["start_date"].isoformat(),
            "end_date": validated["end_date"].isoformat(),
            "compare_start_date": compare_start.isoformat(),
            "compare_end_date": compare_end.isoformat(),
        },
        "metrics": _metric_payload(
            spend=spend,
            impressions=impressions,
            clicks=clicks,
            conversions=conversions,
            conv_value=conversion_value,
        ),
        "comparison": prev_payload,
        "pacing": {
            "spend_mtd": float(spend_mtd),
            "budget_month": float(budget_total),
            "forecast_month_end": float(forecast),
            "over_under": float(forecast - budget_total),
            "pacing_pct": float(pacing_pct),
        },
        "trend": trend,
        "movers": movers,
        "data_freshness_ts": current["updated_at"].isoformat() if current["updated_at"] else None,
        "source_engine": _source_engine_for_tenant(str(user.tenant_id)),
    }
    cache.set(cache_key, payload, timeout=cache_ttl)
    return payload


def _campaign_rows_for_export(user, filters: dict[str, Any]) -> list[dict[str, Any]]:  # noqa: ANN001
    qs = GoogleAdsSdkCampaignDaily.objects.filter(tenant_id=user.tenant_id)
    qs = _apply_customer_scope(qs, user)
    qs = _apply_date_and_common_filters(qs, filters)
    rows = (
        qs.values(
            "customer_id",
            "campaign_id",
            "campaign_name",
            "advertising_channel_type",
            "campaign_status",
        )
        .annotate(
            spend_micros=Sum("cost_micros"),
            impressions_total=Sum("impressions"),
            clicks_total=Sum("clicks"),
            conversions_total=Sum("conversions"),
            conversion_value_total=Sum("conversions_value"),
        )
        .order_by("campaign_name", "campaign_id")
    )
    payload: list[dict[str, Any]] = []
    for row in rows:
        spend = _micros_to_currency(row["spend_micros"])
        clicks = _to_decimal(row["clicks_total"])
        impressions = _to_decimal(row["impressions_total"])
        conversions = _to_decimal(row["conversions_total"])
        conversion_value = _to_decimal(row["conversion_value_total"])
        payload.append(
            {
                "customer_id": row["customer_id"],
                "campaign_id": row["campaign_id"],
                "campaign_name": row["campaign_name"],
                "channel_type": row["advertising_channel_type"],
                "campaign_status": row["campaign_status"],
                "spend": float(spend),
                "impressions": float(impressions),
                "clicks": float(clicks),
                "ctr": float(_safe_div(clicks, impressions)),
                "avg_cpc": float(_safe_div(spend, clicks)),
                "conversions": float(conversions),
                "conversion_value": float(conversion_value),
                "cpa": float(_safe_div(spend, conversions)),
                "roas": float(_safe_div(conversion_value, spend)),
            }
        )
    return payload


class GoogleAdsExecutiveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401
        serializer = GoogleAdsExecutiveQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        payload = _build_executive_payload(
            user=request.user,
            validated=serializer.validated_data,
            cache_key_prefix="gads-exec",
        )
        return Response(payload)


class GoogleAdsWorkspaceSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401
        serializer = GoogleAdsExecutiveQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        payload = _build_executive_payload(
            user=request.user,
            validated=validated,
            cache_key_prefix="gads-workspace-summary",
        ).copy()

        end_date = validated["end_date"]
        recent_start = end_date - timedelta(days=7)

        changes_qs = GoogleAdsSdkChangeEvent.objects.filter(
            tenant_id=request.user.tenant_id,
            change_date_time__date__gte=recent_start,
            change_date_time__date__lte=end_date,
        )
        changes_qs = _apply_customer_scope(changes_qs, request.user)
        customer_id = (validated.get("customer_id") or "").strip()
        if customer_id:
            changes_qs = changes_qs.filter(customer_id=customer_id)

        recs_qs = GoogleAdsSdkRecommendation.objects.filter(tenant_id=request.user.tenant_id)
        recs_qs = _apply_customer_scope(recs_qs, request.user)
        if customer_id:
            recs_qs = recs_qs.filter(customer_id=customer_id)

        disapproved_qs = GoogleAdsSdkAdGroupAdDaily.objects.filter(tenant_id=request.user.tenant_id)
        disapproved_qs = _apply_customer_scope(disapproved_qs, request.user)
        disapproved_qs = _apply_date_and_common_filters(disapproved_qs, validated)
        disapproved_count = disapproved_qs.filter(policy_approval_status="DISAPPROVED").values("ad_id").distinct().count()

        metrics = payload.get("metrics", {})
        comparison = payload.get("comparison", {})
        spend = _to_decimal(metrics.get("spend"))
        prev_spend = _to_decimal(comparison.get("spend"))
        conversions = _to_decimal(metrics.get("conversions"))
        prev_conversions = _to_decimal(comparison.get("conversions"))
        clicks = _to_decimal(metrics.get("clicks"))

        overspend_risk = _to_decimal(payload["pacing"]["forecast_month_end"]) > (
            _to_decimal(payload["pacing"]["budget_month"]) * Decimal("1.10")
        )
        underdelivery = _to_decimal(payload["pacing"]["forecast_month_end"]) < (
            _to_decimal(payload["pacing"]["budget_month"]) * Decimal("0.80")
        ) if _to_decimal(payload["pacing"]["budget_month"]) > 0 else False
        spend_spike = prev_spend > 0 and spend > (prev_spend * Decimal("2"))
        conversion_drop = prev_conversions > 0 and clicks >= Decimal("10") and conversions < (prev_conversions * Decimal("0.60"))

        top_insights: list[dict[str, str]] = []
        if overspend_risk:
            top_insights.append(
                {
                    "id": "overspend_risk",
                    "title": "Overspend risk",
                    "detail": "Forecasted month-end spend is above plan by more than 10%.",
                }
            )
        if conversion_drop:
            top_insights.append(
                {
                    "id": "conversion_drop",
                    "title": "Conversion drop",
                    "detail": "Conversions are down materially versus the comparison window.",
                }
            )
        if spend_spike:
            top_insights.append(
                {
                    "id": "spend_spike",
                    "title": "Spend spike",
                    "detail": "Spend is more than 2x the comparison window baseline.",
                }
            )
        movers = payload.get("movers", [])
        if movers:
            top_mover = movers[0]
            top_insights.append(
                {
                    "id": "top_mover",
                    "title": "Top spend driver",
                    "detail": f"{top_mover.get('campaign_name') or top_mover.get('campaign_id')} leads spend this period.",
                }
            )

        payload["alerts_summary"] = {
            "overspend_risk": overspend_risk,
            "underdelivery": underdelivery,
            "spend_spike": spend_spike,
            "conversion_drop": conversion_drop,
        }
        payload["governance_summary"] = {
            "recent_changes_7d": changes_qs.count(),
            "active_recommendations": recs_qs.filter(dismissed=False).count(),
            "disapproved_ads": disapproved_count,
        }
        payload["top_insights"] = top_insights[:3]
        payload["workspace_generated_at"] = timezone.now().isoformat()
        return Response(payload)


class GoogleAdsCampaignListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401
        serializer = GoogleAdsListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        qs = GoogleAdsSdkCampaignDaily.objects.filter(tenant_id=request.user.tenant_id)
        qs = _apply_customer_scope(qs, request.user)
        qs = _apply_date_and_common_filters(qs, validated)

        rows = list(
            qs.values(
                "customer_id",
                "campaign_id",
                "campaign_name",
                "campaign_status",
                "advertising_channel_type",
            )
            .annotate(
                spend_micros=Sum("cost_micros"),
                impressions_total=Sum("impressions"),
                clicks_total=Sum("clicks"),
                conversions_total=Sum("conversions"),
                conversion_value_total=Sum("conversions_value"),
            )
        )

        query = validated.get("q", "").strip().lower()
        payload = []
        for row in rows:
            campaign_name = row["campaign_name"] or row["campaign_id"]
            if query and query not in campaign_name.lower():
                continue
            spend = _micros_to_currency(row["spend_micros"])
            impressions = _to_decimal(row["impressions_total"])
            clicks = _to_decimal(row["clicks_total"])
            conversions = _to_decimal(row["conversions_total"])
            conv_value = _to_decimal(row["conversion_value_total"])
            payload.append(
                {
                    "customer_id": row["customer_id"],
                    "campaign_id": row["campaign_id"],
                    "campaign_name": campaign_name,
                    "campaign_status": row["campaign_status"],
                    "channel_type": row["advertising_channel_type"],
                    "spend": float(spend),
                    "impressions": float(impressions),
                    "clicks": float(clicks),
                    "ctr": float(_safe_div(clicks, impressions)),
                    "avg_cpc": float(_safe_div(spend, clicks)),
                    "conversions": float(conversions),
                    "cpa": float(_safe_div(spend, conversions)),
                    "conversion_value": float(conv_value),
                    "roas": float(_safe_div(conv_value, spend)),
                }
            )

        sort = validated.get("sort", "-spend")
        reverse = sort.startswith("-")
        sort_key = sort[1:] if reverse else sort
        if sort_key not in {
            "campaign_name",
            "spend",
            "clicks",
            "impressions",
            "conversions",
            "roas",
            "cpa",
        }:
            sort_key = "spend"
            reverse = True
        payload.sort(key=lambda row: row.get(sort_key) or 0, reverse=reverse)

        paginator = Paginator(payload, validated["page_size"])
        page_obj = paginator.get_page(validated["page"])
        return Response(
            {
                "count": paginator.count,
                "page": page_obj.number,
                "page_size": validated["page_size"],
                "num_pages": paginator.num_pages,
                "results": list(page_obj.object_list),
                "source_engine": _source_engine_for_tenant(str(request.user.tenant_id)),
            }
        )


class GoogleAdsCampaignDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, campaign_id: str) -> Response:  # noqa: D401
        serializer = GoogleAdsDateRangeQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        qs = GoogleAdsSdkCampaignDaily.objects.filter(
            tenant_id=request.user.tenant_id,
            campaign_id=campaign_id,
        )
        qs = _apply_customer_scope(qs, request.user)
        qs = _apply_date_and_common_filters(qs, validated)

        aggregate = qs.aggregate(
            spend_micros=Sum("cost_micros"),
            impressions_total=Sum("impressions"),
            clicks_total=Sum("clicks"),
            conversions_total=Sum("conversions"),
            conversion_value_total=Sum("conversions_value"),
            campaign_name=Max("campaign_name"),
            campaign_status=Max("campaign_status"),
            channel_type=Max("advertising_channel_type"),
        )
        spend = _micros_to_currency(aggregate["spend_micros"])
        impressions = _to_decimal(aggregate["impressions_total"])
        clicks = _to_decimal(aggregate["clicks_total"])
        conversions = _to_decimal(aggregate["conversions_total"])
        conversion_value = _to_decimal(aggregate["conversion_value_total"])

        trend_rows = (
            qs.values("date_day")
            .annotate(
                spend_micros=Sum("cost_micros"),
                clicks_total=Sum("clicks"),
                conversions_total=Sum("conversions"),
                conversion_value_total=Sum("conversions_value"),
            )
            .order_by("date_day")
        )
        trend = []
        for row in trend_rows:
            day_spend = _micros_to_currency(row["spend_micros"])
            day_conv = _to_decimal(row["conversions_total"])
            day_conv_value = _to_decimal(row["conversion_value_total"])
            trend.append(
                {
                    "date": row["date_day"].isoformat(),
                    "spend": float(day_spend),
                    "clicks": float(_to_decimal(row["clicks_total"])),
                    "conversions": float(day_conv),
                    "roas": float(_safe_div(day_conv_value, day_spend)),
                }
            )

        return Response(
            {
                "campaign_id": campaign_id,
                "campaign_name": aggregate["campaign_name"] or campaign_id,
                "campaign_status": aggregate["campaign_status"] or "",
                "channel_type": aggregate["channel_type"] or "",
                "metrics": _metric_payload(
                    spend=spend,
                    impressions=impressions,
                    clicks=clicks,
                    conversions=conversions,
                    conv_value=conversion_value,
                ),
                "trend": trend,
                "source_engine": _source_engine_for_tenant(str(request.user.tenant_id)),
            }
        )


class GoogleAdsAdGroupsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401
        serializer = GoogleAdsListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        qs = GoogleAdsSdkAdGroupAdDaily.objects.filter(tenant_id=request.user.tenant_id)
        qs = _apply_customer_scope(qs, request.user)
        qs = _apply_date_and_common_filters(qs, validated)

        rows = (
            qs.values("customer_id", "campaign_id", "ad_group_id")
            .annotate(
                spend_micros=Sum("cost_micros"),
                impressions_total=Sum("impressions"),
                clicks_total=Sum("clicks"),
                conversions_total=Sum("conversions"),
                conversion_value_total=Sum("conversions_value"),
            )
            .order_by("campaign_id", "ad_group_id")
        )
        payload = []
        for row in rows:
            spend = _micros_to_currency(row["spend_micros"])
            clicks = _to_decimal(row["clicks_total"])
            impressions = _to_decimal(row["impressions_total"])
            conversions = _to_decimal(row["conversions_total"])
            conversion_value = _to_decimal(row["conversion_value_total"])
            payload.append(
                {
                    "customer_id": row["customer_id"],
                    "campaign_id": row["campaign_id"],
                    "ad_group_id": row["ad_group_id"],
                    "spend": float(spend),
                    "impressions": float(impressions),
                    "clicks": float(clicks),
                    "ctr": float(_safe_div(clicks, impressions)),
                    "conversions": float(conversions),
                    "cpa": float(_safe_div(spend, conversions)),
                    "conversion_value": float(conversion_value),
                    "roas": float(_safe_div(conversion_value, spend)),
                }
            )
        return Response({"count": len(payload), "results": payload})


class GoogleAdsAdsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401
        serializer = GoogleAdsListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        qs = GoogleAdsSdkAdGroupAdDaily.objects.filter(tenant_id=request.user.tenant_id)
        qs = _apply_customer_scope(qs, request.user)
        qs = _apply_date_and_common_filters(qs, validated)

        rows = (
            qs.values(
                "customer_id",
                "campaign_id",
                "ad_group_id",
                "ad_id",
                "ad_name",
                "ad_status",
                "policy_approval_status",
                "policy_review_status",
            )
            .annotate(
                spend_micros=Sum("cost_micros"),
                impressions_total=Sum("impressions"),
                clicks_total=Sum("clicks"),
                conversions_total=Sum("conversions"),
            )
            .order_by("-spend_micros")
        )

        payload = []
        for row in rows:
            spend = _micros_to_currency(row["spend_micros"])
            conversions = _to_decimal(row["conversions_total"])
            payload.append(
                {
                    "customer_id": row["customer_id"],
                    "campaign_id": row["campaign_id"],
                    "ad_group_id": row["ad_group_id"],
                    "ad_id": row["ad_id"],
                    "ad_name": row["ad_name"],
                    "ad_status": row["ad_status"],
                    "policy_approval_status": row["policy_approval_status"],
                    "policy_review_status": row["policy_review_status"],
                    "spend": float(spend),
                    "impressions": float(_to_decimal(row["impressions_total"])),
                    "clicks": float(_to_decimal(row["clicks_total"])),
                    "conversions": float(conversions),
                    "cpa": float(_safe_div(spend, conversions)),
                }
            )
        return Response({"count": len(payload), "results": payload})


class GoogleAdsAssetsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401
        serializer = GoogleAdsListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data
        qs = GoogleAdsSdkAdGroupAdDaily.objects.filter(tenant_id=request.user.tenant_id)
        qs = _apply_customer_scope(qs, request.user)
        qs = _apply_date_and_common_filters(qs, validated)
        rows = (
            qs.values("ad_id", "ad_name", "policy_approval_status", "policy_review_status")
            .annotate(
                spend_micros=Sum("cost_micros"),
                clicks_total=Sum("clicks"),
                impressions_total=Sum("impressions"),
            )
            .order_by("-spend_micros")
        )
        payload = [
            {
                "asset_id": row["ad_id"],
                "asset_name": row["ad_name"],
                "asset_type": "ad",
                "policy_approval_status": row["policy_approval_status"],
                "policy_review_status": row["policy_review_status"],
                "spend": float(_micros_to_currency(row["spend_micros"])),
                "clicks": float(_to_decimal(row["clicks_total"])),
                "impressions": float(_to_decimal(row["impressions_total"])),
            }
            for row in rows
        ]
        return Response({"count": len(payload), "results": payload})


class GoogleAdsKeywordsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401
        serializer = GoogleAdsListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        qs = GoogleAdsSdkKeywordDaily.objects.filter(tenant_id=request.user.tenant_id)
        qs = _apply_customer_scope(qs, request.user)
        qs = _apply_date_and_common_filters(qs, validated)

        rows = (
            qs.values(
                "customer_id",
                "campaign_id",
                "ad_group_id",
                "criterion_id",
                "keyword_text",
                "match_type",
                "criterion_status",
                "quality_score",
                "ad_relevance",
                "expected_ctr",
                "landing_page_experience",
            )
            .annotate(
                spend_micros=Sum("cost_micros"),
                impressions_total=Sum("impressions"),
                clicks_total=Sum("clicks"),
                conversions_total=Sum("conversions"),
            )
            .order_by("-spend_micros")
        )

        payload = []
        for row in rows:
            spend = _micros_to_currency(row["spend_micros"])
            clicks = _to_decimal(row["clicks_total"])
            impressions = _to_decimal(row["impressions_total"])
            conversions = _to_decimal(row["conversions_total"])
            payload.append(
                {
                    "customer_id": row["customer_id"],
                    "campaign_id": row["campaign_id"],
                    "ad_group_id": row["ad_group_id"],
                    "criterion_id": row["criterion_id"],
                    "keyword_text": row["keyword_text"],
                    "match_type": row["match_type"],
                    "status": row["criterion_status"],
                    "quality_score": row["quality_score"],
                    "ad_relevance": row["ad_relevance"],
                    "expected_ctr": row["expected_ctr"],
                    "landing_page_experience": row["landing_page_experience"],
                    "spend": float(spend),
                    "impressions": float(impressions),
                    "clicks": float(clicks),
                    "ctr": float(_safe_div(clicks, impressions)),
                    "conversions": float(conversions),
                    "cpa": float(_safe_div(spend, conversions)),
                }
            )

        return Response({"count": len(payload), "results": payload})


class GoogleAdsSearchTermsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401
        serializer = GoogleAdsListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        qs = GoogleAdsSdkSearchTermDaily.objects.filter(tenant_id=request.user.tenant_id)
        qs = _apply_customer_scope(qs, request.user)
        qs = _apply_date_and_common_filters(qs, validated)

        rows = (
            qs.values(
                "customer_id",
                "campaign_id",
                "ad_group_id",
                "criterion_id",
                "search_term",
            )
            .annotate(
                spend_micros=Sum("cost_micros"),
                impressions_total=Sum("impressions"),
                clicks_total=Sum("clicks"),
                conversions_total=Sum("conversions"),
            )
            .order_by("-spend_micros")
        )

        payload = []
        for row in rows:
            spend = _micros_to_currency(row["spend_micros"])
            clicks = _to_decimal(row["clicks_total"])
            impressions = _to_decimal(row["impressions_total"])
            conversions = _to_decimal(row["conversions_total"])
            payload.append(
                {
                    "customer_id": row["customer_id"],
                    "campaign_id": row["campaign_id"],
                    "ad_group_id": row["ad_group_id"],
                    "criterion_id": row["criterion_id"],
                    "search_term": row["search_term"],
                    "spend": float(spend),
                    "impressions": float(impressions),
                    "clicks": float(clicks),
                    "ctr": float(_safe_div(clicks, impressions)),
                    "conversions": float(conversions),
                    "cpa": float(_safe_div(spend, conversions)),
                }
            )
        return Response({"count": len(payload), "results": payload})


class GoogleAdsSearchTermInsightsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401
        serializer = GoogleAdsDateRangeQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        qs = GoogleAdsSdkSearchTermDaily.objects.filter(tenant_id=request.user.tenant_id)
        qs = _apply_customer_scope(qs, request.user)
        qs = _apply_date_and_common_filters(qs, validated)

        current_terms = list(qs.values("search_term", "cost_micros", "clicks", "impressions", "conversions"))
        categories: dict[str, dict[str, Decimal]] = {}
        for row in current_terms:
            term = str(row["search_term"] or "").strip()
            if not term:
                continue
            category = term.split()[0].lower()[:64]
            bucket = categories.setdefault(
                category,
                {
                    "spend": Decimal("0"),
                    "clicks": Decimal("0"),
                    "impressions": Decimal("0"),
                    "conversions": Decimal("0"),
                },
            )
            bucket["spend"] += _micros_to_currency(row["cost_micros"])
            bucket["clicks"] += _to_decimal(row["clicks"])
            bucket["impressions"] += _to_decimal(row["impressions"])
            bucket["conversions"] += _to_decimal(row["conversions"])

        compare_start, compare_end = _period_compare_window(validated["start_date"], validated["end_date"])
        prev_qs = GoogleAdsSdkSearchTermDaily.objects.filter(
            tenant_id=request.user.tenant_id,
            date_day__gte=compare_start,
            date_day__lte=compare_end,
        )
        prev_qs = _apply_customer_scope(prev_qs, request.user)
        previous_terms = list(prev_qs.values("search_term", "clicks"))
        prev_clicks_by_category: dict[str, Decimal] = {}
        for row in previous_terms:
            term = str(row["search_term"] or "").strip()
            if not term:
                continue
            category = term.split()[0].lower()[:64]
            prev_clicks_by_category[category] = prev_clicks_by_category.get(category, Decimal("0")) + _to_decimal(
                row["clicks"]
            )

        category_rows = []
        for category, metrics in categories.items():
            prev_clicks = prev_clicks_by_category.get(category, Decimal("0"))
            current_clicks = metrics["clicks"]
            growth_ratio = float(_safe_div(current_clicks - prev_clicks, prev_clicks)) if prev_clicks > 0 else None
            category_rows.append(
                {
                    "category": category,
                    "spend": float(metrics["spend"]),
                    "clicks": float(current_clicks),
                    "impressions": float(metrics["impressions"]),
                    "conversions": float(metrics["conversions"]),
                    "is_new": prev_clicks == 0,
                    "click_growth_ratio": growth_ratio,
                }
            )
        category_rows.sort(key=lambda row: row["spend"], reverse=True)

        rising = [row for row in category_rows if (row["click_growth_ratio"] or 0) > 0.5][:10]
        new_queries = [row for row in category_rows if row["is_new"]][:10]

        return Response(
            {
                "count": len(category_rows),
                "results": category_rows[:100],
                "rising": rising,
                "new": new_queries,
                "availability": {
                    "source": "search_term_view_grouping",
                    "native_search_term_insights": False,
                },
            }
        )


class GoogleAdsPmaxAssetGroupsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401
        serializer = GoogleAdsListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        qs = GoogleAdsSdkAssetGroupDaily.objects.filter(tenant_id=request.user.tenant_id)
        qs = _apply_customer_scope(qs, request.user)
        qs = _apply_date_and_common_filters(qs, validated)

        rows = (
            qs.values(
                "customer_id",
                "campaign_id",
                "asset_group_id",
                "asset_group_name",
                "asset_group_status",
            )
            .annotate(
                spend_micros=Sum("cost_micros"),
                impressions_total=Sum("impressions"),
                clicks_total=Sum("clicks"),
                conversions_total=Sum("conversions"),
                conversion_value_total=Sum("conversions_value"),
            )
            .order_by("-spend_micros")
        )

        payload = []
        for row in rows:
            spend = _micros_to_currency(row["spend_micros"])
            conv_value = _to_decimal(row["conversion_value_total"])
            conversions = _to_decimal(row["conversions_total"])
            payload.append(
                {
                    "customer_id": row["customer_id"],
                    "campaign_id": row["campaign_id"],
                    "asset_group_id": row["asset_group_id"],
                    "asset_group_name": row["asset_group_name"],
                    "asset_group_status": row["asset_group_status"],
                    "spend": float(spend),
                    "impressions": float(_to_decimal(row["impressions_total"])),
                    "clicks": float(_to_decimal(row["clicks_total"])),
                    "conversions": float(conversions),
                    "conversion_value": float(conv_value),
                    "roas": float(_safe_div(conv_value, spend)),
                    "cpa": float(_safe_div(spend, conversions)),
                }
            )

        return Response({"count": len(payload), "results": payload})


class GoogleAdsBreakdownsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401
        serializer = GoogleAdsBreakdownQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        dimension = validated["dimension"]
        if dimension != "location":
            return Response(
                {
                    "dimension": dimension,
                    "count": 0,
                    "results": [],
                    "availability": {
                        "supported": False,
                        "reason": "dimension_not_ingested_yet",
                    },
                }
            )

        qs = GoogleAdsSdkGeographicDaily.objects.filter(tenant_id=request.user.tenant_id)
        qs = _apply_customer_scope(qs, request.user)
        qs = _apply_date_and_common_filters(qs, validated)

        rows = (
            qs.values("geo_target_country", "geo_target_region", "geo_target_city")
            .annotate(
                spend_micros=Sum("cost_micros"),
                impressions_total=Sum("impressions"),
                clicks_total=Sum("clicks"),
                conversions_total=Sum("conversions"),
            )
            .order_by("-spend_micros")
        )

        payload = [
            {
                "country": row["geo_target_country"],
                "region": row["geo_target_region"],
                "city": row["geo_target_city"],
                "spend": float(_micros_to_currency(row["spend_micros"])),
                "impressions": float(_to_decimal(row["impressions_total"])),
                "clicks": float(_to_decimal(row["clicks_total"])),
                "conversions": float(_to_decimal(row["conversions_total"])),
            }
            for row in rows
        ]
        return Response({"dimension": "location", "count": len(payload), "results": payload})


class GoogleAdsConversionsByActionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401
        serializer = GoogleAdsDateRangeQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        qs = GoogleAdsSdkConversionActionDaily.objects.filter(tenant_id=request.user.tenant_id)
        qs = _apply_customer_scope(qs, request.user)
        qs = _apply_date_and_common_filters(qs, validated)

        rows = (
            qs.values(
                "customer_id",
                "conversion_action_id",
                "conversion_action_name",
                "conversion_action_type",
            )
            .annotate(
                conversions_total=Sum("conversions"),
                all_conversions_total=Sum("all_conversions"),
                conversion_value_total=Sum("conversions_value"),
            )
            .order_by("-conversion_value_total")
        )

        payload = [
            {
                "customer_id": row["customer_id"],
                "conversion_action_id": row["conversion_action_id"],
                "conversion_action_name": row["conversion_action_name"],
                "conversion_action_type": row["conversion_action_type"],
                "conversions": float(_to_decimal(row["conversions_total"])),
                "all_conversions": float(_to_decimal(row["all_conversions_total"])),
                "conversion_value": float(_to_decimal(row["conversion_value_total"])),
            }
            for row in rows
        ]
        return Response({"count": len(payload), "results": payload})


class GoogleAdsBudgetPacingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401
        serializer = GoogleAdsDateRangeQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        month_end = validated["end_date"]
        month_start = month_end.replace(day=1)
        qs = GoogleAdsSdkCampaignDaily.objects.filter(
            tenant_id=request.user.tenant_id,
            date_day__gte=month_start,
            date_day__lte=month_end,
        )
        qs = _apply_customer_scope(qs, request.user)
        spend_mtd = _micros_to_currency(qs.aggregate(spend_micros=Sum("cost_micros"))["spend_micros"])

        budget_total = _to_decimal(
            CampaignBudget.objects.filter(tenant_id=request.user.tenant_id, is_active=True).aggregate(
                total=Sum("monthly_target")
            )["total"]
        )
        elapsed_days = max(month_end.day, 1)
        _, total_days = monthrange(month_end.year, month_end.month)
        forecast_month_end = spend_mtd / Decimal(elapsed_days) * Decimal(total_days)

        overspend_risk = forecast_month_end > (budget_total * Decimal("1.10")) if budget_total > 0 else False
        underdelivery = forecast_month_end < (budget_total * Decimal("0.80")) if budget_total > 0 else False

        return Response(
            {
                "month": month_end.strftime("%Y-%m"),
                "spend_mtd": float(spend_mtd),
                "budget_month": float(budget_total),
                "forecast_month_end": float(forecast_month_end),
                "over_under": float(forecast_month_end - budget_total),
                "runway_days": float(_safe_div((budget_total - spend_mtd), _safe_div(spend_mtd, Decimal(elapsed_days))))
                if spend_mtd > 0
                else None,
                "alerts": {
                    "overspend_risk": overspend_risk,
                    "underdelivery": underdelivery,
                },
            }
        )


class GoogleAdsChangeEventsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401
        serializer = GoogleAdsListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        page = validated["page"]
        page_size = validated["page_size"]

        qs = GoogleAdsSdkChangeEvent.objects.filter(
            tenant_id=request.user.tenant_id,
            change_date_time__date__gte=validated["start_date"],
            change_date_time__date__lte=validated["end_date"],
        )
        qs = _apply_customer_scope(qs, request.user)
        customer_id = (validated.get("customer_id") or "").strip()
        if customer_id:
            qs = qs.filter(customer_id=customer_id)

        rows = qs.order_by("-change_date_time")
        paginator = Paginator(rows, page_size)
        page_obj = paginator.get_page(page)
        payload = [
            {
                "customer_id": row.customer_id,
                "change_date_time": row.change_date_time.isoformat(),
                "user_email": row.user_email,
                "client_type": row.client_type,
                "change_resource_type": row.change_resource_type,
                "resource_change_operation": row.resource_change_operation,
                "campaign_id": row.campaign_id,
                "ad_group_id": row.ad_group_id,
                "ad_id": row.ad_id,
                "changed_fields": row.changed_fields,
            }
            for row in page_obj.object_list
        ]
        return Response(
            {
                "count": paginator.count,
                "page": page_obj.number,
                "page_size": page_size,
                "num_pages": paginator.num_pages,
                "results": payload,
            }
        )


class GoogleAdsRecommendationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401
        serializer = GoogleAdsListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        qs = GoogleAdsSdkRecommendation.objects.filter(tenant_id=request.user.tenant_id)
        qs = _apply_customer_scope(qs, request.user)
        customer_id = (validated.get("customer_id") or "").strip()
        if customer_id:
            qs = qs.filter(customer_id=customer_id)

        rows = qs.order_by("dismissed", "-last_seen_at")
        payload = [
            {
                "customer_id": row.customer_id,
                "recommendation_type": row.recommendation_type,
                "resource_name": row.resource_name,
                "campaign_id": row.campaign_id,
                "ad_group_id": row.ad_group_id,
                "dismissed": row.dismissed,
                "impact_metadata": row.impact_metadata,
                "last_seen_at": row.last_seen_at.isoformat(),
            }
            for row in rows
        ]
        return Response({"count": len(payload), "results": payload})


class GoogleAdsChannelPerformanceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request) -> Response:  # noqa: D401
        serializer = GoogleAdsDateRangeQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        qs = GoogleAdsSdkCampaignDaily.objects.filter(tenant_id=request.user.tenant_id)
        qs = _apply_customer_scope(qs, request.user)
        qs = _apply_date_and_common_filters(qs, validated)

        rows = (
            qs.values("advertising_channel_type")
            .annotate(
                spend_micros=Sum("cost_micros"),
                impressions_total=Sum("impressions"),
                clicks_total=Sum("clicks"),
                conversions_total=Sum("conversions"),
                conversion_value_total=Sum("conversions_value"),
            )
            .order_by("-spend_micros")
        )
        payload = []
        for row in rows:
            spend = _micros_to_currency(row["spend_micros"])
            conversion_value = _to_decimal(row["conversion_value_total"])
            payload.append(
                {
                    "channel_type": row["advertising_channel_type"] or "UNKNOWN",
                    "spend": float(spend),
                    "impressions": float(_to_decimal(row["impressions_total"])),
                    "clicks": float(_to_decimal(row["clicks_total"])),
                    "conversions": float(_to_decimal(row["conversions_total"])),
                    "conversion_value": float(conversion_value),
                    "roas": float(_safe_div(conversion_value, spend)),
                }
            )
        return Response({"count": len(payload), "results": payload})


class GoogleAdsSavedViewViewSet(viewsets.ModelViewSet):
    serializer_class = GoogleAdsSavedViewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = GoogleAdsSavedView.objects.filter(tenant_id=user.tenant_id)
        if _is_admin(user):
            return queryset.order_by("-updated_at")
        return queryset.filter(Q(is_shared=True) | Q(created_by_id=user.id)).order_by("-updated_at")

    def perform_create(self, serializer):
        user = self.request.user
        record = serializer.save(
            tenant=user.tenant,
            created_by=user,
            updated_by=user,
        )
        log_audit_event(
            tenant=user.tenant,
            user=user,
            action="google_ads_saved_view_created",
            resource_type="google_ads_saved_view",
            resource_id=record.id,
            metadata={"name": record.name},
        )

    def perform_update(self, serializer):
        user = self.request.user
        record = serializer.save(updated_by=user)
        log_audit_event(
            tenant=user.tenant,
            user=user,
            action="google_ads_saved_view_updated",
            resource_type="google_ads_saved_view",
            resource_id=record.id,
            metadata={"name": record.name},
        )

    def perform_destroy(self, instance):
        user = self.request.user
        if not _is_admin(user) and instance.created_by_id != user.id:
            raise PermissionDenied("Only owners or admins can delete saved views.")
        record_id = instance.id
        super().perform_destroy(instance)
        log_audit_event(
            tenant=user.tenant,
            user=user,
            action="google_ads_saved_view_deleted",
            resource_type="google_ads_saved_view",
            resource_id=record_id,
            metadata={},
        )


class GoogleAdsAccountAssignmentViewSet(viewsets.ModelViewSet):
    serializer_class = GoogleAdsAccountAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = GoogleAdsAccountAssignment.objects.filter(tenant_id=user.tenant_id).order_by("customer_id")
        if _is_admin(user):
            return queryset
        return queryset.filter(user_id=user.id)

    def perform_create(self, serializer):
        user = self.request.user
        if not _is_admin(user):
            raise PermissionDenied("Only admins can assign account access.")
        record = serializer.save(tenant=user.tenant)
        log_audit_event(
            tenant=user.tenant,
            user=user,
            action="google_ads_account_assignment_created",
            resource_type="google_ads_account_assignment",
            resource_id=record.id,
            metadata={"customer_id": record.customer_id, "user_id": str(record.user_id)},
        )

    def perform_update(self, serializer):
        user = self.request.user
        if not _is_admin(user):
            raise PermissionDenied("Only admins can update account access.")
        record = serializer.save()
        log_audit_event(
            tenant=user.tenant,
            user=user,
            action="google_ads_account_assignment_updated",
            resource_type="google_ads_account_assignment",
            resource_id=record.id,
            metadata={"customer_id": record.customer_id, "user_id": str(record.user_id)},
        )

    def perform_destroy(self, instance):
        user = self.request.user
        if not _is_admin(user):
            raise PermissionDenied("Only admins can remove account access.")
        record_id = instance.id
        super().perform_destroy(instance)
        log_audit_event(
            tenant=user.tenant,
            user=user,
            action="google_ads_account_assignment_deleted",
            resource_type="google_ads_account_assignment",
            resource_id=record_id,
            metadata={},
        )


class GoogleAdsExportCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request) -> Response:  # noqa: D401
        serializer = GoogleAdsExportCreateSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data
        filters = validated.get("filters") if isinstance(validated.get("filters"), dict) else {}

        job = GoogleAdsExportJob.objects.create(
            tenant=request.user.tenant,
            requested_by=request.user,
            name=validated.get("name", ""),
            export_format=validated["export_format"],
            filters=filters,
            status=GoogleAdsExportJob.STATUS_RUNNING,
        )

        try:
            normalized_filters = GoogleAdsListQuerySerializer(data=filters)
            normalized_filters.is_valid(raise_exception=True)
            rows = _campaign_rows_for_export(request.user, normalized_filters.validated_data)

            output_dir = Path(settings.BASE_DIR) / "integrations" / "exporter" / "out" / "google_ads"
            output_dir.mkdir(parents=True, exist_ok=True)
            file_name = f"google_ads_export_{job.id}.csv"
            artifact_path = output_dir / file_name

            with artifact_path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(
                    csv_file,
                    fieldnames=[
                        "customer_id",
                        "campaign_id",
                        "campaign_name",
                        "channel_type",
                        "campaign_status",
                        "spend",
                        "impressions",
                        "clicks",
                        "ctr",
                        "avg_cpc",
                        "conversions",
                        "conversion_value",
                        "cpa",
                        "roas",
                    ],
                )
                writer.writeheader()
                writer.writerows(rows)

            metadata = {
                "row_count": len(rows),
                "requested_format": validated["export_format"],
                "actual_format": "csv",
            }
            if validated["export_format"] == GoogleAdsExportJob.FORMAT_PDF:
                metadata["note"] = "PDF generation currently falls back to CSV artifact for MVP."

            job.status = GoogleAdsExportJob.STATUS_COMPLETED
            job.artifact_path = f"/google_ads/{file_name}"
            job.completed_at = timezone.now()
            job.metadata = metadata
            job.error_message = ""
            job.save(update_fields=["status", "artifact_path", "completed_at", "metadata", "error_message", "updated_at"])
        except Exception as exc:  # pragma: no cover - defensive
            job.status = GoogleAdsExportJob.STATUS_FAILED
            job.error_message = str(exc)
            job.completed_at = timezone.now()
            job.save(update_fields=["status", "error_message", "completed_at", "updated_at"])

        return Response(GoogleAdsExportJobSerializer(job).data, status=status.HTTP_201_CREATED)


class GoogleAdsExportStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, job_id: str) -> Response:  # noqa: D401
        job = get_object_or_404(
            GoogleAdsExportJob.objects.filter(tenant_id=request.user.tenant_id),
            id=job_id,
        )
        payload = GoogleAdsExportJobSerializer(job).data
        payload["download_url"] = (
            f"/api/analytics/google-ads/exports/{job.id}/download/"
            if job.status == GoogleAdsExportJob.STATUS_COMPLETED and job.artifact_path
            else None
        )
        return Response(payload)


class GoogleAdsExportDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, job_id: str):  # noqa: D401
        job = get_object_or_404(
            GoogleAdsExportJob.objects.filter(tenant_id=request.user.tenant_id),
            id=job_id,
        )
        if job.status != GoogleAdsExportJob.STATUS_COMPLETED or not job.artifact_path:
            return Response({"detail": "Export is not ready."}, status=status.HTTP_409_CONFLICT)

        if not job.artifact_path.startswith("/google_ads/"):
            return Response({"detail": "Export artifact path is invalid."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        base_dir = Path(settings.BASE_DIR) / "integrations" / "exporter" / "out"
        artifact_path = (base_dir / job.artifact_path.lstrip("/")).resolve()
        if not str(artifact_path).startswith(str(base_dir.resolve())) or not artifact_path.exists():
            return Response({"detail": "Export artifact file was not found."}, status=status.HTTP_404_NOT_FOUND)

        response = FileResponse(artifact_path.open("rb"), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{artifact_path.name}"'
        return response
