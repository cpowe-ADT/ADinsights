from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts.views import MeView, TenantTokenObtainPairView
from integrations.views import PlatformCredentialViewSet
from . import views as core_views

router = DefaultRouter()
router.register(
    r"platform-credentials",
    PlatformCredentialViewSet,
    basename="platformcredential",
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "api/auth/login/", TenantTokenObtainPairView.as_view(), name="token_obtain_pair"
    ),
    path("api/me/", MeView.as_view(), name="me"),
    path("api/health/", core_views.health, name="health"),
    path("api/timezone/", core_views.timezone_view, name="timezone"),
    path("api/", include(router.urls)),
]
