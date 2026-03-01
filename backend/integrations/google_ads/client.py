from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
from typing import Any, Iterator

from django.conf import settings

from integrations.google_ads.gaql_templates import render_gaql_template
from integrations.models import PlatformCredential


class GoogleAdsSdkError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        classification: str = "unknown",
        request_id: str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.classification = classification
        self.request_id = request_id
        self.retryable = retryable


@dataclass(frozen=True)
class CampaignDailyRow:
    customer_id: str
    campaign_id: str
    campaign_name: str
    campaign_status: str
    advertising_channel_type: str
    date_day: date
    currency_code: str
    impressions: int
    clicks: int
    conversions: Decimal
    conversions_value: Decimal
    cost_micros: int
    request_id: str


@dataclass(frozen=True)
class AdGroupAdDailyRow:
    customer_id: str
    campaign_id: str
    ad_group_id: str
    ad_id: str
    campaign_name: str
    ad_name: str
    ad_status: str
    policy_approval_status: str
    policy_review_status: str
    date_day: date
    currency_code: str
    impressions: int
    clicks: int
    conversions: Decimal
    conversions_value: Decimal
    cost_micros: int
    request_id: str


@dataclass(frozen=True)
class GeographicDailyRow:
    customer_id: str
    campaign_id: str
    date_day: date
    geo_target_country: str
    geo_target_region: str
    geo_target_city: str
    currency_code: str
    impressions: int
    clicks: int
    conversions: Decimal
    conversions_value: Decimal
    cost_micros: int
    request_id: str


@dataclass(frozen=True)
class KeywordDailyRow:
    customer_id: str
    campaign_id: str
    ad_group_id: str
    criterion_id: str
    keyword_text: str
    match_type: str
    criterion_status: str
    quality_score: int | None
    ad_relevance: str
    expected_ctr: str
    landing_page_experience: str
    date_day: date
    currency_code: str
    impressions: int
    clicks: int
    conversions: Decimal
    conversions_value: Decimal
    cost_micros: int
    request_id: str


@dataclass(frozen=True)
class SearchTermDailyRow:
    customer_id: str
    campaign_id: str
    ad_group_id: str
    criterion_id: str
    search_term: str
    date_day: date
    currency_code: str
    impressions: int
    clicks: int
    conversions: Decimal
    conversions_value: Decimal
    cost_micros: int
    request_id: str


@dataclass(frozen=True)
class AssetGroupDailyRow:
    customer_id: str
    campaign_id: str
    asset_group_id: str
    asset_group_name: str
    asset_group_status: str
    date_day: date
    currency_code: str
    impressions: int
    clicks: int
    conversions: Decimal
    conversions_value: Decimal
    cost_micros: int
    request_id: str


@dataclass(frozen=True)
class ConversionActionDailyRow:
    customer_id: str
    conversion_action_id: str
    conversion_action_name: str
    conversion_action_type: str
    date_day: date
    conversions: Decimal
    all_conversions: Decimal
    conversions_value: Decimal
    request_id: str


@dataclass(frozen=True)
class ChangeEventRow:
    customer_id: str
    event_fingerprint: str
    change_date_time: datetime
    user_email: str
    client_type: str
    change_resource_type: str
    resource_change_operation: str
    campaign_id: str
    ad_group_id: str
    ad_id: str
    changed_fields: list[str]
    request_id: str


@dataclass(frozen=True)
class RecommendationRow:
    customer_id: str
    recommendation_type: str
    resource_name: str
    campaign_id: str
    ad_group_id: str
    dismissed: bool
    impact_metadata: dict[str, Any]
    request_id: str


@dataclass(frozen=True)
class AccessibleCustomerRow:
    manager_customer_id: str
    customer_id: str
    customer_name: str
    currency_code: str
    time_zone: str
    status: str
    is_manager: bool


def _import_google_ads_symbols() -> tuple[type[Any], type[Exception]]:
    try:
        from google.ads.googleads.client import GoogleAdsClient  # type: ignore[import-not-found]
        from google.ads.googleads.errors import GoogleAdsException  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - exercised only when dependency missing
        raise GoogleAdsSdkError(
            "google-ads package is not installed. Install backend dependencies first.",
            classification="dependency_missing",
            retryable=False,
        ) from exc
    return GoogleAdsClient, GoogleAdsException


def _as_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"Unsupported date value: {value!r}")


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            raise ValueError("datetime string value is empty")
        normalized = candidate.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    raise ValueError(f"Unsupported datetime value: {value!r}")


def _as_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return 0
        return int(float(candidate))
    return int(value)


