"""Guard rail: GA4 dbt models must only reference the allowlisted columns.

See AGENTS.md §130 (PII policy) and
artifacts/roadmap/ga4-investigation.md for why this test exists.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GA4_STAGING_MODEL = REPO_ROOT / "dbt" / "models" / "staging" / "stg_ga4_reports.sql"
GA4_MART_MODEL = REPO_ROOT / "dbt" / "models" / "marts" / "agg_ga4_daily.sql"

FORBIDDEN_PII_COLUMNS = (
    "user_pseudo_id",
    "device_id",
    "client_id",
    "ip_address",
    "stream_id",
    # "user_id" intentionally omitted — too generic; would match tenant_id/other legit tokens in some dbt macros.
    # The concrete GA4 PII leak vectors we want to block are the five above.
)


@pytest.mark.parametrize("model_path", [GA4_STAGING_MODEL, GA4_MART_MODEL])
def test_ga4_model_exists(model_path: Path) -> None:
    assert model_path.is_file(), f"Expected GA4 dbt model at {model_path}"


@pytest.mark.parametrize("model_path", [GA4_STAGING_MODEL, GA4_MART_MODEL])
@pytest.mark.parametrize("forbidden", FORBIDDEN_PII_COLUMNS)
def test_ga4_model_does_not_reference_pii(model_path: Path, forbidden: str) -> None:
    source = model_path.read_text(encoding="utf-8")
    # Word-boundary match so suffixes/prefixes don't false-positive.
    pattern = re.compile(rf"\b{re.escape(forbidden)}\b", re.IGNORECASE)
    match = pattern.search(source)
    assert match is None, (
        f"GA4 dbt model {model_path.name} references PII column {forbidden!r} "
        f"at offset {match.start() if match else '?'}. "
        "GA4 mart/staging must only reference the PII allowlist "
        "(see docs/runbooks/ga4-operations.md § PII policy)."
    )
