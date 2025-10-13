from __future__ import annotations

from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Tenant, User, UserRole
from .permissions import IsTenantAdmin
from .serializers import (
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
        return TenantSerializer

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
