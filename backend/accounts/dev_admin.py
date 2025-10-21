from __future__ import annotations

import os
from typing import Tuple

from django.conf import settings

from .models import Tenant, User, Role, assign_role


def ensure_default_admin() -> Tuple[bool, str]:
    """Create/update a default admin when explicitly allowed via env.

    Safe guards:
    - Only runs when ALLOW_DEFAULT_ADMIN=1 (or truthy) to avoid accidental users.
    - Intended for local/dev use; does nothing in production unless explicitly enabled.
    """

    allowed = str(os.environ.get("ALLOW_DEFAULT_ADMIN", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }
    if not allowed:
        return False, "default admin not allowed"

    username = os.environ.get("DJANGO_DEFAULT_ADMIN_USERNAME", "admin").strip() or "admin"
    email = os.environ.get("DJANGO_DEFAULT_ADMIN_EMAIL", "admin@example.com").strip() or "admin@example.com"
    password = os.environ.get("DJANGO_DEFAULT_ADMIN_PASSWORD", "admin1")

    tenant, _ = Tenant.objects.get_or_create(name="Default Tenant")

    user = User.objects.filter(username=username).first()
    created = False
    if user is None:
        user = User(username=username, tenant=tenant, email=email, first_name="Admin", last_name="User")
        created = True
    else:
        if not user.tenant_id:
            user.tenant = tenant
        user.email = email or user.email

    user.set_password(password)
    user.is_staff = True
    user.is_superuser = True
    user.save()

    assign_role(user, Role.ADMIN)

    return True, ("created" if created else "updated")

