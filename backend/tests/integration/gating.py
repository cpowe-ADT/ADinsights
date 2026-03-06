from __future__ import annotations

import os
from os import PathLike
from collections.abc import Mapping


_TRUTHY_VALUES = {"1", "true", "yes", "y", "on"}
_INTEGRATION_PATH_FRAGMENT = "/tests/integration/"


def integration_tests_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    value = (source.get("RUN_BACKEND_INTEGRATION_TESTS") or "").strip().lower()
    return value in _TRUTHY_VALUES


def is_integration_test_path(path: str | PathLike[str]) -> bool:
    normalized = str(path).replace("\\", "/")
    return _INTEGRATION_PATH_FRAGMENT in normalized or normalized.endswith("/tests/integration")


def should_collect_path(path: str | PathLike[str], env: Mapping[str, str] | None = None) -> bool:
    if not is_integration_test_path(path):
        return True
    return integration_tests_enabled(env)
