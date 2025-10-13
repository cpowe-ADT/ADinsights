"""HTTP endpoints that expose API health and version metadata."""

from __future__ import annotations

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request):
    """Return a simple liveness signal for load balancers and uptime checks."""
    return JsonResponse({"status": "ok"})


@require_GET
def version(request):
    """Report the deployed API version for debugging and release tracking."""
    api_version = getattr(settings, "API_VERSION", "unknown")
    return JsonResponse({"version": api_version})
