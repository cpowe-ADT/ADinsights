from __future__ import annotations

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
