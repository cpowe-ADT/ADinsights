from __future__ import annotations

from django.conf import settings
from django.http import JsonResponse


def health(request):
    return JsonResponse({"status": "ok"})


def timezone_view(request):
    return JsonResponse({"timezone": settings.TIME_ZONE})
