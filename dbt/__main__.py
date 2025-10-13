"""Ensure `python -m dbt` resolves to the installed dbt CLI."""
from __future__ import annotations

import sys
from importlib.machinery import PathFinder
from pathlib import Path


def _extend_namespace() -> None:
    """Add the installed dbt package to this namespace if it exists."""

    package_name = __package__
    if not package_name:
        return

    package = sys.modules.get(package_name)
    if package is None:
        return

    project_location = Path(__file__).resolve().parent
    project_str = str(project_location)

    installed_locations: list[str] = []
    for entry in sys.path:
        spec = PathFinder.find_spec(package_name, [entry])
        if spec is None or spec.submodule_search_locations is None:
            continue

        for location in spec.submodule_search_locations:
            resolved = str(Path(location).resolve())
            if resolved == project_str:
                continue
            if resolved not in installed_locations:
                installed_locations.append(resolved)

    if not installed_locations:
        search_locations = [project_str]
    else:
        search_locations = installed_locations
        if project_str not in search_locations:
            search_locations.append(project_str)

    package.__path__ = search_locations  # type: ignore[attr-defined]

    if getattr(package, "__spec__", None) is not None:
        package.__spec__.submodule_search_locations = package.__path__  # type: ignore[attr-defined]


def main() -> None:
    _extend_namespace()
    from dbt.cli.main import cli

    cli()


if __name__ == "__main__":
    main()
