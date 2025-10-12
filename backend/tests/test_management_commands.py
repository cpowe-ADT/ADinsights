from __future__ import annotations

from django.core.management import call_command


def test_enable_rls_noop_on_sqlite(capfd):
    call_command("enable_rls")
    captured = capfd.readouterr()
    assert "skipping" in captured.out.lower()
