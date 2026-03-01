"""Read-only Meta APIs backed by tenant-scoped analytics tables."""

from __future__ import annotations

import logging

from django.db.models import Q, QuerySet
from django.utils.dateparse import parse_date
from rest_framework import permissions
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination

from core.db_error_responses import schema_out_of_date_response

from .meta_serializers import (
    MetaAccountSerializer,
    MetaAdSerializer,
    MetaAdSetSerializer,
    MetaCampaignSerializer,
    MetaInsightSerializer,
    MetaInsightsQuerySerializer,
)
from .models import Ad, AdAccount, AdSet, Campaign, RawPerformanceRecord

logger = logging.getLogger(__name__)


def _normalize_account_id(value: str) -> str:
    candidate = value.strip()
    if candidate.startswith("act_"):
        return candidate
    if candidate.isdigit():
        return f"act_{candidate}"
    return candidate


def _query_date(value: str | None):
    if not value:
        return None
    return parse_date(value.strip())


class MetaPagePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class TenantScopedMetaListView(ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = MetaPagePagination

    def _tenant_queryset(self, queryset: QuerySet) -> QuerySet:
        tenant = getattr(self.request.user, "tenant", None)
        if tenant is None:
            return queryset.none()
        return queryset.filter(tenant=tenant)


class MetaAccountsListView(TenantScopedMetaListView):
    serializer_class = MetaAccountSerializer

    def get_queryset(self):
        queryset = self._tenant_queryset(AdAccount.objects.all()).order_by("name", "external_id")
        search = (self.request.query_params.get("search") or "").strip()
        status_filter = (self.request.query_params.get("status") or "").strip()
        since = _query_date(self.request.query_params.get("since"))
        until = _query_date(self.request.query_params.get("until"))
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(external_id__icontains=search)
                | Q(account_id__icontains=search)
            )
        if status_filter:
            queryset = queryset.filter(status__iexact=status_filter)
        if since:
            queryset = queryset.filter(updated_at__date__gte=since)
        if until:
            queryset = queryset.filter(updated_at__date__lte=until)
        return queryset


class MetaCampaignListView(TenantScopedMetaListView):
    serializer_class = MetaCampaignSerializer

    def get_queryset(self):
        queryset = (
            self._tenant_queryset(Campaign.objects.select_related("ad_account"))
            .filter(platform__iexact="meta")
            .order_by("name", "external_id")
        )
        account_id = (self.request.query_params.get("account_id") or "").strip()
        search = (self.request.query_params.get("search") or "").strip()
        status_filter = (self.request.query_params.get("status") or "").strip()
        since = _query_date(self.request.query_params.get("since"))
        until = _query_date(self.request.query_params.get("until"))
        if account_id:
            normalized = _normalize_account_id(account_id)
            queryset = queryset.filter(
                Q(account_external_id=account_id)
                | Q(account_external_id=normalized)
                | Q(ad_account__external_id=account_id)
                | Q(ad_account__external_id=normalized)
                | Q(ad_account__account_id=account_id.replace("act_", ""))
            )
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(external_id__icontains=search))
        if status_filter:
            queryset = queryset.filter(status__iexact=status_filter)
        if since:
            queryset = queryset.filter(updated_at__date__gte=since)
        if until:
            queryset = queryset.filter(updated_at__date__lte=until)
        return queryset


class MetaAdSetListView(TenantScopedMetaListView):
    serializer_class = MetaAdSetSerializer

    def get_queryset(self):
        queryset = (
            self._tenant_queryset(AdSet.objects.select_related("campaign", "campaign__ad_account"))
            .order_by("name", "external_id")
        )
        campaign_id = (self.request.query_params.get("campaign_id") or "").strip()
        account_id = (self.request.query_params.get("account_id") or "").strip()
        search = (self.request.query_params.get("search") or "").strip()
        status_filter = (self.request.query_params.get("status") or "").strip()
        since = _query_date(self.request.query_params.get("since"))
        until = _query_date(self.request.query_params.get("until"))
        if campaign_id:
            queryset = queryset.filter(campaign__external_id=campaign_id)
        if account_id:
            normalized = _normalize_account_id(account_id)
            queryset = queryset.filter(
                Q(campaign__account_external_id=account_id)
                | Q(campaign__account_external_id=normalized)
                | Q(campaign__ad_account__external_id=account_id)
                | Q(campaign__ad_account__external_id=normalized)
            )
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(external_id__icontains=search))
        if status_filter:
            queryset = queryset.filter(status__iexact=status_filter)
        if since:
            queryset = queryset.filter(updated_at__date__gte=since)
        if until:
            queryset = queryset.filter(updated_at__date__lte=until)
        return queryset


