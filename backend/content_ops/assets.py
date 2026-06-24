"""Tenant-scoped file storage helpers for Content Operations assets."""

from __future__ import annotations

import mimetypes
import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.db.models import F

from .models import ContentDraft, ContentWorkspace, MediaAsset


ASSET_STORAGE_PREFIX = "content_ops/assets"
ALLOWED_ASSET_MIME_PREFIXES = ("image/", "video/")
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
ASSET_PUBLISH_STATUS_UNAVAILABLE = "asset_not_available"
ASSET_PUBLISH_FILE_MISSING = "asset_file_missing"
ASSET_PUBLISH_STORAGE_KEY_INVALID = "asset_storage_key_invalid"
ASSET_PUBLISH_MIME_UNSUPPORTED = "asset_mime_type_unsupported"
ASSET_PUBLISH_PUBLIC_URL_MISSING = "asset_public_url_missing"
ASSET_PUBLISH_PUBLIC_URL_NOT_FETCHABLE = "asset_public_url_not_fetchable"
ASSET_PUBLISH_NOT_APPROVED_FOR_PUBLIC_FETCH = "asset_not_approved_for_public_fetch"
PUBLISH_PUBLIC_URL_KEYS = ("public_url", "source_url", "media_url", "fetch_url")
PUBLISH_RENDITION_KEYS = ("original", "default", "source", "media")
PUBLIC_MEDIA_APPROVED_DRAFT_STATES = (
    ContentDraft.STATE_CLIENT_APPROVED,
    ContentDraft.STATE_SCHEDULED,
    ContentDraft.STATE_PUBLISHING,
    ContentDraft.STATE_PUBLISHED,
    ContentDraft.STATE_PARTIALLY_PUBLISHED,
)


class ContentOpsAssetStorageError(ValueError):
    """Client-safe asset storage validation error."""


@dataclass(frozen=True)
class AssetPublishValidationResult:
    ready: bool
    failure_code: str = ""
    failure_detail_safe: str = ""
    asset_id: str = ""

    def as_dict(self) -> dict[str, str | bool]:
        return {
            "ready": self.ready,
            "failure_code": self.failure_code,
            "failure_detail_safe": self.failure_detail_safe,
            "asset_id": self.asset_id,
        }


def asset_storage_root() -> Path:
    """Return the configured Content Ops asset root."""

    root = getattr(settings, "CONTENT_OPS_ASSET_ROOT", None)
    if root:
        return Path(root)
    return Path(settings.REPORT_EXPORT_ARTIFACT_ROOT) / "content_ops_assets"


def max_asset_upload_bytes() -> int:
    return int(getattr(settings, "CONTENT_OPS_ASSET_MAX_UPLOAD_BYTES", 25 * 1024 * 1024))


def store_uploaded_asset(
    *,
    tenant,
    workspace: ContentWorkspace,
    upload,
    alt_text: str = "",
) -> MediaAsset:
    """Persist an uploaded file and create a tenant-scoped MediaAsset row."""

    if workspace.tenant_id != tenant.id:
        raise ContentOpsAssetStorageError("workspace_wrong_tenant")
    _validate_upload(upload)
    asset_id = uuid.uuid4()
    filename = _safe_filename(getattr(upload, "name", "") or "asset")
    storage_key = (
        f"{ASSET_STORAGE_PREFIX}/{tenant.id}/{workspace.id}/{asset_id}/{filename}"
    )
    file_path = asset_file_path(storage_key)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("wb") as destination:
        for chunk in _chunks(upload):
            destination.write(chunk)
    if file_path.stat().st_size == 0:
        file_path.unlink(missing_ok=True)
        raise ContentOpsAssetStorageError("asset_empty")
    return MediaAsset.all_objects.create(
        id=asset_id,
        tenant=tenant,
        workspace=workspace,
        source=MediaAsset.SOURCE_UPLOADED,
        storage_key=storage_key,
        mime_type=str(getattr(upload, "content_type", "") or "application/octet-stream"),
        alt_text=alt_text[:1000],
        status=MediaAsset.STATUS_AVAILABLE,
    )


def max_generated_asset_bytes() -> int:
    return int(
        getattr(settings, "CONTENT_OPS_GENERATED_ASSET_MAX_BYTES", 15 * 1024 * 1024)
    )


def _extension_for_mime(mime_type: str) -> str:
    mime = str(mime_type or "").split(";")[0].strip().lower()
    known = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "video/mp4": ".mp4",
        "video/quicktime": ".mov",
    }
    if mime in known:
        return known[mime]
    return (mimetypes.guess_extension(mime) if mime else None) or ""


