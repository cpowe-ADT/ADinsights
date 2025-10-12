from __future__ import annotations

import contextvars
from typing import Optional

_current_tenant_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_tenant_id", default=None
)


def set_current_tenant_id(tenant_id: Optional[str]) -> None:
    _current_tenant_id.set(tenant_id)


def get_current_tenant_id() -> Optional[str]:
    return _current_tenant_id.get()


def clear_current_tenant() -> None:
    _current_tenant_id.set(None)
