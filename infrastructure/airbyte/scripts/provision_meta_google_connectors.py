#!/usr/bin/env python3
"""Provision Meta + Google Airbyte sources and template connections.

This script is idempotent:
- upserts source definitions by name in a workspace
- checks source connectivity
- discovers catalogs
- upserts template connections to a destination

It prints a JSON summary including the connection IDs that should be copied to:
- AIRBYTE_TEMPLATE_META_METRICS_CONNECTION_ID
- AIRBYTE_TEMPLATE_GOOGLE_METRICS_CONNECTION_ID
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import pathlib
import sys
from typing import Any, Dict, Iterable, Optional
from urllib import error, request


META_SOURCE_DEFINITION_ID = "778daa7c-feaf-4db6-96f3-70fd645acc77"
GOOGLE_SOURCE_DEFINITION_ID = "0b29e8f7-f64c-4a24-9e97-07c4603f8c04"

DEFAULT_META_SOURCE_NAME = "Template Meta Source"
DEFAULT_GOOGLE_SOURCE_NAME = "Template Google Ads Source"
DEFAULT_META_CONNECTION_NAME = "Template Meta Metrics"
DEFAULT_GOOGLE_CONNECTION_NAME = "Template Google Metrics"

DEFAULT_METRICS_CRON = "0 6-22 * * *"
DEFAULT_METRICS_TIMEZONE = "America/Jamaica"


class AirbyteProvisioningError(RuntimeError):
    """Provisioning failure that should stop execution."""


@dataclass(frozen=True)
class ConnectorSpec:
    key: str
    source_name_env: str
    connection_name_env: str
    source_definition_id: str


SPECS = (
    ConnectorSpec(
        key="meta",
        source_name_env="AIRBYTE_TEMPLATE_META_SOURCE_NAME",
        connection_name_env="AIRBYTE_TEMPLATE_META_METRICS_NAME",
        source_definition_id=META_SOURCE_DEFINITION_ID,
    ),
    ConnectorSpec(
        key="google",
        source_name_env="AIRBYTE_TEMPLATE_GOOGLE_SOURCE_NAME",
        connection_name_env="AIRBYTE_TEMPLATE_GOOGLE_METRICS_NAME",
        source_definition_id=GOOGLE_SOURCE_DEFINITION_ID,
    ),
)


class AirbyteClient:
    def __init__(self, base_url: str, auth_header: Optional[str]) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_header = auth_header

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if self.auth_header:
            headers["Authorization"] = self.auth_header
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore")
            raise AirbyteProvisioningError(
                f"Airbyte API {path} failed with HTTP {exc.code}: {details}"
            ) from exc
        except error.URLError as exc:
            raise AirbyteProvisioningError(
                f"Unable to reach Airbyte API at {self.base_url}: {exc.reason}"
            ) from exc

    def list_sources(self, workspace_id: str) -> Iterable[Dict[str, Any]]:
        response = self._post("/api/v1/sources/list", {"workspaceId": workspace_id})
        return response.get("sources") or []

    def create_source(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self._post("/api/v1/sources/create", payload)
        return response.get("source") or response

    def update_source(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self._post("/api/v1/sources/update", payload)
        return response.get("source") or response

    def check_source(self, source_id: str) -> Dict[str, Any]:
        response = self._post("/api/v1/sources/check_connection", {"sourceId": source_id})
        return response.get("jobInfo") or response

    def discover_schema(self, source_id: str) -> Dict[str, Any]:
        response = self._post("/api/v1/sources/discover_schema", {"sourceId": source_id})
        catalog = response.get("catalog")
        if not isinstance(catalog, dict):
            raise AirbyteProvisioningError(
                f"discover_schema returned no catalog for source {source_id}"
            )
        return catalog

    def list_connections(self, workspace_id: str) -> Iterable[Dict[str, Any]]:
        response = self._post("/api/v1/connections/list", {"workspaceId": workspace_id})
        return response.get("connections") or []

    def create_connection(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self._post("/api/v1/connections/create", payload)
        return response.get("connection") or response

    def update_connection(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self._post("/api/v1/connections/update", payload)
        return response.get("connection") or response


def _getenv_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise AirbyteProvisioningError(f"Missing required environment variable: {name}")
    return value


def _getenv_optional(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    cleaned = value.strip()
    if not cleaned:
        return default
    return cleaned


def _as_int(name: str, default: int) -> int:
    value = _getenv_optional(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise AirbyteProvisioningError(f"{name} must be an integer, got '{value}'") from exc


def _load_default_google_query() -> str:
    query_path = (
        pathlib.Path(__file__).resolve().parent.parent / "sources" / "google_ads_daily_metrics.sql"
    )
    if not query_path.exists():
        raise AirbyteProvisioningError(
            f"Missing default query template: {query_path}"
        )
    return query_path.read_text(encoding="utf-8").strip()


def _build_meta_configuration() -> Dict[str, Any]:
    return {
        "account_id": _getenv_required("AIRBYTE_META_ACCOUNT_ID"),
        "access_token": _getenv_required("AIRBYTE_META_ACCESS_TOKEN"),
        "app_id": _getenv_required("AIRBYTE_META_APP_ID"),
        "app_secret": _getenv_required("AIRBYTE_META_APP_SECRET"),
        "start_date": _getenv_optional("AIRBYTE_META_START_DATE", "2024-01-01T00:00:00Z"),
        "end_date": None,
        "page_size": _as_int("AIRBYTE_META_PAGE_SIZE", 100),
        "include_deleted": False,
        "action_breakdowns": ["action_type"],
        "breakdowns": ["region", "impression_device"],
        "insights_lookback_window": _as_int("AIRBYTE_META_INSIGHTS_LOOKBACK_DAYS", 3),
        "window_in_days": _as_int("AIRBYTE_META_HOURLY_WINDOW_DAYS", 3),
        "attribution_window": "default",
        "report_interval": "daily",
        "fetch_thumbnail_images": False,
        "custom_insights_fields": [
            "impressions",
            "clicks",
            "spend",
            "actions",
            "action_values",
        ],
    }


def _build_google_configuration() -> Dict[str, Any]:
    custom_query = _getenv_optional("AIRBYTE_GOOGLE_ADS_CUSTOM_QUERY")
    if custom_query is None:
        custom_query = _load_default_google_query()

    return {
        "developer_token": _getenv_required("AIRBYTE_GOOGLE_ADS_DEVELOPER_TOKEN"),
        "client_id": _getenv_required("AIRBYTE_GOOGLE_ADS_CLIENT_ID"),
        "client_secret": _getenv_required("AIRBYTE_GOOGLE_ADS_CLIENT_SECRET"),
        "refresh_token": _getenv_required("AIRBYTE_GOOGLE_ADS_REFRESH_TOKEN"),
        "customer_id": _getenv_required("AIRBYTE_GOOGLE_ADS_CUSTOMER_ID"),
        "login_customer_id": _getenv_required("AIRBYTE_GOOGLE_ADS_LOGIN_CUSTOMER_ID"),
        "start_date": _getenv_optional("AIRBYTE_GOOGLE_ADS_START_DATE", "2024-01-01"),
        "end_date": None,
        "conversion_window": _as_int("AIRBYTE_GOOGLE_ADS_CONVERSION_WINDOW_DAYS", 30),
        "lookback_window": _as_int("AIRBYTE_GOOGLE_ADS_LOOKBACK_WINDOW_DAYS", 3),
        "use_resource_custom_queries": True,
        "custom_queries": [
            {
                "name": "ad_group_ad_performance",
                "query": custom_query,
                "cursor_field": "date_day",
                "primary_key": ["campaign_id", "ad_group_id", "criterion_id", "date_day"],
                "destination_sync_mode": "append_dedup",
            }
        ],
    }


def _find_by_name(items: Iterable[Dict[str, Any]], name: str) -> Dict[str, Any] | None:
    for item in items:
        if item.get("name") == name:
            return item
    return None


def _configured_catalog(catalog: Dict[str, Any]) -> Dict[str, Any]:
    raw_streams = catalog.get("streams") or []
    configured_streams: list[Dict[str, Any]] = []

    for raw in raw_streams:
        supported_sync_modes = raw.get("supportedSyncModes") or ["full_refresh"]
        supported_dest_modes = raw.get("supportedDestinationSyncModes") or ["append"]
        incremental_supported = "incremental" in supported_sync_modes

        if incremental_supported:
            sync_mode = "incremental"
            if "append_dedup" in supported_dest_modes:
                destination_sync_mode = "append_dedup"
            elif "append" in supported_dest_modes:
                destination_sync_mode = "append"
            else:
                destination_sync_mode = supported_dest_modes[0]
        else:
            sync_mode = "full_refresh"
            if "overwrite" in supported_dest_modes:
                destination_sync_mode = "overwrite"
            else:
                destination_sync_mode = supported_dest_modes[0]

        cursor_field = raw.get("defaultCursorField") or []
        if not isinstance(cursor_field, list):
            cursor_field = []

        primary_key = raw.get("sourceDefinedPrimaryKey") or []
        if not isinstance(primary_key, list):
            primary_key = []

        configured_streams.append(
            {
                "stream": raw,
                "config": {
                    "aliasName": raw.get("name"),
                    "selected": True,
                    "syncMode": sync_mode,
                    "destinationSyncMode": destination_sync_mode,
                    "cursorField": cursor_field if incremental_supported else [],
                    "primaryKey": primary_key,
                },
            }
        )

    if not configured_streams:
        raise AirbyteProvisioningError("Discovered catalog has no streams.")

    return {"streams": configured_streams}


def _upsert_source(
    client: AirbyteClient,
    workspace_id: str,
    source_name: str,
    source_definition_id: str,
    configuration: Dict[str, Any],
) -> Dict[str, Any]:
    existing = _find_by_name(client.list_sources(workspace_id), source_name)

    if existing:
        payload = {
            "sourceId": existing["sourceId"],
            "name": source_name,
            "sourceDefinitionId": source_definition_id,
            "workspaceId": workspace_id,
            "connectionConfiguration": configuration,
        }
        return client.update_source(payload)

    payload = {
        "name": source_name,
        "sourceDefinitionId": source_definition_id,
        "workspaceId": workspace_id,
        "connectionConfiguration": configuration,
    }
    return client.create_source(payload)


def _upsert_connection(
    client: AirbyteClient,
    *,
    workspace_id: str,
    destination_id: str,
    source_id: str,
    connection_name: str,
    schedule_expression: str,
    schedule_timezone: str,
    stream_prefix: str,
    sync_catalog: Dict[str, Any],
) -> Dict[str, Any]:
    existing = _find_by_name(client.list_connections(workspace_id), connection_name)

    payload: Dict[str, Any] = {
        "name": connection_name,
        "sourceId": source_id,
        "destinationId": destination_id,
        "status": "active",
        "scheduleType": "cron",
        "scheduleData": {
            "cron": {
                "cronExpression": schedule_expression,
                "cronTimeZone": schedule_timezone,
            }
        },
        "schedule": None,
        "prefix": stream_prefix,
        "syncCatalog": sync_catalog,
        "namespaceDefinition": "destination",
        "operationIds": (existing or {}).get("operationIds") or [],
    }

    if existing:
        payload["connectionId"] = existing["connectionId"]
        return client.update_connection(payload)

    payload["workspaceId"] = workspace_id
    return client.create_connection(payload)


def _ensure_check_succeeded(check_response: Dict[str, Any], source_name: str) -> None:
    status = str(check_response.get("status", "")).lower()
    if status in {"succeeded", "success"}:
        return
    raise AirbyteProvisioningError(
        f"Source connectivity check failed for {source_name} (status={status or 'unknown'})"
    )


def _mask_summary(connector_summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source_name": connector_summary["source_name"],
        "source_id": connector_summary["source_id"],
        "source_check_status": connector_summary["source_check_status"],
        "connection_name": connector_summary["connection_name"],
        "connection_id": connector_summary["connection_id"],
    }


def main() -> int:
    try:
        workspace_id = _getenv_required("AIRBYTE_WORKSPACE_ID")
        destination_id = _getenv_optional(
            "AIRBYTE_TEMPLATE_DESTINATION_ID",
            _getenv_optional("AIRBYTE_TENANT_ALPHA_DESTINATION_ID"),
        )
        if not destination_id:
            raise AirbyteProvisioningError(
                "Set AIRBYTE_TEMPLATE_DESTINATION_ID (or AIRBYTE_TENANT_ALPHA_DESTINATION_ID)."
            )

        base_url = _getenv_optional("AIRBYTE_BASE_URL", "http://localhost:8001")
        auth_header = _getenv_optional("AIRBYTE_API_AUTH_HEADER")
        metrics_cron = _getenv_optional("AIRBYTE_DEFAULT_METRICS_CRON", DEFAULT_METRICS_CRON)
        metrics_timezone = _getenv_optional(
            "AIRBYTE_DEFAULT_METRICS_TIMEZONE", DEFAULT_METRICS_TIMEZONE
        )
        stream_prefix = _getenv_optional("AIRBYTE_DEFAULT_STREAM_PREFIX", "") or ""

        client = AirbyteClient(base_url=base_url or "http://localhost:8001", auth_header=auth_header)

        connector_summaries: list[Dict[str, Any]] = []
        connection_ids: Dict[str, str] = {}

        for spec in SPECS:
            if spec.key == "meta":
                source_configuration = _build_meta_configuration()
                source_name = _getenv_optional(spec.source_name_env, DEFAULT_META_SOURCE_NAME) or DEFAULT_META_SOURCE_NAME
                connection_name = _getenv_optional(spec.connection_name_env, DEFAULT_META_CONNECTION_NAME) or DEFAULT_META_CONNECTION_NAME
            else:
                source_configuration = _build_google_configuration()
                source_name = _getenv_optional(spec.source_name_env, DEFAULT_GOOGLE_SOURCE_NAME) or DEFAULT_GOOGLE_SOURCE_NAME
                connection_name = _getenv_optional(spec.connection_name_env, DEFAULT_GOOGLE_CONNECTION_NAME) or DEFAULT_GOOGLE_CONNECTION_NAME

            source = _upsert_source(
                client=client,
                workspace_id=workspace_id,
                source_name=source_name,
                source_definition_id=spec.source_definition_id,
                configuration=source_configuration,
            )
            source_id = source.get("sourceId")
            if not source_id:
                raise AirbyteProvisioningError(f"Airbyte did not return sourceId for {source_name}")

            source_check = client.check_source(source_id)
            _ensure_check_succeeded(source_check, source_name)

            discovered_catalog = client.discover_schema(source_id)
            sync_catalog = _configured_catalog(discovered_catalog)

            connection = _upsert_connection(
                client=client,
                workspace_id=workspace_id,
                destination_id=destination_id,
                source_id=source_id,
                connection_name=connection_name,
                schedule_expression=metrics_cron or DEFAULT_METRICS_CRON,
                schedule_timezone=metrics_timezone or DEFAULT_METRICS_TIMEZONE,
                stream_prefix=stream_prefix,
                sync_catalog=sync_catalog,
            )

            connection_id = connection.get("connectionId")
            if not connection_id:
                raise AirbyteProvisioningError(
                    f"Airbyte did not return connectionId for {connection_name}"
                )

            connector_summaries.append(
                {
                    "key": spec.key,
                    "source_name": source_name,
                    "source_id": source_id,
                    "source_check_status": source_check.get("status"),
                    "connection_name": connection_name,
                    "connection_id": connection_id,
                }
            )
            connection_ids[spec.key] = connection_id

        print(
            json.dumps(
                {
                    "status": "ok",
                    "workspace_id": workspace_id,
                    "destination_id": destination_id,
                    "connectors": [_mask_summary(item) for item in connector_summaries],
                    "env_exports": {
                        "AIRBYTE_TEMPLATE_META_METRICS_CONNECTION_ID": connection_ids.get("meta"),
                        "AIRBYTE_TEMPLATE_GOOGLE_METRICS_CONNECTION_ID": connection_ids.get("google"),
                    },
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    except AirbyteProvisioningError as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
