"""Authentication backend for service account API keys."""

from __future__ import annotations

from dataclasses import dataclass

from django.utils import timezone
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed

from accounts.models import ServiceAccountKey


@dataclass
class ServiceAccountPrincipal:
    key: ServiceAccountKey

    @property
    def id(self):  # pragma: no cover - simple proxy
        return self.key.id

    @property
    def tenant(self):  # pragma: no cover
        return self.key.tenant

    @property
    def tenant_id(self):  # pragma: no cover
        return self.key.tenant_id

    @property
    def is_authenticated(self) -> bool:  # noqa: D401
        """Service accounts are treated as authenticated principals."""

        return True

    @property
    def is_service_account(self) -> bool:  # pragma: no cover
        return True

    @property
    def email(self) -> str:  # pragma: no cover - to satisfy serializers
        return f"service-account:{self.key.id}"

    def has_role(self, role_name: str) -> bool:
        if not self.key.role:
            return False
        return self.key.role.name == role_name


class ServiceAccountAuthentication(authentication.BaseAuthentication):
    keyword = b"apikey"

    def authenticate(self, request):  # noqa: D401
        """Authenticate requests carrying an API key header."""

        auth = authentication.get_authorization_header(request).split()
        token = None
        if auth and auth[0].lower() == self.keyword:
            if len(auth) != 2:
                raise AuthenticationFailed("Invalid API key header")
            token = auth[1].decode("utf-8")
        elif "HTTP_X_API_KEY" in request.META:
            token = request.META["HTTP_X_API_KEY"]

        if not token:
            return None

        key = self._lookup_key(token)
        if not key.is_active:
            raise AuthenticationFailed("API key is inactive")

        key.last_used_at = timezone.now()
        key.save(update_fields=["last_used_at"])

        return ServiceAccountPrincipal(key), None

    def _lookup_key(self, token: str) -> ServiceAccountKey:
        if "." not in token:
            raise AuthenticationFailed("Malformed API key")
        prefix_part, secret = token.split(".", 1)
        if prefix_part.startswith("sa_"):
            prefix = prefix_part[3:]
        else:
            prefix = prefix_part
        try:
            key = ServiceAccountKey.all_objects.get(prefix=prefix)
        except ServiceAccountKey.DoesNotExist as exc:  # pragma: no cover - defensive
            raise AuthenticationFailed("Invalid API key") from exc
        if not key.verify(secret):
            raise AuthenticationFailed("Invalid API key")
        return key
