from __future__ import annotations

import pytest

from tests.integration.gating import (
    integration_tests_enabled,
    is_integration_test_path,
    should_collect_path,
)


@pytest.mark.parametrize(
    "raw",
    ["1", "true", "TRUE", "yes", "Y", "on"],
)
def test_integration_gating_accepts_truthy_values(raw):
    assert integration_tests_enabled({"RUN_BACKEND_INTEGRATION_TESTS": raw}) is True


@pytest.mark.parametrize(
    "raw",
    ["", "0", "false", "no", "off", "random"],
)
def test_integration_gating_rejects_non_truthy_values(raw):
    assert integration_tests_enabled({"RUN_BACKEND_INTEGRATION_TESTS": raw}) is False


def test_integration_gating_defaults_to_disabled_when_missing():
    assert integration_tests_enabled({}) is False


def test_is_integration_test_path_detects_backend_integration_paths():
    assert is_integration_test_path("/repo/backend/tests/integration/test_vertical_slice.py") is True
    assert is_integration_test_path(r"C:\repo\backend\tests\integration\test_vertical_slice.py") is True
    assert is_integration_test_path("/repo/backend/tests/test_metrics_api.py") is False


def test_should_collect_path_skips_integration_when_opt_in_missing():
    assert should_collect_path(
        "/repo/backend/tests/integration/test_vertical_slice.py",
        {"RUN_BACKEND_INTEGRATION_TESTS": "0"},
    ) is False
    assert should_collect_path(
        "/repo/backend/tests/test_metrics_api.py",
        {"RUN_BACKEND_INTEGRATION_TESTS": "0"},
    ) is True


def test_should_collect_path_allows_integration_with_opt_in():
    assert should_collect_path(
        "/repo/backend/tests/integration/test_vertical_slice.py",
        {"RUN_BACKEND_INTEGRATION_TESTS": "1"},
    ) is True
