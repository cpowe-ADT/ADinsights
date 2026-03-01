#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from integrations.services.meta_metric_catalog import (  # noqa: E402
    load_metric_catalog,
    metric_catalog_doc_path,
    render_metric_catalog_markdown,
)


def main() -> int:
    catalog = load_metric_catalog()
    output_path = metric_catalog_doc_path()
    output_path.write_text(render_metric_catalog_markdown(catalog))
    print(f"Wrote {len(catalog)} metric definitions to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
