from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import random
import time
from typing import Any

import httpx
from django.conf import settings

from core.metrics import observe_meta_graph_retry, observe_meta_graph_throttle_event

logger = logging.getLogger(__name__)

_RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}
_RETRYABLE_META_ERROR_CODES = {1, 2, 4, 17, 32, 613, 80001}
_DEFAULT_PAGE_CAP = 50
_DEFAULT_ROW_CAP = 10000


class MetaGraphConfigurationError(RuntimeError):
    """Raised when Meta OAuth settings are incomplete."""


class MetaGraphClientError(RuntimeError):
    """Raised when Meta Graph API requests fail."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: int | None = None,
        error_subcode: int | None = None,
        retryable: bool = False,
        payload: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.error_subcode = error_subcode
        self.retryable = retryable
        self.payload = payload


@dataclass(slots=True)
class MetaToken:
    access_token: str
    expires_in: int | None = None


@dataclass(slots=True)
class MetaPage:
    id: str
    name: str
    access_token: str
    category: str | None = None
    tasks: list[str] | None = None
    perms: list[str] | None = None
    instagram_business_account: "MetaInstagramAccount | None" = None
    connected_instagram_account: "MetaInstagramAccount | None" = None

    def as_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "tasks": self.tasks or [],
            "perms": self.perms or [],
        }


@dataclass(slots=True)
class MetaInstagramAccount:
    id: str
    username: str | None = None
    name: str | None = None
    profile_picture_url: str | None = None
    followers_count: int | None = None
    media_count: int | None = None
    source_page_id: str | None = None
    source_page_name: str | None = None
    source_field: str | None = None

    def as_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "name": self.name,
            "profile_picture_url": self.profile_picture_url,
            "followers_count": self.followers_count,
            "media_count": self.media_count,
            "source_page_id": self.source_page_id,
            "source_page_name": self.source_page_name,
            "source_field": self.source_field,
        }


@dataclass(slots=True)
class MetaAdAccount:
    id: str
    account_id: str
    name: str | None = None
    currency: str | None = None
    account_status: int | None = None
    business_name: str | None = None

    def as_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "account_id": self.account_id,
            "name": self.name,
            "currency": self.currency,
            "account_status": self.account_status,
            "business_name": self.business_name,
        }


class MetaGraphClient:
    """HTTP client for Meta Graph API OAuth + page/account discovery."""

    def __init__(
        self,
        *,
        app_id: str,
        app_secret: str,
        graph_version: str,
        timeout_seconds: float = 10.0,
        max_attempts: int = 5,
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = f"https://graph.facebook.com/{graph_version}"
        self.max_attempts = max(max_attempts, 1)
        self._client = httpx.Client(timeout=timeout_seconds)

    @classmethod
    def from_settings(cls) -> "MetaGraphClient":
        app_id = (getattr(settings, "META_APP_ID", "") or "").strip()
        app_secret = (getattr(settings, "META_APP_SECRET", "") or "").strip()
        if not app_id or not app_secret:
            raise MetaGraphConfigurationError(
                "META_APP_ID and META_APP_SECRET must be configured for Meta OAuth."
            )
        graph_version = (getattr(settings, "META_GRAPH_API_VERSION", "v24.0") or "v24.0").strip()
        return cls(app_id=app_id, app_secret=app_secret, graph_version=graph_version)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MetaGraphClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: D401 - context manager contract
        self.close()

    def exchange_code(self, *, code: str, redirect_uri: str) -> MetaToken:
        payload = self._request_json(
            "GET",
            "/oauth/access_token",
            params={
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
            request_name="oauth_exchange_code",
        )
        return self._parse_access_token_payload(payload)

    def exchange_for_long_lived_user_token(self, *, short_lived_user_token: str) -> MetaToken:
        payload = self._request_json(
            "GET",
            "/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "fb_exchange_token": short_lived_user_token,
            },
            request_name="oauth_exchange_long_lived",
        )
        return self._parse_access_token_payload(payload)

    def list_pages(self, *, user_access_token: str) -> list[MetaPage]:
        rows = self._paginated_data(
            "/me/accounts",
            params={
                "fields": (
                    "id,name,access_token,category,tasks,perms,"
                    "instagram_business_account{id,username,name,profile_picture_url,followers_count,media_count},"
                    "connected_instagram_account{id,username,name,profile_picture_url,followers_count,media_count}"
                ),
                "limit": 200,
                "access_token": user_access_token,
            },
            request_name="list_pages",
        )
        pages: list[MetaPage] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            page_id = row.get("id")
            page_name = row.get("name")
            page_access_token = row.get("access_token")
            if not isinstance(page_id, str) or not isinstance(page_name, str):
                continue
            if not isinstance(page_access_token, str) or not page_access_token.strip():
                continue
            tasks = row.get("tasks")
            perms = row.get("perms")
            pages.append(
                MetaPage(
                    id=page_id,
                    name=page_name,
                    access_token=page_access_token,
                    category=row.get("category") if isinstance(row.get("category"), str) else None,
                    tasks=[task for task in tasks if isinstance(task, str)] if isinstance(tasks, list) else [],
                    perms=[perm for perm in perms if isinstance(perm, str)] if isinstance(perms, list) else [],
                    instagram_business_account=self._parse_instagram_account(
                        row.get("instagram_business_account"),
                        source_page_id=page_id,
                        source_page_name=page_name,
                        source_field="instagram_business_account",
                    ),
                    connected_instagram_account=self._parse_instagram_account(
                        row.get("connected_instagram_account"),
                        source_page_id=page_id,
                        source_page_name=page_name,
                        source_field="connected_instagram_account",
                    ),
                )
            )
        return pages

    def list_instagram_accounts(self, *, pages: list[MetaPage]) -> list[MetaInstagramAccount]:
        accounts_by_id: dict[str, MetaInstagramAccount] = {}

        for page in pages:
            for account in (page.instagram_business_account, page.connected_instagram_account):
                self._merge_instagram_account(accounts_by_id, account)

            if page.instagram_business_account or page.connected_instagram_account:
                continue

            try:
                page_accounts = self._fetch_page_instagram_accounts(page=page)
            except MetaGraphClientError:
                continue
            for account in page_accounts:
                self._merge_instagram_account(accounts_by_id, account)

        return list(accounts_by_id.values())

    def list_ad_accounts(self, *, user_access_token: str) -> list[MetaAdAccount]:
        rows = self._paginated_data(
            "/me/adaccounts",
            params={
                "fields": "id,account_id,name,currency,account_status,business_name",
                "limit": 200,
                "access_token": user_access_token,
            },
            request_name="list_ad_accounts",
        )
        ad_accounts: list[MetaAdAccount] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            account_id_value = row.get("account_id")
            if not isinstance(account_id_value, str) or not account_id_value.strip():
                continue
            id_value = row.get("id")
            account_id_candidate = account_id_value.strip()
            account_node_id = id_value if isinstance(id_value, str) and id_value.strip() else f"act_{account_id_candidate}"
            account_status_raw = row.get("account_status")
            account_status = account_status_raw if isinstance(account_status_raw, int) else None
            ad_accounts.append(
                MetaAdAccount(
                    id=account_node_id,
                    account_id=account_id_candidate,
                    name=row.get("name") if isinstance(row.get("name"), str) else None,
                    currency=row.get("currency") if isinstance(row.get("currency"), str) else None,
                    account_status=account_status,
                    business_name=(
                        row.get("business_name") if isinstance(row.get("business_name"), str) else None
                    ),
                )
            )
        return ad_accounts

    def debug_token(self, *, input_token: str) -> dict[str, Any]:
        payload = self._request_json(
            "GET",
            "/debug_token",
            params={
                "input_token": input_token,
                "access_token": f"{self.app_id}|{self.app_secret}",
            },
            request_name="debug_token",
        )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise MetaGraphClientError("Meta debug_token response is missing token data.")
        return data

    def list_permissions(self, *, user_access_token: str) -> list[dict[str, str]]:
        rows = self._paginated_data(
            "/me/permissions",
            params={
                "access_token": user_access_token,
                "limit": 200,
            },
            request_name="list_permissions",
        )
        permissions: list[dict[str, str]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            permission = row.get("permission")
            status = row.get("status")
            if not isinstance(permission, str) or not permission.strip():
                continue
            if not isinstance(status, str) or not status.strip():
                continue
            permissions.append({"permission": permission.strip(), "status": status.strip().lower()})
        return permissions

    def list_campaigns(
        self,
        *,
        account_id: str,
        user_access_token: str,
    ) -> list[dict[str, Any]]:
        return self._paginated_data(
            f"/{self._account_node_id(account_id)}/campaigns",
            params={
                "fields": "id,account_id,name,status,effective_status,objective,created_time,updated_time",
                "limit": 200,
                "access_token": user_access_token,
            },
            request_name="list_campaigns",
        )

    def list_adsets(
        self,
        *,
        account_id: str,
        user_access_token: str,
    ) -> list[dict[str, Any]]:
        return self._paginated_data(
            f"/{self._account_node_id(account_id)}/adsets",
            params={
                "fields": (
                    "id,account_id,campaign_id,name,status,effective_status,bid_strategy,"
                    "daily_budget,start_time,end_time,targeting,created_time,updated_time"
                ),
                "limit": 200,
                "access_token": user_access_token,
            },
            request_name="list_adsets",
        )

    def list_ads(
        self,
        *,
        account_id: str,
        user_access_token: str,
    ) -> list[dict[str, Any]]:
        return self._paginated_data(
            f"/{self._account_node_id(account_id)}/ads",
            params={
                "fields": (
                    "id,account_id,campaign_id,adset_id,name,status,effective_status,"
                    "creative{id,name,thumbnail_url},created_time,updated_time"
                ),
                "limit": 200,
                "access_token": user_access_token,
            },
            request_name="list_ads",
        )

    def list_insights(
        self,
        *,
        account_id: str,
        user_access_token: str,
        level: str,
        since: str,
        until: str,
    ) -> list[dict[str, Any]]:
        return self._paginated_data(
            f"/{self._account_node_id(account_id)}/insights",
            params={
                "level": level,
                "time_increment": 1,
                "time_range": json.dumps({"since": since, "until": until}),
                "fields": (
                    "date_start,date_stop,account_id,campaign_id,adset_id,ad_id,"
                    "impressions,reach,spend,clicks,cpc,cpm,actions"
                ),
                "limit": 200,
                "access_token": user_access_token,
            },
            request_name="list_insights",
        )

    def _request_json(
        self,
        method: str,
        path_or_url: str,
        *,
        params: dict[str, Any] | None = None,
        request_name: str,
    ) -> dict[str, Any]:
        url = self._absolute_url(path_or_url)
        last_error: str | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self._client.request(method, url, params=params)
            except httpx.HTTPError as exc:
                last_error = f"Meta Graph API request failed: {exc}"
                if attempt >= self.max_attempts:
                    raise MetaGraphClientError(
                        last_error,
                        retryable=True,
                    ) from exc
                self._observe_retry(
                    request_name=request_name,
                    attempt=attempt,
                    reason="transport_error",
                    status_code=None,
                )
                self._sleep_with_backoff(attempt)
                continue

            self._emit_throttle_from_headers(response.headers, request_name=request_name)

            payload = self._safe_json(response)
            if response.is_success:
                if isinstance(payload, dict):
                    return payload
                raise MetaGraphClientError("Meta Graph API returned an unexpected response payload.")

            details = self._extract_error_details(payload)
            message = details["message"]
            last_error = message or f"Meta Graph API returned HTTP {response.status_code}."
            retryable = self._should_retry_response(
                status_code=response.status_code,
                payload=payload,
            )
            if attempt < self.max_attempts and self._should_retry_response(
                status_code=response.status_code,
                payload=payload,
            ):
                self._observe_retry(
                    request_name=request_name,
                    attempt=attempt,
                    reason="http_retryable",
                    status_code=response.status_code,
                )
                self._sleep_with_backoff(attempt)
                continue

            raise MetaGraphClientError(
                last_error,
                status_code=response.status_code,
                error_code=details["error_code"],
                error_subcode=details["error_subcode"],
                retryable=retryable,
                payload=payload if isinstance(payload, dict) else None,
            )

        raise MetaGraphClientError(
            last_error or "Meta Graph API request failed after retries.",
            retryable=True,
        )

    def _paginated_data(
        self,
        path_or_url: str,
        *,
        params: dict[str, Any] | None,
        request_name: str,
        page_cap: int = _DEFAULT_PAGE_CAP,
        row_cap: int = _DEFAULT_ROW_CAP,
    ) -> list[Any]:
        rows: list[Any] = []
        next_url: str | None = path_or_url
        next_params: dict[str, Any] | None = params
        pages_read = 0

        while next_url and pages_read < page_cap and len(rows) < row_cap:
            payload = self._request_json(
                "GET",
                next_url,
                params=next_params,
                request_name=request_name,
            )
            pages_read += 1
            next_params = None

            data = payload.get("data")
            if isinstance(data, list):
                remaining = max(row_cap - len(rows), 0)
                if remaining:
                    rows.extend(data[:remaining])

            next_url = None
            paging = payload.get("paging")
            if isinstance(paging, dict):
                candidate = paging.get("next")
                if isinstance(candidate, str) and candidate.strip():
                    next_url = candidate.strip()

        if next_url and (pages_read >= page_cap or len(rows) >= row_cap):
            logger.warning(
                "meta.graph.pagination_cap_reached",
                extra={
                    "request_name": request_name,
                    "pages_read": pages_read,
                    "rows_read": len(rows),
                    "page_cap": page_cap,
                    "row_cap": row_cap,
                },
            )

        return rows

    def _absolute_url(self, path_or_url: str) -> str:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        if path_or_url.startswith("/"):
            return f"{self.base_url}{path_or_url}"
        return f"{self.base_url}/{path_or_url}"

    @staticmethod
    def _account_node_id(account_id: str) -> str:
        cleaned = account_id.strip()
        if cleaned.startswith("act_"):
            return cleaned
        if cleaned.isdigit():
            return f"act_{cleaned}"
        return cleaned

    @staticmethod
    def _safe_json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return None

    def _emit_throttle_from_headers(self, headers: httpx.Headers, *, request_name: str) -> None:
        for header_name in (
            "x-app-usage",
            "x-ad-account-usage",
            "x-business-use-case-usage",
        ):
            raw_value = headers.get(header_name)
            if not raw_value:
                continue
            parsed = self._try_parse_usage_header(raw_value)
            usage_pct = self._max_usage_percentage(parsed)
            if usage_pct is None or usage_pct < 85:
                continue
            observe_meta_graph_throttle_event(header_name=header_name)
            logger.warning(
                "meta.graph.throttle_near_limit",
                extra={
                    "request_name": request_name,
                    "header_name": header_name,
                    "usage_pct": usage_pct,
                },
            )

    @staticmethod
    def _try_parse_usage_header(raw_value: str) -> Any:
        try:
            return json.loads(raw_value)
        except ValueError:
            return raw_value

    def _max_usage_percentage(self, payload: Any) -> int | None:
        values: list[int] = []

        def _collect(value: Any, key_hint: str | None = None) -> None:
            if isinstance(value, dict):
                for child_key, child_value in value.items():
                    _collect(child_value, child_key)
                return
            if isinstance(value, list):
                for child in value:
                    _collect(child, key_hint)
                return
            if isinstance(value, (int, float)) and key_hint in {
                "call_count",
                "total_cputime",
                "total_time",
            }:
                values.append(int(value))

        _collect(payload)
        if not values:
            return None
        return max(values)

    def _observe_retry(
        self,
        *,
        request_name: str,
        attempt: int,
        reason: str,
        status_code: int | None,
    ) -> None:
        observe_meta_graph_retry(reason=reason)
        logger.info(
            "meta.graph.retry",
            extra={
                "request_name": request_name,
                "attempt": attempt,
                "reason": reason,
                "status_code": status_code,
            },
        )

    @staticmethod
    def _sleep_with_backoff(attempt: int) -> None:
        base = 2 ** max(attempt - 1, 0)
        jitter = random.uniform(0.0, 1.0)
        time.sleep(base + jitter)

    def _should_retry_response(self, *, status_code: int, payload: Any) -> bool:
        if status_code in _RETRYABLE_HTTP_STATUS:
            return True
        if status_code < 400:
            return False

        if not isinstance(payload, dict):
            return False
        error_payload = payload.get("error")
        if not isinstance(error_payload, dict):
            return False
        if bool(error_payload.get("is_transient")):
            return True

        raw_code = error_payload.get("code")
        try:
            code = int(raw_code)
        except (TypeError, ValueError):
            code = None
        return code in _RETRYABLE_META_ERROR_CODES if code is not None else False

    @staticmethod
    def _extract_error_details(payload: Any) -> dict[str, Any]:
        details: dict[str, Any] = {
            "message": None,
            "error_code": None,
            "error_subcode": None,
        }
        if not isinstance(payload, dict):
            return details
        error_payload = payload.get("error")
        if isinstance(error_payload, dict):
            message = error_payload.get("message")
            if isinstance(message, str) and message.strip():
                details["message"] = message
            raw_code = error_payload.get("code")
            raw_subcode = error_payload.get("error_subcode")
            try:
                details["error_code"] = int(raw_code) if raw_code is not None else None
            except (TypeError, ValueError):
                details["error_code"] = None
            try:
                details["error_subcode"] = int(raw_subcode) if raw_subcode is not None else None
            except (TypeError, ValueError):
                details["error_subcode"] = None
            return details
        detail = payload.get("error_description")
        if isinstance(detail, str) and detail.strip():
            details["message"] = detail
        return details

    @staticmethod
    def _parse_access_token_payload(payload: dict[str, Any]) -> MetaToken:
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token.strip():
            raise MetaGraphClientError("Meta OAuth token exchange succeeded without an access token.")
        expires_in_raw = payload.get("expires_in")
        expires_in: int | None
        try:
            expires_in = int(expires_in_raw) if expires_in_raw is not None else None
        except (TypeError, ValueError):
            expires_in = None
        return MetaToken(access_token=access_token, expires_in=expires_in)

    @staticmethod
    def _coerce_int(raw_value: Any) -> int | None:
        try:
            return int(raw_value) if raw_value is not None else None
        except (TypeError, ValueError):
            return None

    def _parse_instagram_account(
        self,
        raw_value: Any,
        *,
        source_page_id: str,
        source_page_name: str,
        source_field: str,
    ) -> MetaInstagramAccount | None:
        if not isinstance(raw_value, dict):
            return None
        account_id = raw_value.get("id")
        if not isinstance(account_id, str) or not account_id.strip():
            return None
        return MetaInstagramAccount(
            id=account_id,
            username=raw_value.get("username") if isinstance(raw_value.get("username"), str) else None,
            name=raw_value.get("name") if isinstance(raw_value.get("name"), str) else None,
            profile_picture_url=(
                raw_value.get("profile_picture_url")
                if isinstance(raw_value.get("profile_picture_url"), str)
                else None
            ),
            followers_count=self._coerce_int(raw_value.get("followers_count")),
            media_count=self._coerce_int(raw_value.get("media_count")),
            source_page_id=source_page_id,
            source_page_name=source_page_name,
            source_field=source_field,
        )

    def _fetch_page_instagram_accounts(self, *, page: MetaPage) -> list[MetaInstagramAccount]:
        payload = self._request_json(
            "GET",
            f"/{page.id}",
            params={
                "fields": (
                    "instagram_business_account{id,username,name,profile_picture_url,followers_count,media_count},"
                    "connected_instagram_account{id,username,name,profile_picture_url,followers_count,media_count}"
                ),
                "access_token": page.access_token,
            },
            request_name="fetch_page_instagram_accounts",
        )
        accounts: list[MetaInstagramAccount] = []
        for source_field in ("instagram_business_account", "connected_instagram_account"):
            account = self._parse_instagram_account(
                payload.get(source_field),
                source_page_id=page.id,
                source_page_name=page.name,
                source_field=source_field,
            )
            if account is not None:
                accounts.append(account)
        return accounts

    @staticmethod
    def _merge_instagram_account(
        accounts_by_id: dict[str, MetaInstagramAccount],
        account: MetaInstagramAccount | None,
    ) -> None:
        if account is None:
            return
        existing = accounts_by_id.get(account.id)
        if existing is None:
            accounts_by_id[account.id] = account
            return
        for field in (
            "username",
            "name",
            "profile_picture_url",
            "followers_count",
            "media_count",
            "source_page_id",
            "source_page_name",
            "source_field",
        ):
            if getattr(existing, field) in (None, "") and getattr(account, field) not in (None, ""):
                setattr(existing, field, getattr(account, field))
