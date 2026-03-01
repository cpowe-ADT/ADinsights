#!/usr/bin/env python3
"""Wrapper for generate_demo_data with synth_adinsights defaults."""

from __future__ import annotations

import sys
from pathlib import Path

from generate_demo_data import main


def ensure_out_arg(argv: list[str]) -> list[str]:
    if any(arg.startswith("--out") for arg in argv):
        return argv
    default_out = Path(__file__).resolve().parents[1] / "dbt" / "seeds" / "synth_adinsights"
    return [*argv, "--out", str(default_out)]


if __name__ == "__main__":
    raise SystemExit(main(ensure_out_arg(sys.argv[1:])))
