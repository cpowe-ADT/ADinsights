from __future__ import annotations

import scripts.rotate_deks as cli
from core.crypto.kms import KmsError


def test_dry_run_reports_counts(monkeypatch, capsys):
    monkeypatch.setattr(cli, "count_tenant_keys", lambda tenant_id=None: 5)

    exit_code = cli.main(["--dry-run"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "[dry-run] 5 tenant key(s) would be rotated." in captured.out


def test_rotate_single_success(monkeypatch, capsys):
    monkeypatch.setattr(cli, "rotate_single", lambda tenant_id: True)

    exit_code = cli.main(["--tenant-id", "abc123"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Rotated DEK for tenant abc123" in captured.out


def test_rotate_single_failure(monkeypatch, capsys):
    monkeypatch.setattr(cli, "rotate_single", lambda tenant_id: False)

    exit_code = cli.main(["--tenant-id", "missing"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "No tenant key rotated for missing" in captured.err


def test_rotate_all(monkeypatch, capsys):
    monkeypatch.setattr(cli, "rotate_all", lambda: 3)

    exit_code = cli.main([])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Rotated 3 tenant key(s)" in captured.out


def test_smoke_kms_success(monkeypatch, capsys):
    monkeypatch.setattr(cli, "smoke_kms", lambda: True)

    exit_code = cli.main(["--smoke"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "KMS smoke check succeeded." in captured.out


def test_smoke_kms_failure(monkeypatch, capsys):
    monkeypatch.setattr(cli, "smoke_kms", lambda: False)

    exit_code = cli.main(["--smoke"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "KMS smoke check failed." in captured.err


def test_smoke_kms_error(monkeypatch, capsys):
    def raise_kms_error():
        raise KmsError("down")

    monkeypatch.setattr(cli, "smoke_kms", raise_kms_error)

    exit_code = cli.main(["--smoke"])

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "KMS smoke check failed: down" in captured.err
