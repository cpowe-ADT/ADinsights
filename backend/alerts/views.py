from __future__ import annotations

from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import AlertRun
from .serializers import AlertRunSerializer


class AlertRunViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = AlertRunSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = AlertRun.objects.all()
        rule = self.request.query_params.get("rule")
        status_param = self.request.query_params.get("status")
        if rule:
            queryset = queryset.filter(rule_slug=rule)
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset
