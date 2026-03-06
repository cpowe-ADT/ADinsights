from __future__ import annotations

from io import StringIO
import json

import pytest
from django.core.management import call_command as django_call_command

from core.metrics import reset_metrics


@pytest.mark.django_db
def test_backend_release_preflight_invokes_strict_smoke(monkeypatch):
    from analytics.management.commands import backend_release_preflight as command_module

    seeded = {"called": False}
    observed: dict[str, object] = {}

    def fake_seed() -> None:
        seeded["called"] = True

    def fake_call_command(name: str, *args, **kwargs):  # noqa: ANN002, ANN003
        observed["name"] = name
        observed["args"] = args
        observed["kwargs"] = kwargs

    monkeypatch.setattr(command_module, "_seed_required_metrics", fake_seed)
    monkeypatch.setattr(command_module, "call_command", fake_call_command)

    django_call_command("backend_release_preflight")

    assert seeded["called"] is True
    assert observed["name"] == "backend_release_smoke"
    assert observed["args"] == ("--strict-observability",)
    assert "stdout" in observed["kwargs"]


@pytest.mark.django_db
def test_backend_release_preflight_forwards_strict_external(monkeypatch):
    from analytics.management.commands import backend_release_preflight as command_module

    observed: dict[str, object] = {}

    def fake_call_command(name: str, *args, **kwargs):  # noqa: ANN002, ANN003
        observed["name"] = name
        observed["args"] = args
        observed["kwargs"] = kwargs

    monkeypatch.setattr(command_module, "call_command", fake_call_command)

    django_call_command("backend_release_preflight", "--strict-external")

    assert observed["name"] == "backend_release_smoke"
    assert observed["args"] == ("--strict-observability", "--strict-external")


@pytest.mark.django_db
def test_backend_release_preflight_skips_seed_when_requested(monkeypatch):
    from analytics.management.commands import backend_release_preflight as command_module

    seeded = {"called": False}

    def fake_seed() -> None:
        seeded["called"] = True

    monkeypatch.setattr(command_module, "_seed_required_metrics", fake_seed)
    monkeypatch.setattr(command_module, "call_command", lambda *args, **kwargs: None)

    django_call_command("backend_release_preflight", "--no-seed-metrics")

    assert seeded["called"] is False


@pytest.mark.django_db
def test_backend_release_preflight_runs_end_to_end():
    reset_metrics()
    stdout = StringIO()

    django_call_command("backend_release_preflight", stdout=stdout)

    payload = json.loads(stdout.getvalue())
    assert payload["ok"] is True
    assert payload["strict_observability"] is True
    assert payload["missing_metrics"] == []
    assert payload["missing_metric_labels"] == []
