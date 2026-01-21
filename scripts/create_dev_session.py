#!/usr/bin/env python3
"""Create a Django session cookie for a local dev user."""

from __future__ import annotations

import argparse
import os
import sys
from importlib import import_module
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def ensure_django() -> None:
    if "DJANGO_SETTINGS_MODULE" not in os.environ:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()


def truthy(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def dev_auth_enabled() -> bool:
    ensure_django()
    from django.conf import settings

    return bool(settings.DEBUG) or truthy(os.environ.get("DEV_AUTH")) or truthy(
        os.environ.get("ALLOW_DEFAULT_ADMIN")
    )


def find_user(user_id: str | None, username: str | None, email: str | None):
    from accounts.models import User

    if user_id:
        return User.objects.get(id=user_id)
    if username:
        return User.objects.get(username=username)
    if email:
        matches = list(User.objects.filter(email=email))
        if not matches:
            raise User.DoesNotExist
        if len(matches) > 1:
            raise ValueError("Multiple users match email; use --user-id or --username.")
        return matches[0]
    raise ValueError("Provide --user-id, --username, or --email.")


def build_session(user, ttl_seconds: int | None) -> str:
    from django.conf import settings
    from django.contrib.auth import (
        BACKEND_SESSION_KEY,
        HASH_SESSION_KEY,
        SESSION_KEY,
    )

    session_engine = import_module(settings.SESSION_ENGINE)
    session = session_engine.SessionStore()
    session[SESSION_KEY] = str(user.pk)
    session[BACKEND_SESSION_KEY] = settings.AUTHENTICATION_BACKENDS[0]
    session[HASH_SESSION_KEY] = user.get_session_auth_hash()
    if ttl_seconds is not None:
        session.set_expiry(ttl_seconds)
    session.save()
    return session.session_key


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a Django session cookie for a local dev user.",
    )
    parser.add_argument("--user-id", help="User UUID to create a session for.")
    parser.add_argument("--username", help="Username to create a session for.")
    parser.add_argument("--email", help="Email to create a session for.")
    parser.add_argument(
        "--ttl-hours",
        type=int,
        default=12,
        help="Session lifetime in hours (default: 12).",
    )
    parser.add_argument(
        "--ttl-seconds",
        type=int,
        help="Override session lifetime in seconds.",
    )
    parser.add_argument(
        "--cookie",
        action="store_true",
        help="Print a full Cookie header value instead of the raw session key.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_django()

    if not dev_auth_enabled():
        print(
            "Refusing to create dev session outside DEBUG. "
            "Set DEV_AUTH=1 or ALLOW_DEFAULT_ADMIN=1 to override.",
            file=sys.stderr,
        )
        return 1

    try:
        user = find_user(args.user_id, args.username, args.email)
    except Exception as exc:  # noqa: BLE001 - CLI guard
        print(f"Unable to resolve user: {exc}", file=sys.stderr)
        return 1

    ttl_seconds = args.ttl_seconds
    if ttl_seconds is None and args.ttl_hours is not None:
        ttl_seconds = max(0, args.ttl_hours) * 3600

    session_key = build_session(user, ttl_seconds)

    from django.conf import settings

    cookie_name = settings.SESSION_COOKIE_NAME
    output = f"{cookie_name}={session_key}" if args.cookie else session_key
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
