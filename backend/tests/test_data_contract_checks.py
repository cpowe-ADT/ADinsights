from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_airbyte_data_contract_script_passes():
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "infrastructure/airbyte/scripts/check_data_contracts.py"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
