from backend.core.settings import *  # noqa
from backend.core.settings import REST_FRAMEWORK as CORE_REST_FRAMEWORK

REST_FRAMEWORK = {
    **CORE_REST_FRAMEWORK,
    "DEFAULT_PERMISSION_CLASSES": (
        "accounts.permissions.IsTenantUser",
    ),
}
