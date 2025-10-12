from __future__ import annotations

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Tenant, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "tenant", "timezone"]
        read_only_fields = fields


class TenantTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["tenant_id"] = str(user.tenant_id)
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["tenant_id"] = str(self.user.tenant_id)
        data["user"] = UserSerializer(self.user).data
        return data


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "name", "created_at"]
        read_only_fields = fields
