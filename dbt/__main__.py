"""Ensure `python -m dbt` resolves to the installed dbt CLI."""
from __future__ import annotations

import sys
from importlib.util import find_spec
from pathlib import Path


def _extend_namespace() -> None:
    package = sys.modules.get(__package__)
    if package is None:
        return

    spec = find_spec(__package__)
    if spec is None or spec.submodule_search_locations is None:
        return

    project_location = str(Path(__file__).resolve().parent)
    locations: list[str] = []

    for location in spec.submodule_search_locations:
        if location not in locations:
            locations.append(location)

    if project_location not in locations:
        locations.append(project_location)

    package.__path__ = locations  # type: ignore[attr-defined]


def main() -> None:
    _extend_namespace()
    from dbt.cli.main import cli

    cli()


if __name__ == "__main__":
    main()
