from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.dev_admin import resolve_default_tenant
from accounts.models import Role, User, assign_role, seed_default_roles
from analytics.models import (
    Ad,
    AdSet,
    Campaign,
    RawPerformanceRecord,
    TenantMetricsSnapshot,
)


def _dev_seed_allowed() -> bool:
    allowed = str(os.environ.get("ALLOW_DEFAULT_ADMIN", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }
    return settings.DEBUG or allowed


def _ensure_admin_user(tenant) -> tuple[User, bool]:
    username = os.environ.get("DJANGO_DEFAULT_ADMIN_USERNAME", "admin").strip() or "admin"
    email = os.environ.get("DJANGO_DEFAULT_ADMIN_EMAIL", "admin@example.com").strip() or "admin@example.com"
    password = os.environ.get("DJANGO_DEFAULT_ADMIN_PASSWORD", "admin1")

    user = User.objects.filter(username=username).first()
    created = False
    if user is None:
        user = User(
            username=username,
            tenant=tenant,
            email=email,
            first_name="Dev",
            last_name="Admin",
        )
        created = True
    else:
        if not user.tenant_id or user.tenant_id != tenant.id:
            user.tenant = tenant
        if email:
            user.email = email

    user.set_password(password)
    user.is_staff = True
    user.is_superuser = True
    user.save()

    assign_role(user, Role.ADMIN)
    return user, created


def _reset_tenant_analytics(tenant) -> None:
    RawPerformanceRecord.objects.filter(tenant=tenant).delete()
    Ad.objects.filter(tenant=tenant).delete()
    AdSet.objects.filter(tenant=tenant).delete()
    Campaign.objects.filter(tenant=tenant).delete()
    TenantMetricsSnapshot.objects.filter(tenant=tenant, source="warehouse").delete()


class Command(BaseCommand):
    help = "Seed local development data (tenant, admin user, and demo analytics payloads)."

    def add_arguments(self, parser):  # noqa: ANN001
        parser.add_argument(
            "--fixture",
            help="Override the default fixture path for dev seed data.",
        )
        parser.add_argument(
            "--skip-fixture",
            action="store_true",
            help="Skip loading the JSON fixture and only ensure the admin user exists.",
        )
        parser.add_argument(
            "--no-refresh-snapshot",
            action="store_true",
            help="Do not refresh the snapshot timestamp after loading.",
        )

    def handle(self, *args: Any, **options: Any) -> None:  # noqa: ANN001
        if not _dev_seed_allowed():
            self.stdout.write(
                self.style.WARNING(
                    "Refusing to seed dev data outside DEBUG. Set ALLOW_DEFAULT_ADMIN=1 to override."
                )
            )
            return

        seed_default_roles()
        tenant = resolve_default_tenant()
        user, created = _ensure_admin_user(tenant)

        fixture_override = options.get("fixture")
        default_fixture = Path(settings.BASE_DIR) / "fixtures" / "dev_seed.json"
        fixture_path = Path(fixture_override) if fixture_override else default_fixture

        if not options.get("skip_fixture"):
            if not fixture_path.exists():
                self.stdout.write(self.style.ERROR(f"Fixture not found: {fixture_path}"))
                return
            _reset_tenant_analytics(tenant)
            call_command("loaddata", str(fixture_path), verbosity=0)

        if not options.get("no_refresh_snapshot"):
            snapshot = (
                TenantMetricsSnapshot.objects.filter(tenant=tenant, source="warehouse")
                .order_by("-generated_at", "-created_at")
                .first()
            )
            if snapshot:
                now = timezone.now()
                payload = dict(snapshot.payload or {})
                payload["snapshot_generated_at"] = now.isoformat()
                snapshot.payload = payload
                snapshot.generated_at = now
                snapshot.save(update_fields=["payload", "generated_at", "updated_at"])
            else:
                self.stdout.write(
                    self.style.WARNING("No warehouse snapshot found to refresh.")
                )

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} admin user {user.username} for tenant {tenant.name}."
            )
        )
        if not options.get("skip_fixture"):
            self.stdout.write(self.style.SUCCESS(f"Loaded fixture {fixture_path}."))
