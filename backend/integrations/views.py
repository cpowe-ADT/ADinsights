from __future__ import annotations

from rest_framework import permissions, viewsets

from accounts.audit import log_audit_event
from .models import PlatformCredential
from .serializers import PlatformCredentialSerializer


class PlatformCredentialViewSet(viewsets.ModelViewSet):
    serializer_class = PlatformCredentialSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return PlatformCredential.objects.none()
        return PlatformCredential.objects.filter(tenant_id=user.tenant_id).order_by(
            "-created_at"
        )

    def perform_create(self, serializer):
        credential = serializer.save()
        actor = self.request.user if self.request.user.is_authenticated else None
        log_audit_event(
            tenant=credential.tenant,
            user=actor,
            action="credential_created",
            resource_type="platform_credential",
            resource_id=credential.id,
            metadata={
                "provider": credential.provider,
                "account_id": credential.account_id,
            },
        )

    def perform_update(self, serializer):
        credential = serializer.save()
        actor = self.request.user if self.request.user.is_authenticated else None
        log_audit_event(
            tenant=credential.tenant,
            user=actor,
            action="credential_updated",
            resource_type="platform_credential",
            resource_id=credential.id,
            metadata={
                "provider": credential.provider,
                "account_id": credential.account_id,
            },
        )

    def perform_destroy(self, instance):
        tenant = instance.tenant
        credential_id = instance.id
        provider = instance.provider
        account_id = instance.account_id
        actor = self.request.user if self.request.user.is_authenticated else None
        super().perform_destroy(instance)
        log_audit_event(
            tenant=tenant,
            user=actor,
            action="credential_deleted",
            resource_type="platform_credential",
            resource_id=credential_id,
            metadata={"provider": provider, "account_id": account_id},
        )
