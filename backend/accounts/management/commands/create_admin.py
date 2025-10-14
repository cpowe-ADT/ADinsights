import os

from django.conf import settings
from django.core.management.base import BaseCommand

from accounts.models import Tenant, User, Role, assign_role

class Command(BaseCommand):
    help = (
        "Create or update a default admin user for local development. "
        "Uses environment variables DJANGO_DEFAULT_ADMIN_USERNAME, DJANGO_DEFAULT_ADMIN_EMAIL, "
        "and DJANGO_DEFAULT_ADMIN_PASSWORD with safe defaults."
    )

    def handle(self, *args, **kwargs):
        # Safety guard: only allow in DEBUG or when explicitly permitted
        allow_default = str(os.environ.get("ALLOW_DEFAULT_ADMIN", "")).strip().lower() in (
            "1",
            "true",
            "yes",
            "y",
            "on",
        )
        if not settings.DEBUG and not allow_default:
            self.stdout.write(
                self.style.WARNING(
                    "Refusing to create default admin outside DEBUG. Set ALLOW_DEFAULT_ADMIN=1 to override."
                )
            )
            return

        username = os.environ.get("DJANGO_DEFAULT_ADMIN_USERNAME", "admin").strip() or "admin"
        email = os.environ.get("DJANGO_DEFAULT_ADMIN_EMAIL", "admin@example.com").strip() or "admin@example.com"
        password = os.environ.get("DJANGO_DEFAULT_ADMIN_PASSWORD", "admin1")

        # Create default tenant
        tenant, _ = Tenant.objects.get_or_create(name="Default Tenant")

        # Create or update admin user
        user = User.objects.filter(username=username).first()
        created = False
        if user is None:
            user = User(username=username, tenant=tenant, email=email, first_name="Admin", last_name="User")
            created = True
        else:
            # Keep existing tenant association if present; otherwise, attach to default tenant
            if not user.tenant_id:
                user.tenant = tenant
            user.email = email or user.email

        # Always (re)set password to ensure a known dev credential
        user.set_password(password)
        # Give Django admin access in local/dev contexts
        user.is_staff = True
        user.is_superuser = True
        user.save()

        # Ensure ADMIN role assignment exists
        assign_role(user, Role.ADMIN)

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(f"{action} admin user: {username} (tenant: {user.tenant.name})")
        )
