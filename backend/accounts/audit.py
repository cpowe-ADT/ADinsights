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
) -> AuditLog:
    """Persist an audit log entry.

    Parameters mirror the :class:`AuditLog` model fields while taking care of
    coercing the ``resource_id`` to a string and normalising any metadata to a
    JSON serialisable dictionary. The helper returns the created ``AuditLog`` to
    support follow-up assertions in tests.
    """

    return AuditLog.all_objects.create(
        tenant=tenant,
        user=user,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        metadata=_normalise_metadata(metadata),
    )
