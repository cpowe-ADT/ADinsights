from __future__ import annotations

import pytest

from tests.integration.gating import integration_tests_enabled


@pytest.fixture(autouse=True)
def require_integration_opt_in():
    if not integration_tests_enabled():
        pytest.skip("Set RUN_BACKEND_INTEGRATION_TESTS=1 to run integration tests.")
