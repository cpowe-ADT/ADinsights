#!/usr/bin/env python3
"""Command-line helper to rotate tenant data-encryption keys."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

logger = logging.getLogger("rotate_deks")


def ensure_django() -> None:
    """Initialise Django so ORM models can be used."""

    if "DJANGO_SETTINGS_MODULE" not in os.environ:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()


def rotate_all() -> int:
    ensure_django()
    from core.crypto.dek_manager import rotate_all_tenant_deks

    return rotate_all_tenant_deks()


def rotate_single(tenant_id: str) -> bool:
    ensure_django()
    from core.crypto.dek_manager import rotate_tenant_dek

    return rotate_tenant_dek(tenant_id)


def count_tenant_keys(tenant_id: str | None = None) -> int:
    ensure_django()
    from accounts.models import TenantKey

    queryset = TenantKey.all_objects
    if tenant_id:
        queryset = queryset.filter(tenant_id=tenant_id)
    return queryset.count()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rotate tenant data-encryption keys via the configured KMS provider.",
    )
    parser.add_argument(
        "--tenant-id",
        help="Optional tenant UUID to rotate. When omitted every tenant is rotated.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report how many tenant keys would be rotated without making changes.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging output.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if not args.verbose else logging.DEBUG,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.dry_run:
        total = count_tenant_keys(args.tenant_id)
        scope = f"tenant {args.tenant_id}" if args.tenant_id else "all tenants"
        logger.info("[dry-run] %s key(s) would be rotated (%s).", total, scope)
        print(f"[dry-run] {total} tenant key(s) would be rotated.")
        return 0

    if args.tenant_id:
        success = rotate_single(args.tenant_id)
        if not success:
            logger.error("No tenant key rotated for %s", args.tenant_id)
            print(f"No tenant key rotated for {args.tenant_id}", file=sys.stderr)
            return 1
        logger.info("Rotated DEK for tenant %s", args.tenant_id)
        print(f"Rotated DEK for tenant {args.tenant_id}")
        return 0

    rotated = rotate_all()
    logger.info("Rotated %s tenant key(s)", rotated)
    print(f"Rotated {rotated} tenant key(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
