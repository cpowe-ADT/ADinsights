from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Optional

from django.contrib.auth import get_user_model

from .models import AuditLog, Tenant

UserModel = get_user_model()


Metadata = Mapping[str, Any]
MutableMetadata = MutableMapping[str, Any]


def _normalise_metadata(metadata: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    if metadata is None:
        return {}
    if isinstance(metadata, dict):
        return metadata
    return dict(metadata)


def log_audit_event(
    *,
    tenant: Tenant,
    action: str,
    resource_type: str,
    resource_id: str | int,
    user: Optional[UserModel] = None,
    metadata: Optional[Mapping[str, Any]] = None,
    request: Optional[Any] = None,
) -> AuditLog:
    """Persist an audit log entry.

    Parameters mirror the :class:`AuditLog` model fields while taking care of
    coercing the ``resource_id`` to a string and normalising any metadata to a
    JSON serialisable dictionary.

    If a ``request`` is provided, ``actor_ip`` and ``user_agent`` are extracted
    and merged into the metadata.
    """

    final_metadata = _normalise_metadata(metadata).copy()
    if request:
        # Extract IP (respecting proxy headers if configured in middleware)
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")
        
        final_metadata["actor_ip"] = ip
        final_metadata["user_agent"] = request.META.get("HTTP_USER_AGENT")

    return AuditLog.all_objects.create(
        tenant=tenant,
        user=user,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        metadata=final_metadata,
    )
