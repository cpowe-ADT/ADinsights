from __future__ import annotations

from django.core.management.base import BaseCommand

from accounts.models import Role


class Command(BaseCommand):
    help = "Seed the default tenant roles required for RBAC flows."

    def handle(self, *args, **options):
        created_roles: list[str] = []

        for role_name, _label in Role.ROLE_CHOICES:
            _role, created = Role.objects.get_or_create(name=role_name)
            if created:
                created_roles.append(role_name)

        if created_roles:
            joined_roles = ", ".join(created_roles)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Seeded {len(created_roles)} default role(s): {joined_roles}"
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS("Default roles already present; nothing to seed.")
        )
