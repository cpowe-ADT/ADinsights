from __future__ import annotations

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .audit import log_audit_event
from .hooks import send_invitation_email
from .models import AuditLog, Invitation, Role, Tenant, User, UserRole, assign_role


class RoleNameField(serializers.ChoiceField):
    def __init__(self, **kwargs):
        choices = [choice[0] for choice in Role.ROLE_CHOICES]
        super().__init__(choices=choices, **kwargs)

    def to_representation(self, value):  # type: ignore[override]
        if isinstance(value, Role):
            return value.name
        return super().to_representation(value)

    def to_internal_value(self, data):  # type: ignore[override]
        if data is None:
            if self.allow_null:
                return None
            raise serializers.ValidationError("This field may not be null.")

        role_name = super().to_internal_value(data)
        role, _ = Role.objects.get_or_create(name=role_name)
        return role


class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "tenant",
            "timezone",
            "roles",
        ]
        read_only_fields = fields

    def get_roles(self, obj: User) -> list[str]:
        return list(obj.user_roles.values_list("role__name", flat=True))


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
        log_audit_event(
            tenant=self.user.tenant,
            user=self.user,
            action="login",
            resource_type="auth",
            resource_id=self.user.id,
        )
        return data


class AuditLogSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "tenant",
            "user",
            "action",
            "resource_type",
            "resource_id",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields

    def get_user(self, obj: AuditLog):
        user = obj.user
        if user is None:
            return None
        return {
            "id": str(user.id),
            "email": user.email,
        }


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "name", "created_at"]
        read_only_fields = fields


class TenantSignupSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    admin_email = serializers.EmailField(write_only=True)
    admin_password = serializers.CharField(write_only=True, min_length=8)
    admin_first_name = serializers.CharField(
        max_length=150, write_only=True, required=False, allow_blank=True
    )
    admin_last_name = serializers.CharField(
        max_length=150, write_only=True, required=False, allow_blank=True
    )

    def create(self, validated_data):
        admin_email = validated_data.pop("admin_email")
        admin_password = validated_data.pop("admin_password")
        admin_first_name = validated_data.pop("admin_first_name", "")
        admin_last_name = validated_data.pop("admin_last_name", "")

        tenant = Tenant.objects.create(**validated_data)
        user = User.objects.create_user(
            username=admin_email,
            email=admin_email,
            tenant=tenant,
            first_name=admin_first_name,
            last_name=admin_last_name,
        )
        user.set_password(admin_password)
        user.save()

        assign_role(user, Role.ADMIN)

        return {"tenant": tenant, "user": user}

    def to_representation(self, instance):  # type: ignore[override]
        tenant = instance["tenant"] if isinstance(instance, dict) else instance
        user = instance.get("user") if isinstance(instance, dict) else None
        data = TenantSerializer(tenant, context=self.context).data
        if user:
            data["admin_user_id"] = str(user.id)
        return data


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "timezone",
            "password",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        tenant = self.context.get("tenant")
        if tenant is None:
            raise serializers.ValidationError("Tenant context is required.")

        password = validated_data.pop("password")
        user = User.objects.create_user(
            username=validated_data["email"],
            tenant=tenant,
            **validated_data,
        )
        user.set_password(password)
        user.save()
        return user


class InvitationSerializer(serializers.ModelSerializer):
    role = RoleNameField(allow_null=True, required=False)

    class Meta:
        model = Invitation
        fields = [
            "id",
            "email",
            "token",
            "role",
            "tenant",
            "invited_by",
            "expires_at",
            "accepted_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "token",
            "tenant",
            "invited_by",
            "expires_at",
            "accepted_at",
            "created_at",
        ]


class InvitationCreateSerializer(InvitationSerializer):
    class Meta(InvitationSerializer.Meta):
        fields = ["id", "email", "role", "token", "expires_at", "accepted_at"]
        read_only_fields = ["id", "token", "expires_at", "accepted_at"]

    def create(self, validated_data):
        tenant = self.context.get("tenant")
        invited_by = self.context.get("invited_by")
        if tenant is None:
            raise serializers.ValidationError("Tenant context is required.")

        invitation = Invitation.objects.create(
            tenant=tenant, invited_by=invited_by, **validated_data
        )
        send_invitation_email(invitation)
        return invitation


class InvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True
    )
    last_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True
    )

    def validate_token(self, value: str) -> str:
        try:
            invitation = Invitation.objects.get(token=value)
        except Invitation.DoesNotExist as exc:  # pragma: no cover - defensive branch
            raise serializers.ValidationError("Invalid invitation token.") from exc

        if invitation.accepted_at is not None:
            raise serializers.ValidationError("Invitation has already been accepted.")
        if invitation.is_expired:
            raise serializers.ValidationError("Invitation has expired.")

        self.context["invitation"] = invitation
        return value

    def create(self, validated_data):
        invitation: Invitation = self.context["invitation"]
        tenant = invitation.tenant

        if User.objects.filter(email=invitation.email, tenant=tenant).exists():
            raise serializers.ValidationError(
                "A user with this email already exists for the tenant."
            )

        password = validated_data.pop("password")
        first_name = validated_data.get("first_name", "")
        last_name = validated_data.get("last_name", "")

        user = User.objects.create_user(
            username=invitation.email,
            email=invitation.email,
            tenant=tenant,
            first_name=first_name,
            last_name=last_name,
        )
        user.set_password(password)
        user.save()

        if invitation.role:
            UserRole.objects.get_or_create(
                user=user, tenant=tenant, role=invitation.role
            )

        invitation.mark_accepted()
        return user

    def to_representation(self, instance):  # type: ignore[override]
        return UserSerializer(instance, context=self.context).data


class UserRoleSerializer(serializers.ModelSerializer):
    role = RoleNameField()
    tenant = serializers.PrimaryKeyRelatedField(
        queryset=Tenant.objects.all(), required=False
    )

    class Meta:
        model = UserRole
        fields = ["id", "user", "tenant", "role", "created_at"]
        read_only_fields = ["id", "created_at"]
        validators: list = []

    def validate(self, attrs):
        tenant = attrs.get("tenant") or self.context.get("tenant")
        if tenant is None:
            request = self.context.get("request")
            if request is not None and getattr(request.user, "is_authenticated", False):
                tenant = getattr(request.user, "tenant", None)
        if tenant is None:
            raise serializers.ValidationError("Tenant context is required.")

        user = attrs.get("user")
        if user and user.tenant_id != tenant.id:
            raise serializers.ValidationError(
                "The selected user does not belong to this tenant."
            )
        attrs["tenant"] = tenant
        return attrs

    def create(self, validated_data):
        tenant = validated_data["tenant"]
        user = validated_data["user"]
        role = validated_data["role"]
        user_role, _ = UserRole.objects.get_or_create(
            tenant=tenant, user=user, role=role
        )
        return user_role
