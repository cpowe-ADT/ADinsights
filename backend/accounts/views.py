from __future__ import annotations

from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .audit import log_audit_event
from .models import AuditLog, Tenant, User, UserRole
from .permissions import IsTenantAdmin
from .serializers import (
    AuditLogSerializer,
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    TenantSerializer,
    TenantSignupSerializer,
    TenantTokenObtainPairSerializer,
    UserCreateSerializer,
    UserRoleSerializer,
    UserSerializer,
)


class TenantTokenObtainPairView(TokenObtainPairView):
    serializer_class = TenantTokenObtainPairSerializer


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


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
