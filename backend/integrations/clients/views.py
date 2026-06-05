"""REST API for Client grouping (Sprint 3).

Endpoints:

* ``GET  /api/clients/``                         — list clients (lightweight)
* ``POST /api/clients/``                         — create client
* ``GET  /api/clients/<uuid:id>/``               — retrieve (with accounts)
* ``PATCH /api/clients/<uuid:id>/``              — update client fields
* ``DELETE /api/clients/<uuid:id>/``             — delete client (cascades links)
* ``GET  /api/clients/<uuid:id>/accounts/``      — list linked platform accounts
* ``POST /api/clients/<uuid:id>/accounts/``      — attach an account (409 if claimed)
* ``DELETE /api/clients/<uuid:id>/accounts/<uuid:account_id>/`` — detach
* ``GET  /api/clients/suggest/``                 — name-match suggestions
* ``POST /api/clients/suggest/apply/``           — apply one suggestion atomically
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from django.utils import timezone

from integrations.clients.resolver import resolve_client_for_external
from integrations.clients.serializers import (
    ClientCreateSerializer,
    ClientListSerializer,
    ClientPlatformAccountAttachSerializer,
    ClientPlatformAccountSerializer,
    ClientSerializer,
    ClientSuggestionSerializer,
    ClientSuggestionSnapshotSerializer,
    SuggestionApplySerializer,
)
from integrations.clients.suggester import suggest_clients
from integrations.clients.tasks import (
    DEFAULT_SUGGESTION_THRESHOLD,
    enqueue_refresh_client_suggestions,
)
from integrations.models import Client, ClientPlatformAccount, ClientSuggestionSnapshot

logger = logging.getLogger(__name__)


def _tenant_id(request) -> str:
    return str(request.user.tenant_id)


def _get_client_for_tenant(request, client_id: str) -> Client:
    return get_object_or_404(
        Client.all_objects, id=client_id, tenant_id=_tenant_id(request)
    )


class ClientListCreateView(APIView):
    """``GET`` and ``POST /api/clients/``."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = (
            Client.all_objects.filter(tenant_id=_tenant_id(request))
            .prefetch_related("platform_accounts")
            .order_by("name")
        )
        serializer = ClientListSerializer(qs, many=True)
        return Response({"results": serializer.data})

    def post(self, request):
        serializer = ClientCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            client = Client.all_objects.create(
                tenant_id=_tenant_id(request),
                **serializer.validated_data,
            )
        except IntegrityError as exc:
            logger.warning("clients.create.integrity_error", exc_info=exc)
            return Response(
                {"detail": "A client with this slug already exists for your tenant."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            ClientSerializer(client).data, status=status.HTTP_201_CREATED
        )


class ClientDetailView(APIView):
    """``GET``/``PATCH``/``DELETE /api/clients/<id>/``."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, client_id: str):
        client = _get_client_for_tenant(request, client_id)
        return Response(ClientSerializer(client).data)

    def patch(self, request, client_id: str):
        client = _get_client_for_tenant(request, client_id)
        serializer = ClientSerializer(client, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, client_id: str):
        client = _get_client_for_tenant(request, client_id)
        client.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ClientAccountsView(APIView):
    """``GET`` and ``POST /api/clients/<id>/accounts/``."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, client_id: str):
        client = _get_client_for_tenant(request, client_id)
        qs = client.platform_accounts.all().order_by("platform", "external_id")
        return Response(
            {"results": ClientPlatformAccountSerializer(qs, many=True).data}
        )

    def post(self, request, client_id: str):
        client = _get_client_for_tenant(request, client_id)
        serializer = ClientPlatformAccountAttachSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        tenant_id = _tenant_id(request)

        existing = resolve_client_for_external(
            tenant_id, data["platform"], data["external_id"]
        )
        if existing is not None:
            return Response(
                {
                    "detail": "This account is already linked to another client.",
                    "claimed_by": {
                        "client_id": str(existing.id),
                        "client_name": existing.name,
                    },
                },
                status=status.HTTP_409_CONFLICT,
            )

        try:
            link = ClientPlatformAccount.all_objects.create(
                tenant_id=tenant_id,
                client=client,
                platform=data["platform"],
                external_id=data["external_id"],
                display_name=data.get("display_name", ""),
                is_primary=data.get("is_primary", False),
            )
        except IntegrityError as exc:
            logger.warning("clients.attach_account.integrity_error", exc_info=exc)
            return Response(
                {"detail": "Failed to attach account."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            ClientPlatformAccountSerializer(link).data,
            status=status.HTTP_201_CREATED,
        )


class ClientAccountDetachView(APIView):
    """``DELETE /api/clients/<id>/accounts/<account_id>/``."""

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, client_id: str, account_id: str):
        client = _get_client_for_tenant(request, client_id)
        link = get_object_or_404(
            ClientPlatformAccount.all_objects,
            id=account_id,
            tenant_id=_tenant_id(request),
            client=client,
        )
        link.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ClientSuggestView(APIView):
    """``GET /api/clients/suggest/``."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        threshold_raw = request.query_params.get("threshold")
        try:
            threshold = (
                float(threshold_raw) if threshold_raw is not None else 0.7
            )
        except ValueError:
            return Response(
                {"detail": "threshold must be a number between 0 and 1."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not (0.0 <= threshold <= 1.0):
            return Response(
                {"detail": "threshold must be between 0 and 1."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = suggest_clients(_tenant_id(request), threshold=threshold)
        return Response(
            {
                "threshold": threshold,
                "results": ClientSuggestionSerializer(results, many=True).data,
            }
        )


class ClientSuggestApplyView(APIView):
    """``POST /api/clients/suggest/apply/`` — atomic create-or-attach."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = SuggestionApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        tenant_id = _tenant_id(request)

        # Pre-flight: reject if any account is already claimed by another client.
        for acct in data["accounts"]:
            existing = resolve_client_for_external(
                tenant_id, acct["platform"], acct["external_id"]
            )
            if existing is not None:
                target_id = data.get("client_id")
                if target_id is None or str(existing.id) != str(target_id):
                    return Response(
                        {
                            "detail": (
                                f"{acct['platform']}:{acct['external_id']} is already "
                                "linked to another client."
                            ),
                            "claimed_by": {
                                "client_id": str(existing.id),
                                "client_name": existing.name,
                            },
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

        with transaction.atomic():
            if data.get("client_id"):
                client = get_object_or_404(
                    Client.all_objects, id=data["client_id"], tenant_id=tenant_id
                )
            else:
                from django.utils.text import slugify as _slugify

                slug = _slugify(data["create_name"])
                if not slug:
                    return Response(
                        {"detail": "Unable to derive a slug from create_name."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                try:
                    client = Client.all_objects.create(
                        tenant_id=tenant_id,
                        name=data["create_name"],
                        slug=slug,
                    )
                except IntegrityError:
                    return Response(
                        {
                            "detail": (
                                "A client with this slug already exists — "
                                "pass client_id instead of create_name."
                            )
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

            created_links: list[dict[str, Any]] = []
            for acct in data["accounts"]:
                # Idempotent within-scope: if this account already links to
                # THIS client (from the pre-flight allowance), skip silently.
                link, _ = ClientPlatformAccount.all_objects.get_or_create(
                    tenant_id=tenant_id,
                    platform=acct["platform"],
                    external_id=acct["external_id"],
                    defaults={
                        "client": client,
                        "display_name": acct.get("display_name", ""),
                        "is_primary": acct.get("is_primary", False),
                    },
                )
                if link.client_id != client.id:
                    # Defensive — pre-flight should have blocked this path.
                    raise IntegrityError("Cross-client reassignment attempted.")
                created_links.append(ClientPlatformAccountSerializer(link).data)

        return Response(
            {
                "client": ClientSerializer(client).data,
                "attached_accounts": created_links,
            },
            status=status.HTTP_201_CREATED,
        )


class ClientSuggestionSnapshotView(APIView):
    """``GET  /api/clients/suggestions/latest/`` — read cached snapshot.

    ``POST /api/clients/suggestions/latest/refresh/`` — enqueue a refresh.
    ``POST /api/clients/suggestions/latest/acknowledge/`` — mark as seen.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        tenant_id = _tenant_id(request)
        snapshot = ClientSuggestionSnapshot.all_objects.filter(
            tenant_id=tenant_id
        ).first()
        if snapshot is None:
            return Response({"snapshot": None})
        return Response(
            {"snapshot": ClientSuggestionSnapshotSerializer(snapshot).data}
        )


class ClientSuggestionSnapshotRefreshView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        tenant_id = _tenant_id(request)
        threshold_raw = request.data.get("threshold") if hasattr(request, "data") else None
        threshold = DEFAULT_SUGGESTION_THRESHOLD
        if threshold_raw is not None:
            try:
                threshold = float(threshold_raw)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "threshold must be a number between 0 and 1."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not (0.0 <= threshold <= 1.0):
                return Response(
                    {"detail": "threshold must be between 0 and 1."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        enqueue_refresh_client_suggestions(
            tenant_id,
            trigger_reason=ClientSuggestionSnapshot.REASON_MANUAL,
        )
        return Response({"status": "enqueued", "threshold": threshold}, status=status.HTTP_202_ACCEPTED)


class ClientSuggestionSnapshotAcknowledgeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        tenant_id = _tenant_id(request)
        snapshot = ClientSuggestionSnapshot.all_objects.filter(
            tenant_id=tenant_id
        ).first()
        if snapshot is None:
            return Response(
                {"detail": "No snapshot to acknowledge."},
                status=status.HTTP_404_NOT_FOUND,
            )
        snapshot.acknowledged_at = timezone.now()
        snapshot.save(update_fields=["acknowledged_at", "updated_at"])
        return Response(
            {"snapshot": ClientSuggestionSnapshotSerializer(snapshot).data}
        )
