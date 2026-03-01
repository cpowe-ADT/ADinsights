from __future__ import annotations

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
_RETRYABLE_GRAPH_CODES = {80001}


class MetaInsightsGraphClientError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: int | None = None,
        error_subcode: int | None = None,
        retryable: bool = False,
        payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.error_subcode = error_subcode
        self.retryable = retryable
        self.payload = payload or {}


class MetaInsightsGraphClient:
    def __init__(
        self,
        *,
        graph_version: str,
        timeout_seconds: float = 20.0,
        max_attempts: int = 5,
    ) -> None:
        self.base_url = f"https://graph.facebook.com/{graph_version}"
        self.max_attempts = max(max_attempts, 1)
        self._client = httpx.Client(timeout=timeout_seconds)

    @classmethod
    def from_settings(cls) -> "MetaInsightsGraphClient":
        graph_version = (getattr(settings, "META_GRAPH_API_VERSION", "v24.0") or "v24.0").strip()
        return cls(
            graph_version=graph_version,
            timeout_seconds=float(getattr(settings, "META_PAGE_INSIGHTS_TIMEOUT_SECONDS", 20.0)),
            max_attempts=int(getattr(settings, "META_PAGE_INSIGHTS_MAX_ATTEMPTS", 5)),
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MetaInsightsGraphClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: D401
        self.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None,
        token: str,
    ) -> dict[str, Any]:
        url = self._absolute_url(path)
        request_params = dict(params or {})
        request_params["access_token"] = token

        last_message = "Meta Graph request failed"
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self._client.request(method, url, params=request_params)
            except httpx.HTTPError as exc:
                retryable = attempt < self.max_attempts
                observe_meta_graph_retry(reason="transport_error")
                if retryable:
                    self._sleep_backoff(attempt)
                    continue
                raise MetaInsightsGraphClientError(
                    f"Meta Graph transport error: {exc}",
                    retryable=True,
                ) from exc

            self._emit_throttle_from_headers(response.headers)
            payload = self._safe_json(response)
            details = self._extract_error_details(payload)
            retryable = self._should_retry(response.status_code, details["error_code"])
            if response.is_success:
                if isinstance(payload, dict):
                    return payload
                return {}

            last_message = details["message"] or f"Meta Graph request failed with status {response.status_code}."
            if retryable and attempt < self.max_attempts:
                observe_meta_graph_retry(reason="meta_retryable")
                self._sleep_backoff(attempt)
                continue

            raise MetaInsightsGraphClientError(
                last_message,
                status_code=response.status_code,
                error_code=details["error_code"],
                error_subcode=details["error_subcode"],
                retryable=retryable,
                payload=payload if isinstance(payload, dict) else None,
            )

        raise MetaInsightsGraphClientError(last_message, retryable=True)

    def fetch_page_insights(
        self,
        *,
        page_id: str,
        metrics: list[str],
        period: str,
        since: str,
        until: str,
        token: str,
    ) -> dict[str, Any]:
        if not metrics:
            raise MetaInsightsGraphClientError(
                "No metrics were provided for Page Insights request.",
                error_code=3001,
                error_subcode=1504028,
                retryable=False,
            )
        return self.request(
            "GET",
            f"/{page_id}/insights",
            params={
                "metric": ",".join(metrics),
                "period": period,
                "since": since,
                "until": until,
            },
            token=token,
        )

    def fetch_post_insights(
        self,
        *,
        post_id: str,
        metrics: list[str],
        period: str,
        since: str | None,
        until: str | None,
        token: str,
    ) -> dict[str, Any]:
        if not metrics:
            raise MetaInsightsGraphClientError(
                "No metrics were provided for Post Insights request.",
                error_code=3001,
                error_subcode=1504028,
                retryable=False,
            )
        params: dict[str, Any] = {
            "metric": ",".join(metrics),
            "period": period,
        }
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        return self.request(
            "GET",
            f"/{post_id}/insights",
            params=params,
            token=token,
        )

    def fetch_page_posts(
        self,
        *,
        page_id: str,
        since: str,
        until: str,
        token: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        next_path: str | None = f"/{page_id}/posts"
        next_params: dict[str, Any] | None = {
            "fields": "id,message,permalink_url,created_time,updated_time,attachments{media_type,type}",
            "since": since,
            "until": until,
            "limit": limit,
        }
        pages = 0
        while next_path and pages < 50:
            payload = self.request("GET", next_path, params=next_params, token=token)
            pages += 1
            data = payload.get("data")
            if isinstance(data, list):
                for row in data:
                    if isinstance(row, dict):
                        results.append(row)
            next_params = None
            next_path = None
            paging = payload.get("paging")
            if isinstance(paging, dict):
                candidate = paging.get("next")
                if isinstance(candidate, str) and candidate.strip():
                    next_path = candidate.strip()
        return results

    def _emit_throttle_from_headers(self, headers: httpx.Headers) -> None:
        for header_name in (
            "x-app-usage",
            "x-ad-account-usage",
            "x-business-use-case-usage",
        ):
            raw_value = headers.get(header_name)
            if not raw_value:
                continue
            usage_pct = self._extract_usage_percent(raw_value)
            if usage_pct is not None and usage_pct >= 85:
                observe_meta_graph_throttle_event(header_name=header_name)

    def _extract_usage_percent(self, raw_value: str) -> int | None:
        try:
            payload = json.loads(raw_value)
        except ValueError:
            return None

        values: list[int] = []

        def collect(value: Any, key_hint: str | None = None) -> None:
            if isinstance(value, dict):
                for child_key, child_value in value.items():
                    collect(child_value, child_key)
                return
            if isinstance(value, list):
                for child in value:
                    collect(child, key_hint)
                return
            if isinstance(value, (int, float)) and key_hint in {
                "call_count",
                "total_cputime",
                "total_time",
            }:
                values.append(int(value))

        collect(payload)
        if not values:
            return None
        return max(values)

    @staticmethod
    def _safe_json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return None

    @staticmethod
    def _extract_error_details(payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            err = payload.get("error")
            if isinstance(err, dict):
                return {
                    "message": str(err.get("message") or ""),
                    "error_code": _maybe_int(err.get("code")),
                    "error_subcode": _maybe_int(err.get("error_subcode")),
                }
        return {
            "message": "",
            "error_code": None,
            "error_subcode": None,
        }

    @staticmethod
    def _should_retry(status_code: int, error_code: int | None) -> bool:
        return status_code in _RETRYABLE_HTTP_STATUS or error_code in _RETRYABLE_GRAPH_CODES

    @staticmethod
    def _sleep_backoff(attempt: int) -> None:
        # Exponential backoff (base 2) with jitter.
        delay = float(2 ** (attempt - 1))
        jitter = random.uniform(0, 1)
        time.sleep(delay + jitter)

    def _absolute_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if path.startswith("/"):
            return f"{self.base_url}{path}"
        return f"{self.base_url}/{path}"


def _maybe_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
