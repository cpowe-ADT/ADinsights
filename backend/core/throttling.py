"""DRF throttle classes for unauthenticated/auth flows."""

from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured
from rest_framework.settings import api_settings
from rest_framework.throttling import AnonRateThrottle


class _DynamicRateAnonThrottle(AnonRateThrottle):
    """Resolve rates from the active REST framework settings each request."""

    def get_rate(self) -> str | None:
        if not getattr(self, "scope", None):
            msg = f"You must set `.scope` for '{self.__class__.__name__}' throttle"
            raise ImproperlyConfigured(msg)

        rates = api_settings.DEFAULT_THROTTLE_RATES
        try:
            return rates[self.scope]
        except KeyError as exc:
            msg = f"No default throttle rate set for '{self.scope}' scope"
            raise ImproperlyConfigured(msg) from exc


class AuthBurstRateThrottle(_DynamicRateAnonThrottle):
    """Short-window limiter for login/reset/signup endpoints."""

    scope = "auth_burst"


class AuthSustainedRateThrottle(_DynamicRateAnonThrottle):
    """Long-window limiter to cap repeated authentication attempts."""

    scope = "auth_sustained"


class PublicEndpointRateThrottle(_DynamicRateAnonThrottle):
    """Limiter for public unauthenticated endpoints."""

    scope = "public"