def _as_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if value is None:
        return False
    return bool(value)
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _classify_google_ads_exception(exc: Exception, google_ads_exception_cls: type[Exception]) -> GoogleAdsSdkError:
    if isinstance(exc, google_ads_exception_cls):
        request_id = getattr(exc, "request_id", None)
        failure = getattr(exc, "failure", None)
        retryable = False
        classification = "google_ads_api_error"
        if failure is not None:
            errors = getattr(failure, "errors", None) or []
            for error in errors:
                error_code = getattr(error, "error_code", None)
                code_repr = str(error_code).lower()
                if "quota" in code_repr or "rate" in code_repr or "internal" in code_repr:
                    retryable = True
                    classification = "google_ads_transient_error"
                    break
        return GoogleAdsSdkError(
            str(exc),
            classification=classification,
            request_id=request_id,
            retryable=retryable,
        )

    return GoogleAdsSdkError(
        str(exc),
        classification="google_ads_unknown_error",
        retryable=False,
    )


class GoogleAdsSdkClient:
    def __init__(self, *, credential: PlatformCredential, login_customer_id: str | None = None) -> None:
        self.credential = credential
        self.login_customer_id = login_customer_id or (getattr(settings, "GOOGLE_ADS_LOGIN_CUSTOMER_ID", "") or "")
        self._client = self._build_client()

    def _build_client(self):  # type: ignore[no-untyped-def]
        refresh_token = self.credential.decrypt_refresh_token()
        if not refresh_token:
            raise GoogleAdsSdkError(
                "Google credential does not include refresh token.",
                classification="missing_refresh_token",
                retryable=False,
            )
        client_id = (getattr(settings, "GOOGLE_ADS_CLIENT_ID", "") or "").strip()
        client_secret = (getattr(settings, "GOOGLE_ADS_CLIENT_SECRET", "") or "").strip()
        developer_token = (getattr(settings, "GOOGLE_ADS_DEVELOPER_TOKEN", "") or "").strip()
        if not client_id or not client_secret or not developer_token:
            raise GoogleAdsSdkError(
                "Google Ads SDK configuration is incomplete.",
                classification="misconfigured",
                retryable=False,
            )

        google_ads_client_cls, _ = _import_google_ads_symbols()
        config: dict[str, Any] = {
            "client_id": client_id,
            "client_secret": client_secret,
            "developer_token": developer_token,
            "refresh_token": refresh_token,
            "use_proto_plus": True,
        }
        normalized_login_customer = "".join(ch for ch in str(self.login_customer_id) if ch.isdigit())
        if normalized_login_customer:
            config["login_customer_id"] = normalized_login_customer
        return google_ads_client_cls.load_from_dict(config)

    def _search_stream(self, *, customer_id: str, query: str) -> Iterator[tuple[str, Any]]:
        service = self._client.get_service("GoogleAdsService")
        _, google_ads_exception_cls = _import_google_ads_symbols()
        normalized_customer = "".join(ch for ch in customer_id if ch.isdigit())
        if not normalized_customer:
            raise GoogleAdsSdkError(
                "customer_id must contain digits.",
                classification="invalid_customer_id",
                retryable=False,
            )
        try:
            stream = service.search_stream(customer_id=normalized_customer, query=query)
            for batch in stream:
                request_id = str(getattr(batch, "request_id", "") or "")
                rows = getattr(batch, "results", None) or []
                for row in rows:
                    yield request_id, row
        except Exception as exc:  # pragma: no cover - integration surface
            raise _classify_google_ads_exception(exc, google_ads_exception_cls) from exc

    def fetch_campaign_daily(
        self,
        *,
        customer_id: str,
        start_date: date,
        end_date: date,
    ) -> list[CampaignDailyRow]:
        query = render_gaql_template(
            "campaign_daily_performance",
            start_date=start_date,
            end_date=end_date,
        )
        rows: list[CampaignDailyRow] = []
        for request_id, row in self._search_stream(customer_id=customer_id, query=query):
            rows.append(
                CampaignDailyRow(
                    customer_id=str(row.customer.id),
                    campaign_id=str(row.campaign.id),
                    campaign_name=str(getattr(row.campaign, "name", "") or ""),
                    campaign_status=str(getattr(row.campaign, "status", "") or ""),
                    advertising_channel_type=str(
                        getattr(row.campaign, "advertising_channel_type", "") or ""
                    ),
                    date_day=_as_date(row.segments.date),
                    currency_code=str(getattr(row.customer, "currency_code", "") or ""),
                    impressions=_as_int(getattr(row.metrics, "impressions", 0)),
                    clicks=_as_int(getattr(row.metrics, "clicks", 0)),
                    conversions=_as_decimal(getattr(row.metrics, "conversions", 0)),
                    conversions_value=_as_decimal(getattr(row.metrics, "conversions_value", 0)),
                    cost_micros=_as_int(getattr(row.metrics, "cost_micros", 0)),
                    request_id=request_id,
                )
            )
        return rows

    def fetch_ad_group_ad_daily(
        self,
        *,
        customer_id: str,
        start_date: date,
        end_date: date,
    ) -> list[AdGroupAdDailyRow]:
        query = render_gaql_template(
            "ad_group_ad_daily_performance",
            start_date=start_date,
            end_date=end_date,
        )
        rows: list[AdGroupAdDailyRow] = []
        for request_id, row in self._search_stream(customer_id=customer_id, query=query):
            rows.append(
                AdGroupAdDailyRow(
                    customer_id=str(row.customer.id),
                    campaign_id=str(row.campaign.id),
                    ad_group_id=str(row.ad_group.id),
                    ad_id=str(row.ad_group_ad.ad.id),
                    campaign_name=str(getattr(row.campaign, "name", "") or ""),
                    ad_name=str(getattr(row.ad_group_ad.ad, "name", "") or ""),
                    ad_status=str(getattr(row.ad_group_ad, "status", "") or ""),
                    policy_approval_status=str(
                        getattr(getattr(row.ad_group_ad, "policy_summary", None), "approval_status", "") or ""
                    ),
                    policy_review_status=str(
                        getattr(getattr(row.ad_group_ad, "policy_summary", None), "review_status", "") or ""
                    ),
                    date_day=_as_date(row.segments.date),
                    currency_code=str(getattr(row.customer, "currency_code", "") or ""),
                    impressions=_as_int(getattr(row.metrics, "impressions", 0)),
                    clicks=_as_int(getattr(row.metrics, "clicks", 0)),
                    conversions=_as_decimal(getattr(row.metrics, "conversions", 0)),
                    conversions_value=_as_decimal(getattr(row.metrics, "conversions_value", 0)),
                    cost_micros=_as_int(getattr(row.metrics, "cost_micros", 0)),
                    request_id=request_id,
                )
            )
        return rows

    def fetch_geographic_daily(
        self,
        *,
        customer_id: str,
        start_date: date,
        end_date: date,
    ) -> list[GeographicDailyRow]:
        query = render_gaql_template(
            "geographic_daily_performance",
            start_date=start_date,
            end_date=end_date,
        )
        rows: list[GeographicDailyRow] = []
        for request_id, row in self._search_stream(customer_id=customer_id, query=query):
            rows.append(
                GeographicDailyRow(
                    customer_id=str(row.customer.id),
                    campaign_id=str(row.campaign.id),
                    date_day=_as_date(row.segments.date),
                    geo_target_country=str(getattr(row.segments, "geo_target_country", "") or ""),
                    geo_target_region=str(getattr(row.segments, "geo_target_region", "") or ""),
                    geo_target_city=str(getattr(row.segments, "geo_target_city", "") or ""),
                    currency_code=str(getattr(row.customer, "currency_code", "") or ""),
                    impressions=_as_int(getattr(row.metrics, "impressions", 0)),
                    clicks=_as_int(getattr(row.metrics, "clicks", 0)),
                    conversions=_as_decimal(getattr(row.metrics, "conversions", 0)),
                    conversions_value=_as_decimal(getattr(row.metrics, "conversions_value", 0)),
                    cost_micros=_as_int(getattr(row.metrics, "cost_micros", 0)),
                    request_id=request_id,
                )
            )
        return rows

    def fetch_keyword_daily(
        self,
        *,
        customer_id: str,
        start_date: date,
        end_date: date,
    ) -> list[KeywordDailyRow]:
        query = render_gaql_template(
            "keyword_daily_performance",
            start_date=start_date,
            end_date=end_date,
        )
        rows: list[KeywordDailyRow] = []
        for request_id, row in self._search_stream(customer_id=customer_id, query=query):
            quality_info = getattr(row.ad_group_criterion, "quality_info", None)
            quality_score_raw = getattr(quality_info, "quality_score", None)
            rows.append(
                KeywordDailyRow(
                    customer_id=str(row.customer.id),
                    campaign_id=str(row.campaign.id),
                    ad_group_id=str(row.ad_group.id),
                    criterion_id=str(row.ad_group_criterion.criterion_id),
                    keyword_text=str(getattr(getattr(row.ad_group_criterion, "keyword", None), "text", "") or ""),
                    match_type=str(
                        getattr(getattr(row.ad_group_criterion, "keyword", None), "match_type", "") or ""
                    ),
                    criterion_status=str(getattr(row.ad_group_criterion, "status", "") or ""),
                    quality_score=_as_int(quality_score_raw) if quality_score_raw is not None else None,
                    ad_relevance=str(
                        getattr(quality_info, "ad_relevance", "") or ""
                    ),
                    expected_ctr=str(
                        getattr(
                            quality_info,
                            "expected_clickthrough_rate",
                            "",
                        )
                        or ""
                    ),
                    landing_page_experience=str(
                        getattr(
                            quality_info,
                            "landing_page_experience",
                            "",
                        )
                        or ""
                    ),
                    date_day=_as_date(row.segments.date),
                    currency_code=str(getattr(row.customer, "currency_code", "") or ""),
                    impressions=_as_int(getattr(row.metrics, "impressions", 0)),
                    clicks=_as_int(getattr(row.metrics, "clicks", 0)),
                    conversions=_as_decimal(getattr(row.metrics, "conversions", 0)),
                    conversions_value=_as_decimal(getattr(row.metrics, "conversions_value", 0)),
                    cost_micros=_as_int(getattr(row.metrics, "cost_micros", 0)),
                    request_id=request_id,
                )
            )
        return rows

    def fetch_search_term_daily(
        self,
        *,
        customer_id: str,
        start_date: date,
        end_date: date,
    ) -> list[SearchTermDailyRow]:
        query = render_gaql_template(
            "search_term_daily_performance",
            start_date=start_date,
            end_date=end_date,
        )
        rows: list[SearchTermDailyRow] = []
        for request_id, row in self._search_stream(customer_id=customer_id, query=query):
            rows.append(
                SearchTermDailyRow(
                    customer_id=str(row.customer.id),
                    campaign_id=str(row.campaign.id),
                    ad_group_id=str(row.ad_group.id),
                    criterion_id=str(getattr(row.ad_group_criterion, "criterion_id", "") or ""),
                    search_term=str(getattr(row.search_term_view, "search_term", "") or ""),
                    date_day=_as_date(row.segments.date),
                    currency_code=str(getattr(row.customer, "currency_code", "") or ""),
                    impressions=_as_int(getattr(row.metrics, "impressions", 0)),
                    clicks=_as_int(getattr(row.metrics, "clicks", 0)),
                    conversions=_as_decimal(getattr(row.metrics, "conversions", 0)),
                    conversions_value=_as_decimal(getattr(row.metrics, "conversions_value", 0)),
                    cost_micros=_as_int(getattr(row.metrics, "cost_micros", 0)),
                    request_id=request_id,
                )
            )
        return rows

    def fetch_asset_group_daily(
        self,
        *,
        customer_id: str,
        start_date: date,
        end_date: date,
    ) -> list[AssetGroupDailyRow]:
        query = render_gaql_template(
            "asset_group_daily_performance",
            start_date=start_date,
            end_date=end_date,
        )
        rows: list[AssetGroupDailyRow] = []
        for request_id, row in self._search_stream(customer_id=customer_id, query=query):
            rows.append(
                AssetGroupDailyRow(
                    customer_id=str(row.customer.id),
                    campaign_id=str(row.campaign.id),
                    asset_group_id=str(row.asset_group.id),
                    asset_group_name=str(getattr(row.asset_group, "name", "") or ""),
                    asset_group_status=str(getattr(row.asset_group, "status", "") or ""),
                    date_day=_as_date(row.segments.date),
                    currency_code=str(getattr(row.customer, "currency_code", "") or ""),
                    impressions=_as_int(getattr(row.metrics, "impressions", 0)),
                    clicks=_as_int(getattr(row.metrics, "clicks", 0)),
                    conversions=_as_decimal(getattr(row.metrics, "conversions", 0)),
                    conversions_value=_as_decimal(getattr(row.metrics, "conversions_value", 0)),
                    cost_micros=_as_int(getattr(row.metrics, "cost_micros", 0)),
                    request_id=request_id,
                )
            )
        return rows

    def fetch_conversion_action_daily(
        self,
        *,
        customer_id: str,
        start_date: date,
        end_date: date,
    ) -> list[ConversionActionDailyRow]:
        query = render_gaql_template(
            "conversion_action_daily_performance",
            start_date=start_date,
            end_date=end_date,
        )
        rows: list[ConversionActionDailyRow] = []
        for request_id, row in self._search_stream(customer_id=customer_id, query=query):
            rows.append(
                ConversionActionDailyRow(
                    customer_id=str(row.customer.id),
                    conversion_action_id=str(row.conversion_action.id),
                    conversion_action_name=str(getattr(row.conversion_action, "name", "") or ""),
                    conversion_action_type=str(getattr(row.conversion_action, "type", "") or ""),
                    date_day=_as_date(row.segments.date),
                    conversions=_as_decimal(getattr(row.metrics, "conversions", 0)),
                    all_conversions=_as_decimal(getattr(row.metrics, "all_conversions", 0)),
                    conversions_value=_as_decimal(getattr(row.metrics, "conversions_value", 0)),
                    request_id=request_id,
                )
            )
        return rows

    def fetch_change_events(
        self,
        *,
        customer_id: str,
        start_datetime: datetime,
        end_datetime: datetime,
    ) -> list[ChangeEventRow]:
        query = render_gaql_template(
            "change_event_incremental",
            start_datetime=start_datetime,
            end_datetime=end_datetime,
        )
        rows: list[ChangeEventRow] = []
        for request_id, row in self._search_stream(customer_id=customer_id, query=query):
            changed_fields_raw = getattr(row.change_event, "changed_fields", None)
            changed_fields: list[str] = []
            if changed_fields_raw:
                try:
                    changed_fields = list(changed_fields_raw.paths)
                except Exception:
                    changed_fields = []
            change_date_time = _as_datetime(getattr(row.change_event, "change_date_time", ""))
            resource_type = str(getattr(row.change_event, "change_resource_type", "") or "")
            operation = str(getattr(row.change_event, "resource_change_operation", "") or "")
            campaign_id = str(getattr(getattr(row.change_event, "campaign", None), "id", "") or "")
            ad_group_id = str(getattr(getattr(row.change_event, "ad_group", None), "id", "") or "")
            ad_id = str(getattr(getattr(row.change_event, "ad", None), "id", "") or "")
            fingerprint_source = "|".join(
                [
                    str(customer_id),
                    change_date_time.isoformat(),
                    resource_type,
                    operation,
                    campaign_id,
                    ad_group_id,
                    ad_id,
                    ",".join(changed_fields),
                ]
            )
            rows.append(
                ChangeEventRow(
                    customer_id=str(row.change_event.customer),
                    event_fingerprint=hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest(),
                    change_date_time=change_date_time,
                    user_email=str(getattr(row.change_event, "user_email", "") or ""),
                    client_type=str(getattr(row.change_event, "client_type", "") or ""),
                    change_resource_type=resource_type,
                    resource_change_operation=operation,
                    campaign_id=campaign_id,
                    ad_group_id=ad_group_id,
                    ad_id=ad_id,
                    changed_fields=changed_fields,
                    request_id=request_id,
                )
            )
        return rows

    def fetch_recommendations(
        self,
        *,
        customer_id: str,
    ) -> list[RecommendationRow]:
        query = render_gaql_template("recommendations_inventory")
        rows: list[RecommendationRow] = []
        for request_id, row in self._search_stream(customer_id=customer_id, query=query):
            rec = row.recommendation
            impact_metadata = {
                "impact": str(getattr(rec, "impact", "") or ""),
                "primary_status": str(getattr(rec, "primary_status", "") or ""),
            }
            rows.append(
                RecommendationRow(
                    customer_id=str(row.customer.id),
                    recommendation_type=str(getattr(rec, "type", "") or ""),
                    resource_name=str(getattr(rec, "resource_name", "") or ""),
                    campaign_id=str(getattr(rec, "campaign", "") or ""),
                    ad_group_id=str(getattr(rec, "ad_group", "") or ""),
                    dismissed=_as_bool(getattr(rec, "dismissed", False)),
                    impact_metadata=impact_metadata,
                    request_id=request_id,
                )
            )
        return rows

    def fetch_accessible_customers(self, *, customer_id: str) -> list[AccessibleCustomerRow]:
        query = render_gaql_template("accessible_customers")
        rows: list[AccessibleCustomerRow] = []
        for _request_id, row in self._search_stream(customer_id=customer_id, query=query):
            rows.append(
                AccessibleCustomerRow(
                    manager_customer_id=str(customer_id),
                    customer_id=str(getattr(row.customer_client, "id", "") or ""),
                    customer_name=str(getattr(row.customer_client, "descriptive_name", "") or ""),
                    currency_code=str(getattr(row.customer_client, "currency_code", "") or ""),
                    time_zone=str(getattr(row.customer_client, "time_zone", "") or ""),
                    status=str(getattr(row.customer_client, "status", "") or ""),
                    is_manager=_as_bool(getattr(row.customer_client, "manager", False)),
                )
            )
        return rows
