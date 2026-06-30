"""Read-only Meta APIs backed by tenant-scoped analytics tables."""

from __future__ import annotations

import logging
from typing import Any

from django.db.models import Q, QuerySet
from django.utils.dateparse import parse_date
from rest_framework import permissions
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination

from core.db_error_responses import schema_out_of_date_response
from integrations.clients.resolver import resolve_client_accounts
from integrations.models import (
    Client as IntegrationsClient,
    ClientPlatformAccount,
)

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


# --- Sprint 5: Client grouping support --------------------------------------
#
# Meta stores ad account external_ids with and without the ``act_`` prefix in
# the wild. When a Client is linked via ``ClientPlatformAccount.external_id`` we
# can't know which form the stored record uses, so we build a permissive set
# containing both forms for every linked id. The caller filters on the full
# set using ``__in``.


def _variants(raw: str) -> list[str]:
    """Return both ``act_`` and bare-digit forms of an account id."""

    candidate = (raw or "").strip()
    if not candidate:
        return []
    if candidate.startswith("act_"):
        return [candidate, candidate[len("act_"):]]
    if candidate.isdigit():
        return [candidate, f"act_{candidate}"]
    return [candidate]


def _resolve_meta_account_ids(
    user, query_params: dict[str, Any] | Any
) -> tuple[list[str] | None, dict[str, Any] | None]:
    """Resolve the set of Meta ad account external_ids to scope the query by.

    Semantics:
        * ``None`` → no client-level restriction (legacy ``account_id`` path still
          applies via each view's existing filter).
        * ``[...]`` → filter Meta ad_account external_id ``__in=...`` (variants
          expanded so both ``act_123`` and ``123`` match).
        * ``[]`` → client resolved to zero Meta accounts or the explicit
          ``account_id`` isn't part of the client; caller should return empty.
    """

    client_id_raw = query_params.get("client_id")
    explicit_account = (query_params.get("account_id") or "").strip()

    if not client_id_raw:
        # Legacy path: no client-level restriction. Views apply their own
        # ``account_id`` filter if one was passed.
        return None, None

    client_id = str(client_id_raw)
    try:
        bundle = resolve_client_accounts(
            str(user.tenant_id),
            client_id,
            platforms={ClientPlatformAccount.PLATFORM_META_ADS},
        )
    except (IntegrationsClient.DoesNotExist, ValueError):
        return (
            [],
            {
                "client_id": client_id,
                "reason": "client_not_found",
                "meta_ad_account_ids": [],
            },
        )

    meta_ids = list(bundle.meta_ad_account_ids)
    meta: dict[str, Any] = {
        "client_id": client_id,
        "meta_ad_account_ids": meta_ids,
        "reason": None,
    }

    if explicit_account:
        bare = explicit_account[len("act_"):] if explicit_account.startswith("act_") else explicit_account
        act_form = explicit_account if explicit_account.startswith("act_") else f"act_{explicit_account}"
        if bare in meta_ids or act_form in meta_ids or explicit_account in meta_ids:
            return _variants(explicit_account), {**meta, "reason": "client_plus_account"}
        return [], {**meta, "reason": "account_not_in_client"}

    if not meta_ids:
        return [], {**meta, "reason": "no_meta_accounts_for_client"}

    # Expand each linked id to its variants for permissive matching.
    variants: list[str] = []
    for linked in meta_ids:
        variants.extend(_variants(linked))
    # Dedupe while preserving order.
    seen: set[str] = set()
    deduped = []
    for item in variants:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped, meta


def _attach_client_resolution(response, meta: dict[str, Any] | None):
    if meta is None:
        return response
    response["X-Adinsights-Resolved-Via"] = f"client:{meta.get('client_id', '')}"
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        data["client_resolution"] = meta
    return response


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

    def _resolution_meta(self) -> dict[str, Any] | None:
        """Lazily resolve + cache the client_id resolution for this request."""

        cached = getattr(self, "_cached_resolution", "MISS")
        if cached != "MISS":
            return cached
        _scoped, meta = _resolve_meta_account_ids(self.request.user, self.request.query_params)
        self._cached_resolution = meta
        return meta

    def _scoped_meta_ids(self) -> list[str] | None:
        scoped, meta = _resolve_meta_account_ids(self.request.user, self.request.query_params)
        self._cached_resolution = meta
        return scoped

    def list(self, request, *args, **kwargs):  # noqa: D401
        response = super().list(request, *args, **kwargs)
        return _attach_client_resolution(response, self._resolution_meta())


class MetaAccountsListView(TenantScopedMetaListView):
    serializer_class = MetaAccountSerializer

    def get_queryset(self):
        queryset = self._tenant_queryset(AdAccount.objects.all()).order_by("name", "external_id")
        scoped_ids = self._scoped_meta_ids()
        if scoped_ids is not None:
            queryset = queryset.filter(external_id__in=scoped_ids)
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
        scoped_ids = self._scoped_meta_ids()
        account_id = (self.request.query_params.get("account_id") or "").strip()
        search = (self.request.query_params.get("search") or "").strip()
        status_filter = (self.request.query_params.get("status") or "").strip()
        since = _query_date(self.request.query_params.get("since"))
        until = _query_date(self.request.query_params.get("until"))
        if scoped_ids is not None:
            # Client-scoped: resolver already intersected with account_id if given.
            queryset = queryset.filter(
                Q(account_external_id__in=scoped_ids)
                | Q(ad_account__external_id__in=scoped_ids)
            )
        elif account_id:
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
        scoped_ids = self._scoped_meta_ids()
        campaign_id = (self.request.query_params.get("campaign_id") or "").strip()
        account_id = (self.request.query_params.get("account_id") or "").strip()
        search = (self.request.query_params.get("search") or "").strip()
        status_filter = (self.request.query_params.get("status") or "").strip()
        since = _query_date(self.request.query_params.get("since"))
        until = _query_date(self.request.query_params.get("until"))
        if campaign_id:
            queryset = queryset.filter(campaign__external_id=campaign_id)
        if scoped_ids is not None:
            queryset = queryset.filter(
                Q(campaign__account_external_id__in=scoped_ids)
                | Q(campaign__ad_account__external_id__in=scoped_ids)
            )
        elif account_id:
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
        scoped_ids = self._scoped_meta_ids()
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
        if scoped_ids is not None:
            queryset = queryset.filter(
                Q(adset__campaign__account_external_id__in=scoped_ids)
                | Q(adset__campaign__ad_account__external_id__in=scoped_ids)
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

        scoped_ids = self._scoped_meta_ids()
        if scoped_ids is not None:
            queryset = queryset.filter(
                Q(ad_account__external_id__in=scoped_ids)
                | Q(campaign__account_external_id__in=scoped_ids)
            )
        elif account_id:
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
