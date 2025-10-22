#!/usr/bin/env python3
"""Validate Airbyte tenant configuration before deploying bootstrap changes."""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any, Dict, Optional

from urllib import error, request

if __package__ is None or __package__ == "":  # pragma: no cover - CLI execution path
    current_dir = pathlib.Path(__file__).resolve().parent
    if str(current_dir) not in sys.path:
        sys.path.append(str(current_dir))
    from config import (  # type: ignore
        TEMPLATE_ORDER,
        AirbyteEnvironment,
        TenantConfig,
        load_environment,
    )
else:  # pragma: no cover - module execution path
    from .config import (
        TEMPLATE_ORDER,
        AirbyteEnvironment,
        TenantConfig,
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
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Airbyte API {path} failed with HTTP {exc.code}: {message}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Unable to reach Airbyte API at {self.base_url}: {exc.reason}") from exc

    def get_destination(self, destination_id: str) -> Dict[str, Any]:
        resp = self._post("/api/v1/destinations/get", {"destinationId": destination_id})
        return resp.get("destination") or resp

    def get_workspace(self, workspace_id: str) -> Dict[str, Any]:
        resp = self._post("/api/v1/workspaces/get", {"workspaceId": workspace_id})
        return resp.get("workspace") or resp

    def get_connection(self, connection_id: str) -> Dict[str, Any]:
        resp = self._post("/api/v1/connections/get", {"connectionId": connection_id})
        return resp.get("connection") or resp


def _validate_tenant(
    client: AirbyteClient,
    tenant: TenantConfig,
    template_lookup: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    tenant_report: Dict[str, Any] = {
        "slug": tenant.slug,
        "workspaceId": tenant.workspace_id,
        "destinationId": tenant.destination_id,
        "checks": [],
        "warnings": [],
        "errors": [],
    }

    try:
        workspace = client.get_workspace(tenant.workspace_id)
        tenant_report["workspaceName"] = workspace.get("name")
    except RuntimeError as exc:
        tenant_report["errors"].append({"check": "workspace", "message": str(exc)})

    try:
        destination = client.get_destination(tenant.destination_id)
        tenant_report["destinationName"] = destination.get("name")
        dest_workspace = destination.get("workspaceId")
        if dest_workspace and dest_workspace != tenant.workspace_id:
            tenant_report["warnings"].append(
                {
                    "check": "destination",
                    "message": (
                        "Destination belongs to workspace "
                        f"{dest_workspace} instead of {tenant.workspace_id}"
                    ),
                }
            )
    except RuntimeError as exc:
        tenant_report["errors"].append({"check": "destination", "message": str(exc)})

    if tenant.bucket and "//" not in tenant.bucket:
        tenant_report["warnings"].append(
            {
                "check": "bucket",
                "message": f"Bucket '{tenant.bucket}' should be a URI (e.g. s3://bucket)",
            }
        )

    for template in TEMPLATE_ORDER:
        conn_cfg = tenant.connection(template.key)
        label = f"{tenant.slug}:{template.key}"
        for error_msg in conn_cfg.schedule.validate(label):
            tenant_report["errors"].append({"check": "schedule", "message": error_msg})

        if conn_cfg.existing_connection_id:
            try:
                existing = client.get_connection(conn_cfg.existing_connection_id)
                if existing.get("workspaceId") and existing["workspaceId"] != tenant.workspace_id:
                    tenant_report["errors"].append(
                        {
                            "check": "connection",
                            "message": (
                                f"Existing connection {conn_cfg.existing_connection_id} belongs to workspace "
                                f"{existing.get('workspaceId')}"
                            ),
                        }
                    )
            except RuntimeError as exc:
                tenant_report["errors"].append(
                    {
                        "check": "connection",
                        "message": f"Unable to load existing connection {conn_cfg.existing_connection_id}: {exc}",
                    }
                )

        template_conn = template_lookup.get(template.key)
        if not template_conn:
            tenant_report["errors"].append(
                {
                    "check": "template",
                    "message": f"Template connection {template.key} is unavailable",
                }
            )
            continue

        tenant_report["checks"].append(
            {
                "template": template.key,
                "desiredName": conn_cfg.name,
                "scheduleType": conn_cfg.schedule.to_airbyte_payload()[0],
                "status": conn_cfg.status,
            }
        )

    if not tenant_report["errors"]:
        tenant_report.pop("errors")
    if not tenant_report["warnings"]:
        tenant_report.pop("warnings")

    return tenant_report


def main() -> int:
    try:
        env: AirbyteEnvironment = load_environment()
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        return 2

    client = AirbyteClient(env.base_url, env.auth_header)
    template_lookup: Dict[str, Dict[str, Any]] = {}
    for template in TEMPLATE_ORDER:
        template_id = env.template_connection_id(template.key)
        try:
            template_lookup[template.key] = client.get_connection(template_id)
        except RuntimeError as exc:
            print(f"Unable to load template connection {template.key} ({template_id}): {exc}")
            return 2

    report = {
        "baseUrl": env.base_url,
        "tenants": [],
    }

    has_errors = False
    for tenant in env.tenants:
        tenant_report = _validate_tenant(client, tenant, template_lookup)
        if "errors" in tenant_report:
            has_errors = True
        report["tenants"].append(tenant_report)

    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
