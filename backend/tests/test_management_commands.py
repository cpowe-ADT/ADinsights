from __future__ import annotations

import pytest

from accounts.models import Role
from django.core.management import call_command


def test_enable_rls_noop_on_sqlite(capfd):
    call_command("enable_rls")
    captured = capfd.readouterr()
    assert "skipping" in captured.out.lower()


@pytest.mark.django_db
def test_seed_roles_creates_default_roles(capfd):
    Role.objects.all().delete()

    call_command("seed_roles")
    captured = capfd.readouterr()

    assert f"seeded {len(Role.ROLE_CHOICES)} default role(s)" in captured.out.lower()
    assert set(Role.objects.values_list("name", flat=True)) == {
        choice[0] for choice in Role.ROLE_CHOICES
    }


@pytest.mark.django_db
def test_seed_roles_is_idempotent(capfd):
    call_command("seed_roles")
    capfd.readouterr()

    call_command("seed_roles")
    captured = capfd.readouterr()

    assert "already present" in captured.out.lower()
    assert Role.objects.count() == len(Role.ROLE_CHOICES)
