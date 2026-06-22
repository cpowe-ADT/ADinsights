"""Persisted export artifact helpers for Content Operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone

from .models import ContentExportArtifact, ContentWorkspace

CONTENT_EXPORT_PREFIX = "/content_ops/exports/"


class ContentOpsExportArtifactError(ValueError):
    """Client-safe export artifact validation error."""


def content_exports_root() -> Path:
    return Path(settings.REPORT_EXPORT_ARTIFACT_ROOT)


def create_content_plan_export_artifact(
    *,
    tenant,
    workspace: ContentWorkspace,
    payload: dict[str, Any],
    requested_by,
    states: list[str],
) -> ContentExportArtifact:
    artifact = ContentExportArtifact.all_objects.create(
        tenant=tenant,
        workspace=workspace,
        export_type=ContentExportArtifact.TYPE_CONTENT_PLAN,
        export_format=ContentExportArtifact.FORMAT_JSON,
        status=ContentExportArtifact.STATUS_COMPLETED,
        item_count=int(payload.get("item_count") or 0),
        requested_by=requested_by,
        completed_at=timezone.now(),
        metadata={
            "workspace_id": str(workspace.id),
            "workspace_name": workspace.name,
            "states": states,
        },
    )
    artifact_path, file_path = _artifact_file_path(
        tenant_id=str(tenant.id),
        workspace_id=str(workspace.id),
        artifact_id=str(artifact.id),
    )
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    _verify_artifact_path(artifact_path)
    artifact.artifact_path = artifact_path
    artifact.save(update_fields=["artifact_path", "updated_at"])
    return artifact


def resolve_content_export_artifact_path(artifact_path: str) -> Path:
    _verify_artifact_path(artifact_path)
    root = content_exports_root().resolve()
    resolved = (root / artifact_path.lstrip("/")).resolve()
    if not resolved.is_relative_to(root):
        raise ContentOpsExportArtifactError("export_artifact_path_unsafe")
    if not resolved.exists() or resolved.stat().st_size <= 0:
        raise ContentOpsExportArtifactError("export_artifact_missing")
    return resolved


def _artifact_file_path(
    *,
    tenant_id: str,
    workspace_id: str,
    artifact_id: str,
) -> tuple[str, Path]:
    artifact_path = (
        f"{CONTENT_EXPORT_PREFIX}{tenant_id}/{workspace_id}/{artifact_id}.json"
    )
    root = content_exports_root().resolve()
    file_path = (root / artifact_path.lstrip("/")).resolve()
    if not file_path.is_relative_to(root):
        raise ContentOpsExportArtifactError("export_artifact_path_unsafe")
    return artifact_path, file_path


def _verify_artifact_path(artifact_path: str) -> None:
    if not artifact_path.startswith(CONTENT_EXPORT_PREFIX):
        raise ContentOpsExportArtifactError("export_artifact_path_invalid")
    if ".." in Path(artifact_path).parts:
        raise ContentOpsExportArtifactError("export_artifact_path_unsafe")