def store_generated_asset_bytes(
    *,
    tenant,
    workspace: ContentWorkspace,
    content: bytes,
    mime_type: str,
    alt_text: str = "",
    ai_lineage: dict[str, Any] | None = None,
    width: int | None = None,
    height: int | None = None,
    max_bytes: int | None = None,
) -> MediaAsset:
    """Persist generated media bytes; quarantine oversized or unsupported output.

    Empty output is a generation failure (raises). Output with an unsupported
    mime type or larger than the configured limit is recorded in QUARANTINED
    status with no stored file (the rejected bytes are never written to disk),
    so it can never be published.
    """

    if workspace.tenant_id != tenant.id:
        raise ContentOpsAssetStorageError("workspace_wrong_tenant")
    if not content:
        raise ContentOpsAssetStorageError("asset_empty")
    limit = int(max_bytes) if max_bytes else max_generated_asset_bytes()
    mime = str(mime_type or "").strip()
    quarantine_reason = ""
    if not any(mime.startswith(prefix) for prefix in ALLOWED_ASSET_MIME_PREFIXES):
        quarantine_reason = "unsupported_mime"
    elif len(content) > limit:
        quarantine_reason = "too_large"
    asset_id = uuid.uuid4()
    lineage = dict(ai_lineage or {})
    if quarantine_reason:
        # Rejected output is never published, so skip writing the bytes to disk.
        lineage["quarantine_reason"] = quarantine_reason
        storage_key = ""
    else:
        storage_key = (
            f"{ASSET_STORAGE_PREFIX}/{tenant.id}/{workspace.id}/{asset_id}/"
            f"generated{_extension_for_mime(mime)}"
        )
        file_path = asset_file_path(storage_key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
    return MediaAsset.all_objects.create(
        id=asset_id,
        tenant=tenant,
        workspace=workspace,
        source=MediaAsset.SOURCE_AI_GENERATED,
        storage_key=storage_key,
        mime_type=mime or "application/octet-stream",
        width=width,
        height=height,
        alt_text=alt_text[:1000],
        ai_lineage=lineage,
        status=(
            MediaAsset.STATUS_QUARANTINED
            if quarantine_reason
            else MediaAsset.STATUS_AVAILABLE
        ),
    )


def asset_file_path(storage_key: str) -> Path:
    """Resolve and validate a stored asset path under the configured root."""

    if not storage_key.startswith(f"{ASSET_STORAGE_PREFIX}/"):
        raise ContentOpsAssetStorageError("asset_storage_key_invalid")
    if ".." in Path(storage_key).parts:
        raise ContentOpsAssetStorageError("asset_storage_key_unsafe")
    root = asset_storage_root().resolve()
    path = (root / storage_key).resolve()
    if not path.is_relative_to(root):
        raise ContentOpsAssetStorageError("asset_storage_key_unsafe")
    return path


def validate_media_assets_for_publish(
    assets: Iterable[MediaAsset],
) -> AssetPublishValidationResult:
    """Validate attached media has local file proof and public HTTPS fetch URL metadata."""

    for asset in assets:
        result = validate_media_asset_for_publish(asset)
        if not result.ready:
            return result
    return AssetPublishValidationResult(ready=True)


def validate_media_asset_for_publish(asset: MediaAsset) -> AssetPublishValidationResult:
    if asset.status != MediaAsset.STATUS_AVAILABLE:
        return _publish_asset_blocked(
            asset=asset,
            code=ASSET_PUBLISH_STATUS_UNAVAILABLE,
            detail="Attached media asset is not available.",
        )
    if not any(str(asset.mime_type or "").startswith(prefix) for prefix in ALLOWED_ASSET_MIME_PREFIXES):
        return _publish_asset_blocked(
            asset=asset,
            code=ASSET_PUBLISH_MIME_UNSUPPORTED,
            detail="Attached media asset type is not supported for publishing.",
        )
    try:
        file_path = asset_file_path(asset.storage_key)
    except ContentOpsAssetStorageError:
        return _publish_asset_blocked(
            asset=asset,
            code=ASSET_PUBLISH_STORAGE_KEY_INVALID,
            detail="Attached media asset storage key is invalid.",
        )
    if not file_path.exists() or file_path.stat().st_size <= 0:
        return _publish_asset_blocked(
            asset=asset,
            code=ASSET_PUBLISH_FILE_MISSING,
            detail="Attached media asset file is missing or empty.",
        )
    public_url = public_media_fetch_url(asset)
    if not public_url:
        return _publish_asset_blocked(
            asset=asset,
            code=ASSET_PUBLISH_PUBLIC_URL_MISSING,
            detail="Attached media asset is missing public HTTPS fetch URL proof.",
        )
    if not is_public_https_url(public_url):
        return _publish_asset_blocked(
            asset=asset,
            code=ASSET_PUBLISH_PUBLIC_URL_NOT_FETCHABLE,
            detail="Attached media asset public URL is not a public HTTPS URL.",
        )
    return AssetPublishValidationResult(ready=True, asset_id=str(asset.id))


def public_media_fetch_url(asset: MediaAsset) -> str:
    renditions = asset.renditions if isinstance(asset.renditions, dict) else {}
    direct = _first_string_key(renditions, PUBLISH_PUBLIC_URL_KEYS)
    if direct:
        return direct
    for key in PUBLISH_RENDITION_KEYS:
        candidate = renditions.get(key)
        if isinstance(candidate, dict):
            nested = _first_string_key(candidate, PUBLISH_PUBLIC_URL_KEYS)
            if nested:
                return nested
    return configured_public_media_fetch_url(asset)


def configured_public_media_fetch_url(asset: MediaAsset) -> str:
    base_url = str(getattr(settings, "CONTENT_OPS_PUBLIC_MEDIA_BASE_URL", "") or "").strip()
    if not base_url:
        return ""
    return f"{base_url.rstrip('/')}/{asset.id}/"


def asset_has_public_fetch_approval(asset: MediaAsset) -> bool:
    return asset.draft_versions.filter(
        draft__active_version_id=F("id"),
        draft__state__in=PUBLIC_MEDIA_APPROVED_DRAFT_STATES,
    ).exists()


def public_media_asset_proof(asset: MediaAsset) -> dict[str, Any]:
    validation = validate_media_asset_for_publish(asset)
    approved = asset_has_public_fetch_approval(asset)
    ready = validation.ready and approved
    failure_code = validation.failure_code
    failure_detail = validation.failure_detail_safe
    if validation.ready and not approved:
        failure_code = ASSET_PUBLISH_NOT_APPROVED_FOR_PUBLIC_FETCH
        failure_detail = "Attached media asset is not approved for public Meta fetch."
    content_length = 0
    if validation.ready:
        try:
            file_path = asset_file_path(asset.storage_key)
        except ContentOpsAssetStorageError:
            content_length = 0
        else:
            content_length = file_path.stat().st_size if file_path.exists() else 0
    public_url = public_media_fetch_url(asset)
    parsed = urlparse(public_url)
    return {
        "ready": ready,
        "asset_id": str(asset.id),
        "failure_code": "" if ready else failure_code,
        "failure_detail_safe": "" if ready else failure_detail,
        "public_url_scheme": parsed.scheme if public_url else "",
        "public_url_host": parsed.hostname or "",
        "public_url_redacted": _redacted_public_url(public_url),
        "public_url_is_https": is_public_https_url(public_url) if public_url else False,
        "approved_for_public_fetch": approved,
        "mime_type": asset.mime_type,
        "content_length": content_length,
        "storage_key_exposed": False,
    }


def is_public_https_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        return False
    if parsed.username or parsed.password:
        return False
    host = parsed.hostname
    if not host:
        return False
    normalized_host = host.strip().lower().rstrip(".")
    if normalized_host in {"localhost", "0.0.0.0"} or normalized_host.endswith(".local"):
        return False
    try:
        address = ip_address(normalized_host)
    except ValueError:
        return "." in normalized_host
    return address.is_global


def _redacted_public_url(value: str) -> str:
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return ""
    path_parts = [part for part in parsed.path.split("/") if part]
    tail = path_parts[-1] if path_parts else ""
    redacted_path = f"/.../{tail}" if tail else "/..."
    return f"{parsed.scheme}://{parsed.netloc}{redacted_path}"


def _publish_asset_blocked(
    *,
    asset: MediaAsset,
    code: str,
    detail: str,
) -> AssetPublishValidationResult:
    return AssetPublishValidationResult(
        ready=False,
        failure_code=code,
        failure_detail_safe=detail,
        asset_id=str(asset.id),
    )


def _first_string_key(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _validate_upload(upload) -> None:
    if upload is None:
        raise ContentOpsAssetStorageError("file_required")
    size = int(getattr(upload, "size", 0) or 0)
    if size <= 0:
        raise ContentOpsAssetStorageError("asset_empty")
    if size > max_asset_upload_bytes():
        raise ContentOpsAssetStorageError("asset_too_large")
    content_type = str(getattr(upload, "content_type", "") or "")
    if not any(content_type.startswith(prefix) for prefix in ALLOWED_ASSET_MIME_PREFIXES):
        raise ContentOpsAssetStorageError("asset_mime_type_unsupported")


def _safe_filename(value: str) -> str:
    name = Path(value).name.strip().replace(" ", "_")
    name = SAFE_FILENAME_RE.sub("_", name).strip("._")
    return name[:120] or "asset"


def _chunks(upload) -> Iterable[bytes]:
    chunks = getattr(upload, "chunks", None)
    if callable(chunks):
        return chunks()
    return [upload.read()]
