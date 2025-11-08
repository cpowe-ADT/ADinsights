from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Iterator, Optional

from django.conf import settings
from django.db import connection

_current_tenant_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_tenant_id", default=None
)


def set_current_tenant_id(tenant_id: Optional[str]) -> None:
    _current_tenant_id.set(tenant_id)


def get_current_tenant_id() -> Optional[str]:
    return _current_tenant_id.get()


def clear_current_tenant() -> None:
    _current_tenant_id.set(None)


def set_connection_tenant(tenant_id: Optional[str]) -> None:
    """Propagate the tenant identifier to the active DB connection."""

    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            if tenant_id:
                cursor.execute("SET app.tenant_id = %s", [tenant_id])
            else:
                cursor.execute("SET app.tenant_id = DEFAULT")
    else:
        setattr(connection, settings.TENANT_SETTING_KEY, tenant_id)


def reset_connection_tenant() -> None:
    """Reset the DB connection tenant context."""

    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("RESET app.tenant_id")
    else:
        setattr(connection, settings.TENANT_SETTING_KEY, None)


@contextmanager
def tenant_context(tenant_id: Optional[str]) -> Iterator[None]:
    """Context manager that sets tenant context for ORM + connection."""

    previous = get_current_tenant_id()
    set_current_tenant_id(tenant_id)
    set_connection_tenant(tenant_id)
    try:
        yield
    finally:
        if previous is None:
            clear_current_tenant()
            reset_connection_tenant()
        else:
            set_current_tenant_id(previous)
            set_connection_tenant(previous)