class MetaAdsListView(TenantScopedMetaListView):
    serializer_class = MetaAdSerializer

    def get_queryset(self):
        queryset = (
            self._tenant_queryset(Ad.objects.select_related("adset", "adset__campaign"))
            .order_by("name", "external_id")
        )
        adset_id = (self.request.query_params.get("adset_id") or "").strip()
        campaign_id = (self.request.query_params.get("campaign_id") or "").strip()
        search = (self.request.query_params.get("search") or "").strip()
        status_filter = (self.request.query_params.get("status") or "").strip()
        since = _query_date(self.request.query_params.get("since"))
        until = _query_date(self.request.query_params.get("until"))
        if adset_id:
            queryset = queryset.filter(adset__external_id=adset_id)
        if campaign_id:
            queryset = queryset.filter(adset__campaign__external_id=campaign_id)
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(external_id__icontains=search))
        if status_filter:
            queryset = queryset.filter(status__iexact=status_filter)
        if since:
            queryset = queryset.filter(updated_at__date__gte=since)
        if until:
            queryset = queryset.filter(updated_at__date__lte=until)
        return queryset


class MetaInsightsListView(TenantScopedMetaListView):
    serializer_class = MetaInsightSerializer

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except Exception as exc:  # pragma: no cover - exercised by API tests
            schema_response = schema_out_of_date_response(
                exc=exc,
                logger=logger,
                endpoint="analytics.meta_insights.list",
                tenant_id=getattr(request.user, "tenant_id", None),
            )
            if schema_response is not None:
                return schema_response
            raise

    def get_queryset(self):
        serializer = MetaInsightsQuerySerializer(data=self.request.query_params)
        serializer.is_valid(raise_exception=True)
        params = serializer.validated_data
        queryset = (
            self._tenant_queryset(
                RawPerformanceRecord.objects.select_related("ad_account", "campaign", "adset", "ad")
            )
            .filter(source__iexact="meta")
            .order_by("-date", "-updated_at")
        )
        account_id = params.get("account_id")
        level = params.get("level")
        since = params.get("since")
        until = params.get("until")
        search = (self.request.query_params.get("search") or "").strip()
        status_filter = (self.request.query_params.get("status") or "").strip()
        campaign_id = (self.request.query_params.get("campaign_id") or "").strip()
        adset_id = (self.request.query_params.get("adset_id") or "").strip()
        ad_id = (self.request.query_params.get("ad_id") or "").strip()

        if account_id:
            normalized = _normalize_account_id(str(account_id))
            queryset = queryset.filter(
                Q(ad_account__external_id=account_id)
                | Q(ad_account__external_id=normalized)
                | Q(campaign__account_external_id=account_id)
                | Q(campaign__account_external_id=normalized)
            )
        if level:
            queryset = queryset.filter(level=level)
        if since:
            queryset = queryset.filter(date__gte=since)
        if until:
            queryset = queryset.filter(date__lte=until)
        if campaign_id:
            queryset = queryset.filter(campaign__external_id=campaign_id)
        if adset_id:
            queryset = queryset.filter(adset__external_id=adset_id)
        if ad_id:
            queryset = queryset.filter(ad__external_id=ad_id)
        if search:
            queryset = queryset.filter(
                Q(external_id__icontains=search)
                | Q(campaign__name__icontains=search)
                | Q(adset__name__icontains=search)
                | Q(ad__name__icontains=search)
            )
        if status_filter:
            queryset = queryset.filter(
                Q(campaign__status__iexact=status_filter)
                | Q(adset__status__iexact=status_filter)
                | Q(ad__status__iexact=status_filter)
            )
        return queryset
