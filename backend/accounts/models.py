from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from .tenant_context import get_current_tenant_id


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover - repr helper
        return self.name


class TenantAwareManager(models.Manager):
    def get_queryset(self):  # type: ignore[override]
        qs = super().get_queryset()
        tenant_id = get_current_tenant_id()
        if tenant_id and "tenant_id" in [
            field.attname for field in self.model._meta.fields
        ]:
            qs = qs.filter(tenant_id=tenant_id)
        return qs


class Role(models.Model):
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"
    ROLE_CHOICES = [
        (ADMIN, "Admin"),
        (ANALYST, "Analyst"),
        (VIEWER, "Viewer"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=32, choices=ROLE_CHOICES, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover
        return self.name


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="users")
    timezone = models.CharField(max_length=64, default="America/Jamaica")

    REQUIRED_FIELDS = ["email", "tenant"]

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = str(self.id)
        super().save(*args, **kwargs)

    def has_role(self, role_name: str) -> bool:
        return self.user_roles.filter(role__name=role_name).exists()


class UserRole(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_roles")
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="tenant_roles"
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "tenant", "role")


def default_invitation_expiry():
    return timezone.now() + timedelta(days=7)


def generate_invitation_token() -> str:
    return secrets.token_urlsafe(32)


class Invitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="invitations"
    )
    email = models.EmailField()
    token = models.CharField(
        max_length=128, unique=True, default=generate_invitation_token
    )
    role = models.ForeignKey(Role, null=True, blank=True, on_delete=models.SET_NULL)
    invited_by = models.ForeignKey(
        "User", null=True, blank=True, on_delete=models.SET_NULL, related_name="sent_invitations"
    )
    expires_at = models.DateTimeField(default=default_invitation_expiry)
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "email"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - repr helper
        return f"Invitation<{self.email}>"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def mark_accepted(self) -> None:
        self.accepted_at = timezone.now()
        self.save(update_fields=["accepted_at"])


class ServiceAccountKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="service_account_keys"
    )
    name = models.CharField(max_length=128)
    role = models.ForeignKey(Role, null=True, blank=True, on_delete=models.SET_NULL)
    prefix = models.CharField(max_length=12, unique=True)
    secret_hash = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"ServiceAccountKey<{self.tenant_id}:{self.name}>"

    @classmethod
    def _generate_prefix(cls) -> str:
        while True:
            prefix = secrets.token_hex(4)
            if not cls.all_objects.filter(prefix=prefix).exists():
                return prefix

    @classmethod
    def create_key(
        cls,
        *,
        tenant: Tenant,
        name: str,
        role: Role | None = None,
    ) -> tuple["ServiceAccountKey", str]:
        secret = secrets.token_urlsafe(32)
        prefix = cls._generate_prefix()
        secret_hash = cls._hash_secret(secret)
        instance = cls.all_objects.create(
            tenant=tenant,
            name=name,
            role=role,
            prefix=prefix,
            secret_hash=secret_hash,
        )
        token = f"sa_{prefix}.{secret}"
        return instance, token

    @staticmethod
    def _hash_secret(secret: str) -> str:
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()

    def verify(self, secret: str) -> bool:
        candidate = self._hash_secret(secret)
        return hmac.compare_digest(self.secret_hash, candidate)

    def mark_used(self) -> None:
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at"])

    def has_role(self, role_name: str) -> bool:
        if not self.role:
            return False
        return self.role.name == role_name


class PasswordResetToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="password_reset_tokens"
    )
    token_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "expires_at"]),
        ]

    @staticmethod
    def _hash_token(raw_value: str) -> str:
        return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()

    @classmethod
    def issue(
        cls,
        *,
        user: User,
        ttl: timedelta | None = None,
    ) -> tuple["PasswordResetToken", str]:
        """Create a new password reset token for the user.

        Any existing active tokens are expired to prevent parallel reuse. The
        helper returns both the stored instance and the raw token value so it can
        be delivered out of band (e.g. via email).
        """

        expires_at = timezone.now() + (ttl or timedelta(hours=1))
        cls.objects.filter(
            user=user,
            used_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).update(expires_at=timezone.now())

        raw_token = secrets.token_urlsafe(32)
        token_hash = cls._hash_token(raw_token)

        instance = cls.objects.create(
            user=user,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        return instance, raw_token

    def mark_used(self) -> None:
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])

    def is_valid(self, raw_token: str) -> bool:
        if self.used_at is not None:
            return False
        if timezone.now() >= self.expires_at:
            return False
        candidate = self._hash_token(raw_token)
        return hmac.compare_digest(self.token_hash, candidate)


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="audit_logs"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    action = models.CharField(max_length=128)
    resource_type = models.CharField(max_length=64)
    resource_id = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()


class TenantKey(models.Model):
    tenant = models.OneToOneField(
        Tenant, on_delete=models.CASCADE, related_name="tenant_key"
    )
    dek_ciphertext = models.BinaryField()
    dek_key_version = models.CharField(max_length=128)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    def touch(self) -> None:
        self.updated_at = timezone.now()
        super().save(update_fields=["updated_at"])


def get_or_create_role(name: str) -> Role:
    role, _ = Role.objects.get_or_create(name=name)
    return role


def seed_default_roles() -> None:
    for role_name, _label in Role.ROLE_CHOICES:
        Role.objects.get_or_create(name=role_name)


def assign_role(user: User, role_name: str):
    role = get_or_create_role(role_name)
    return UserRole.objects.get_or_create(user=user, tenant=user.tenant, role=role)[0]
