#!/usr/bin/env python3
"""Bootstrap or update Airbyte connections per tenant using env-driven config."""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any, Dict, Iterable, Optional

from urllib import error, request

if __package__ is None or __package__ == "":  # pragma: no cover - CLI execution path
    current_dir = pathlib.Path(__file__).resolve().parent
    if str(current_dir) not in sys.path:
        sys.path.append(str(current_dir))
    from config import (  # type: ignore
        TEMPLATE_ORDER,
        AirbyteEnvironment,
        TenantConfig,
        TenantConnectionConfig,
        load_environment,
    )
else:  # pragma: no cover - module execution path
    from .config import (
        TEMPLATE_ORDER,
        AirbyteEnvironment,
        TenantConfig,
        TenantConnectionConfig,
        load_environment,
    )


class AirbyteClient:
    def __init__(self, base_url: str, auth_header: Optional[str]):
        self.base_url = base_url.rstrip("/")
        self.auth_header = auth_header

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if self.auth_header:
            headers["Authorization"] = self.auth_header
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Airbyte API {path} failed with HTTP {exc.code}: {message}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Unable to reach Airbyte API at {self.base_url}: {exc.reason}") from exc

    def get_connection(self, connection_id: str) -> Dict[str, Any]:
        resp = self._post("/api/v1/connections/get", {"connectionId": connection_id})
        return resp.get("connection") or resp

    def list_connections(self, workspace_id: str) -> Iterable[Dict[str, Any]]:
        resp = self._post("/api/v1/connections/list", {"workspaceId": workspace_id})
        return resp.get("connections") or []

    def create_connection(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = self._post("/api/v1/connections/create", payload)
        return resp.get("connection") or resp

    def update_connection(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = self._post("/api/v1/connections/update", payload)
        return resp.get("connection") or resp


def _merge_optional_fields(template: Dict[str, Any], existing: Optional[Dict[str, Any]], *fields: str) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for field in fields:
        if existing and existing.get(field) is not None:
            merged[field] = existing[field]
        elif template.get(field) is not None:
            merged[field] = template[field]
    return merged


def _find_connection_by_name(connections: Iterable[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    for conn in connections:
        if conn.get("name") == name:
            return conn
    return None


def _build_payload(
    tenant: TenantConfig,
    conn_cfg: TenantConnectionConfig,
    template_conn: Dict[str, Any],
    existing_conn: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    schedule_type, schedule_data = conn_cfg.schedule.to_airbyte_payload()
    prefix = conn_cfg.prefix
    if prefix is None:
        prefix = tenant.stream_prefix or ""

    payload: Dict[str, Any] = {
        "name": conn_cfg.name,
        "sourceId": template_conn.get("sourceId") if template_conn else (existing_conn or {}).get("sourceId"),
        "destinationId": tenant.destination_id,
        "operationIds": (existing_conn or template_conn or {}).get("operationIds") or [],
        "status": conn_cfg.status,
        "scheduleType": schedule_type,
        "scheduleData": schedule_data,
        "schedule": None,
        "prefix": prefix,
    }

    # Namespace + formatting
    if tenant.namespace:
        payload.update({
            "namespaceDefinition": "customformat",
            "namespaceFormat": tenant.namespace,
        })
    else:
        payload.update(
            _merge_optional_fields(
                template_conn or {},
                existing_conn,
                "namespaceDefinition",
                "namespaceFormat",
            )
        )

    # Preserve additional template metadata where present.
    payload.update(
        _merge_optional_fields(
            template_conn or {},
            existing_conn,
            "geography",
            "resourceRequirements",
            "notifySchemaChanges",
            "nonBreakingChangesPreference",
            "dataResidency",
            "backfillPreference",
            "dataPlaneResourceConfigurationId",
            "sourceCatalogId",
            "customTransformations",
        )
    )

    # syncCatalog is required when creating; prefer existing to preserve overrides.
    sync_catalog = (existing_conn or {}).get("syncCatalog") or (template_conn or {}).get("syncCatalog")
    if sync_catalog:
        payload["syncCatalog"] = sync_catalog

    return payload


def _ensure_connection(
    client: AirbyteClient,
    tenant: TenantConfig,
    template_conn: Dict[str, Any],
    conn_cfg: TenantConnectionConfig,
) -> Dict[str, Any]:
    existing_conn: Optional[Dict[str, Any]] = None
    if conn_cfg.existing_connection_id:
        try:
            existing_conn = client.get_connection(conn_cfg.existing_connection_id)
        except RuntimeError as exc:
            raise RuntimeError(
                f"Unable to fetch existing connection {conn_cfg.existing_connection_id} for tenant {tenant.slug}: {exc}"
            ) from exc

    if existing_conn is None:
        connections = list(client.list_connections(tenant.workspace_id))
        existing_conn = _find_connection_by_name(connections, conn_cfg.name)

    payload = _build_payload(tenant, conn_cfg, template_conn, existing_conn)

    if existing_conn:
        payload["connectionId"] = existing_conn["connectionId"]
        return client.update_connection(payload)

    payload["workspaceId"] = tenant.workspace_id
    return client.create_connection(payload)


def _summarize_connection(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "connectionId": result.get("connectionId"),
        "name": result.get("name"),
        "destinationId": result.get("destinationId"),
        "status": result.get("status"),
        "scheduleType": result.get("scheduleType"),
        "scheduleData": result.get("scheduleData"),
    }


def main() -> int:
    try:
        env: AirbyteEnvironment = load_environment()
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        return 2

    client = AirbyteClient(env.base_url, env.auth_header)
    template_cache: Dict[str, Dict[str, Any]] = {}

    for template in TEMPLATE_ORDER:
        template_id = env.template_connection_id(template.key)
        try:
            template_cache[template.key] = client.get_connection(template_id)
        except RuntimeError as exc:
            print(f"Failed to load template connection {template.key} ({template_id}): {exc}")
            return 2

    results: Dict[str, Dict[str, Any]] = {"tenants": []}

    for tenant in env.tenants:
        tenant_summary = {
            "slug": tenant.slug,
            "workspaceId": tenant.workspace_id,
            "connections": [],
        }
        for template in TEMPLATE_ORDER:
            conn_cfg = tenant.connection(template.key)
            try:
                result = _ensure_connection(
                    client=client,
                    tenant=tenant,
                    template_conn=template_cache[template.key],
                    conn_cfg=conn_cfg,
                )
            except RuntimeError as exc:
                tenant_summary.setdefault("errors", []).append({
                    "template": template.key,
                    "message": str(exc),
                })
                continue
            tenant_summary["connections"].append({
                "template": template.key,
                "result": _summarize_connection(result),
            })
        results["tenants"].append(tenant_summary)

    print(json.dumps(results, indent=2, sort_keys=True))
    has_errors = any("errors" in tenant for tenant in results["tenants"])
    return 1 if has_errors else 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
