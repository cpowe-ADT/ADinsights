"""Serializers for the Client grouping REST API (Sprint 3)."""

from __future__ import annotations

from django.utils.text import slugify
from rest_framework import serializers

from integrations.models import Client, ClientPlatformAccount, ClientSuggestionSnapshot


class ClientPlatformAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientPlatformAccount
        fields = (
            "id",
            "platform",
            "external_id",
            "display_name",
            "is_primary",
            "metadata",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class ClientPlatformAccountAttachSerializer(serializers.Serializer):
    """Input for POST /api/clients/<id>/accounts/."""

    platform = serializers.ChoiceField(choices=ClientPlatformAccount.PLATFORM_CHOICES)
    external_id = serializers.CharField(max_length=128)
    display_name = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )
    is_primary = serializers.BooleanField(required=False, default=False)


class ClientSerializer(serializers.ModelSerializer):
    """Detail + update payload."""

    platform_counts = serializers.SerializerMethodField()
    platform_accounts = ClientPlatformAccountSerializer(many=True, read_only=True)

    class Meta:
        model = Client
        fields = (
            "id",
            "name",
            "slug",
            "industry",
            "parish",
            "notes",
            "is_active",
            "metadata",
            "platform_counts",
            "platform_accounts",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "slug", "platform_counts", "created_at", "updated_at")

    def get_platform_counts(self, obj: Client) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in obj.platform_accounts.values("platform"):
            counts[row["platform"]] = counts.get(row["platform"], 0) + 1
        return counts


class ClientCreateSerializer(serializers.ModelSerializer):
    """Input for POST /api/clients/. Slug is auto-derived from name if omitted."""

    class Meta:
        model = Client
        fields = ("name", "slug", "industry", "parish", "notes", "metadata")
        extra_kwargs = {
            "slug": {"required": False, "allow_blank": True},
            "industry": {"required": False, "allow_blank": True},
            "parish": {"required": False, "allow_blank": True},
            "notes": {"required": False, "allow_blank": True},
            "metadata": {"required": False},
        }

    def validate(self, attrs):
        slug = (attrs.get("slug") or "").strip()
        if not slug:
            slug = slugify(attrs.get("name") or "")
        if not slug:
            raise serializers.ValidationError(
                {"slug": "Unable to derive a slug from the given name."}
            )
        attrs["slug"] = slug
        return attrs


class ClientListSerializer(serializers.ModelSerializer):
    """Lightweight list payload — no nested accounts."""

    platform_counts = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = (
            "id",
            "name",
            "slug",
            "industry",
            "parish",
            "is_active",
            "platform_counts",
            "updated_at",
        )

    def get_platform_counts(self, obj: Client) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in obj.platform_accounts.values("platform"):
            counts[row["platform"]] = counts.get(row["platform"], 0) + 1
        return counts


class SuggestionAccountSerializer(serializers.Serializer):
    platform = serializers.CharField()
    external_id = serializers.CharField()
    display_name = serializers.CharField(allow_blank=True)


class ClientSuggestionSerializer(serializers.Serializer):
    proposed_name = serializers.CharField()
    normalized_name = serializers.CharField()
    unclaimed_accounts = SuggestionAccountSerializer(many=True)
    existing_client_id = serializers.CharField(allow_null=True)
    confidence = serializers.FloatField()


class SuggestionApplySerializer(serializers.Serializer):
    """Input for POST /api/clients/suggest/apply/.

    Either ``client_id`` (attach to existing) or ``create_name`` (create a new
    Client with this name) — exactly one is required. Accounts is the list of
    {platform, external_id} pairs to link atomically.
    """

    client_id = serializers.UUIDField(required=False)
    create_name = serializers.CharField(max_length=255, required=False)
    accounts = serializers.ListField(
        child=ClientPlatformAccountAttachSerializer(),
        allow_empty=False,
    )

    def validate(self, attrs):
        has_id = bool(attrs.get("client_id"))
        has_name = bool(attrs.get("create_name"))
        if has_id == has_name:
            raise serializers.ValidationError(
                "Provide exactly one of client_id or create_name."
            )
        return attrs


class ClientSuggestionSnapshotSerializer(serializers.ModelSerializer):
    """Read-only payload for the banner UI."""

    is_unacknowledged = serializers.BooleanField(read_only=True)

    class Meta:
        model = ClientSuggestionSnapshot
        fields = (
            "id",
            "trigger_reason",
            "threshold",
            "suggestion_count",
            "payload",
            "generated_at",
            "acknowledged_at",
            "is_unacknowledged",
        )
        read_only_fields = fields
