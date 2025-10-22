from __future__ import annotations

from django.conf import settings
from django.db import connection
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .audit import log_audit_event
from .models import AuditLog, ServiceAccountKey, Tenant, User, UserRole
from .permissions import IsTenantAdmin
from .serializers import (
    AuditLogSerializer,
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    TenantSerializer,
    TenantSwitchSerializer,
    TenantSignupSerializer,
    TenantTokenObtainPairSerializer,
    UserCreateSerializer,
    UserRoleSerializer,
    UserSerializer,
    ServiceAccountKeySerializer,
)
from .tasks import send_password_reset_email
from .tenant_context import set_current_tenant_id


class TenantTokenObtainPairView(TokenObtainPairView):
    serializer_class = TenantTokenObtainPairSerializer


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.save()
        raw_token = serializer.context["raw_token"]
        user = serializer.context["user"]

        send_password_reset_email.delay(str(token.id), raw_token)

        log_audit_event(
            tenant=user.tenant,
            user=user,
            action="password_reset_requested",
            resource_type="user",
            resource_id=user.id,
        )

        return Response(status=status.HTTP_202_ACCEPTED)


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        log_audit_event(
            tenant=user.tenant,
            user=user,
            action="password_reset_completed",
            resource_type="user",
            resource_id=user.id,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class TenantSwitchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = TenantSwitchSerializer(
            data=request.data, context={"request": request, "user": request.user}
        )
        serializer.is_valid(raise_exception=True)
        tenant = serializer.save()
        tenant_id = str(tenant.id)

        set_current_tenant_id(tenant_id)
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SET app.tenant_id = %s", [tenant_id])
        else:
            setattr(connection, settings.TENANT_SETTING_KEY, tenant_id)

        log_audit_event(
            tenant=tenant,
            user=request.user,
            action="tenant_switched",
            resource_type="tenant",
            resource_id=tenant_id,
        )

        return Response({"tenant_id": tenant_id}, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user_data = UserSerializer(request.user).data
        tenant_id = getattr(request, "tenant_id", None)
        if tenant_id is None:
            tenant_id = getattr(request.user, "tenant_id", None)
            if tenant_id is not None:
                tenant_id = str(tenant_id)
        return Response({"user": user_data, "tenant_id": tenant_id})


class TenantViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Tenant.objects.all().order_by("created_at")
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):  # noqa: D401 - DRF API
        """Allow unauthenticated access for tenant creation."""

        if self.action == "create":
            return [permissions.AllowAny()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "create":
            return TenantSignupSerializer
        if self.action == "invite":
            return InvitationCreateSerializer
        return TenantSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action == "invite":
            if "tenant" not in context and self.kwargs.get(self.lookup_field):
                context["tenant"] = self.get_object()
            user = getattr(self.request, "user", None)
            if user and user.is_authenticated:
                context.setdefault("invited_by", user)
        return context

    def get_queryset(self):  # type: ignore[override]
        user = self.request.user
        if getattr(user, "is_superuser", False):
            return super().get_queryset()
        if user and user.is_authenticated:
            return Tenant.objects.filter(id=user.tenant_id)
        return Tenant.objects.none()

    def create(self, request, *args, **kwargs):  # noqa: D401 - DRF API
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        tenant = result["tenant"]
        admin_user = result["user"]
        output = TenantSerializer(tenant, context=self.get_serializer_context()).data
        output["admin_user_id"] = str(admin_user.id)
        headers = self.get_success_headers(output)
        return Response(output, status=status.HTTP_201_CREATED, headers=headers)

    @action(
        detail=True,
        methods=["post"],
        url_path="invite",
        permission_classes=[permissions.IsAuthenticated, IsTenantAdmin],
    )
    def invite(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation = serializer.save()
        response_serializer = InvitationCreateSerializer(invitation)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class UserViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = (
        User.objects.select_related("tenant")
        .prefetch_related("user_roles__role")
        .order_by("email")
    )
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):  # noqa: D401 - DRF API
        """RBAC enforcement for mutating operations."""

        if self.action in {"create", "invite"}:
            return [permissions.IsAuthenticated(), IsTenantAdmin()]
        if self.action == "accept_invite":
            return [permissions.AllowAny()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action == "invite":
            return InvitationCreateSerializer
        if self.action == "accept_invite":
            return InvitationAcceptSerializer
        return UserSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        user = self.request.user
        if user and user.is_authenticated:
            context.setdefault("tenant", getattr(user, "tenant", None))
            context.setdefault("invited_by", user)
        return context

    def get_queryset(self):  # type: ignore[override]
        user = self.request.user
        if getattr(user, "is_superuser", False):
            return super().get_queryset()
        if user and user.is_authenticated:
            return self.queryset.filter(tenant_id=user.tenant_id)
        return User.objects.none()

    @action(detail=False, methods=["post"], url_path="invite")
    def invite(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation = serializer.save()
        response_serializer = InvitationCreateSerializer(invitation)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="accept-invite")
    def accept_invite(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        response_serializer = UserSerializer(user)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class UserRoleViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = UserRole.objects.select_related("user", "tenant", "role").order_by(
        "created_at"
    )
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserRoleSerializer

    def get_permissions(self):  # noqa: D401 - DRF API
        """Admins manage assignments; all users may list."""

        if self.action in {"create", "destroy"}:
            return [permissions.IsAuthenticated(), IsTenantAdmin()]
        return super().get_permissions()

    def get_queryset(self):  # type: ignore[override]
        user = self.request.user
        if getattr(user, "is_superuser", False):
            return super().get_queryset()
        if user and user.is_authenticated:
            return self.queryset.filter(tenant_id=user.tenant_id)
        return UserRole.objects.none()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        user = self.request.user
        if user and user.is_authenticated:
            context.setdefault("tenant", getattr(user, "tenant", None))
        return context

    def perform_create(self, serializer):
        user_role = serializer.save()
        actor = self.request.user if self.request.user.is_authenticated else None
        log_audit_event(
            tenant=user_role.tenant,
            user=actor,
            action="role_assigned",
            resource_type="role",
            resource_id=user_role.user_id,
            metadata={
                "role": user_role.role.name,
            },
        )

    def perform_destroy(self, instance):
        tenant = instance.tenant
        user_id = instance.user_id
        role_name = instance.role.name
        actor = self.request.user if self.request.user.is_authenticated else None
        super().perform_destroy(instance)
        log_audit_event(
            tenant=tenant,
            user=actor,
            action="role_revoked",
            resource_type="role",
            resource_id=user_id,
            metadata={"role": role_name},
        )


class ServiceAccountKeyViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ServiceAccountKeySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):  # noqa: D401
        """Restrict mutating operations to tenant admins."""

        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [permissions.IsAuthenticated(), IsTenantAdmin()]
        return super().get_permissions()

    def get_queryset(self):  # type: ignore[override]
        user = self.request.user
        if not user or not getattr(user, "is_authenticated", False):
            return ServiceAccountKey.objects.none()
        return ServiceAccountKey.objects.filter(tenant_id=user.tenant_id).order_by("-created_at")

    def get_serializer_context(self):  # type: ignore[override]
        context = super().get_serializer_context()
        user = self.request.user
        tenant = getattr(user, "tenant", None)
        if tenant is not None:
            context.setdefault("tenant", tenant)
        return context

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class RoleAssignmentView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]

    def post(self, request):
        serializer = UserRoleSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        user_role = serializer.save()

        log_audit_event(
            tenant=user_role.tenant,
            user=request.user,
            action="role_assigned",
            resource_type="role",
            resource_id=user_role.user_id,
            metadata={"role": user_role.role.name},
        )

        response_serializer = UserRoleSerializer(
            user_role, context={"request": request}
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class AuditLogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return AuditLog.objects.none()
        queryset = AuditLog.objects.filter(tenant_id=user.tenant_id).order_by(
            "-created_at"
        )
        action = self.request.query_params.get("action")
        if action:
            queryset = queryset.filter(action=action)
        resource_type = self.request.query_params.get("resource_type")
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)
        return queryset
