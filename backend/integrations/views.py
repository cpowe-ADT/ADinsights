from __future__ import annotations

from rest_framework import permissions, viewsets

from .models import PlatformCredential
from .serializers import PlatformCredentialSerializer


class PlatformCredentialViewSet(viewsets.ModelViewSet):
    serializer_class = PlatformCredentialSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PlatformCredential.objects.all()
