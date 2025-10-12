from __future__ import annotations

from rest_framework import serializers

from accounts.models import Tenant
from .models import PlatformCredential


class PlatformCredentialSerializer(serializers.ModelSerializer):
    access_token = serializers.CharField(write_only=True, required=True)
    refresh_token = serializers.CharField(
        write_only=True, required=False, allow_null=True, allow_blank=True
        write_only=False, required=False, allow_null=True, allow_blank=True
    )

    class Meta:
        model = PlatformCredential
        fields = [
            "id",
            "provider",
            "account_id",
            "expires_at",
            "created_at",
            "updated_at",
            "access_token",
            "refresh_token",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data):
        access_token = validated_data.pop("access_token")
        refresh_token = validated_data.pop("refresh_token", None)
        tenant: Tenant = self.context["request"].user.tenant
        credential = PlatformCredential(tenant=tenant, **validated_data)
        credential.set_raw_tokens(access_token, refresh_token)
        credential.save()
        return credential

    def update(self, instance, validated_data):
        access_token = validated_data.pop("access_token", None)
        refresh_token = validated_data.pop("refresh_token", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.set_raw_tokens(access_token, refresh_token)
        instance.save()
        return instance

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep.pop("access_token", None)
        rep.pop("refresh_token", None)
        return rep
