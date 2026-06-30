"""Currency conversion helpers backed by :class:`DailyFxRate`.

Sprint 6 of Client grouping:
    The Combined view aggregates spend/CPM/CPA across accounts that may bill
    in different currencies (USD, JMD, GBP...). This module normalizes those
    values to a single display currency for the caller.

    The public surface is intentionally minimal — callers pass an amount + a
    source/target currency + a date and get a Decimal back. Batch call sites
    should pre-fetch rates via :func:`load_rate_table` to avoid N+1 queries.

    Missing rates: ``convert`` returns ``None`` so callers can decide whether
    to show a warning banner ("2 accounts billed in JMD — rate unavailable
    for 2026-03-12, totals exclude 18,000 JMD") rather than silently zeroing
    the contribution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from django.db.models import Q

from .models import DailyFxRate


# Money precision — eight decimal places is enough for the tightest major-pair
# rates (e.g. JPY→USD) and matches the DB column.
_FX_PRECISION = Decimal("0.00000001")


def _normalize_ccy(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip().upper()
    if len(candidate) < 3:
        return None
    return candidate


@dataclass(frozen=True)
class RateLookup:
    """Resolved FX rate for a single (date, base, quote) tuple."""

    rate_date: date
    base_currency: str
    quote_currency: str
    rate: Decimal
    # When the requested date had no exact row, this records the fallback
    # date we used (the most recent on-or-before ``rate_date``). UI can show
    # "converted using 2026-03-10 close" when ``used_date != rate_date``.
    used_date: date


def _find_single(
    *,
    on_date: date,
    base: str,
    quote: str,
) -> DailyFxRate | None:
    """Return the freshest rate on-or-before ``on_date`` for the pair."""

    return (
        DailyFxRate.objects
        .filter(base_currency=base, quote_currency=quote, rate_date__lte=on_date)
        .order_by("-rate_date")
        .first()
    )


def resolve_rate(
    *,
    on_date: date,
    base_currency: str,
    quote_currency: str,
) -> RateLookup | None:
    """Find the best available rate to convert ``base`` → ``quote``.

    Resolution order:
        1. Same currency → rate ``Decimal("1")`` (no DB hit).
        2. Direct pair ``(base, quote)`` on-or-before ``on_date``.
        3. Inverse pair ``(quote, base)`` on-or-before ``on_date`` → flipped.

    Triangulation via a third currency is intentionally NOT attempted here —
    propagating two rounding steps introduces pennies of drift which is the
    difference between a tenant trusting the combined total and not. A Celery
    job backfills USD pivots daily; if the direct pair is missing the caller
    should treat the contribution as unconvertible.
    """

    base = _normalize_ccy(base_currency)
    quote = _normalize_ccy(quote_currency)
    if not base or not quote:
        return None

    if base == quote:
        return RateLookup(
            rate_date=on_date,
            base_currency=base,
            quote_currency=quote,
            rate=Decimal("1"),
            used_date=on_date,
        )

    direct = _find_single(on_date=on_date, base=base, quote=quote)
    if direct is not None:
        return RateLookup(
            rate_date=on_date,
            base_currency=base,
            quote_currency=quote,
            rate=direct.rate,
            used_date=direct.rate_date,
        )

    inverse = _find_single(on_date=on_date, base=quote, quote=base)
    if inverse is not None and inverse.rate and inverse.rate > 0:
        flipped = (Decimal("1") / inverse.rate).quantize(_FX_PRECISION)
        return RateLookup(
            rate_date=on_date,
            base_currency=base,
            quote_currency=quote,
            rate=flipped,
            used_date=inverse.rate_date,
        )

    return None


def convert(
    amount: Decimal | float | int | None,
    *,
    from_currency: str | None,
    to_currency: str | None,
    on_date: date,
) -> Decimal | None:
    """Convert ``amount`` from ``from_currency`` to ``to_currency`` on ``on_date``.

    Returns ``None`` when the amount is missing, either currency is missing,
    or no rate is available. Callers distinguish ``None`` (unconvertible,
    warn the user) from ``Decimal("0")`` (zero-valued spend, aggregate as-is).
    """

    if amount is None:
        return None
    if not isinstance(amount, Decimal):
        try:
            amount = Decimal(str(amount))
        except (TypeError, ValueError, ArithmeticError):
            return None

    lookup = resolve_rate(
        on_date=on_date,
        base_currency=from_currency or "",
        quote_currency=to_currency or "",
    )
    if lookup is None:
        return None
    return (amount * lookup.rate).quantize(_FX_PRECISION)


def load_rate_table(
    *,
    currencies: Iterable[str],
    target: str,
    dates: Iterable[date],
) -> dict[tuple[date, str], Decimal]:
    """Pre-fetch a ``(date, ccy) → rate-to-target`` lookup for batch conversion.

    Warehouse/meta_direct adapters aggregate thousands of rows per request;
    calling :func:`convert` per-row would do one query per row. This helper
    issues a single query that covers every ``(from_ccy, to=target)`` pair
    across the requested date window, then fills in gaps by falling back to
    the last known rate (emulating the on-or-before behaviour of
    :func:`resolve_rate`).
    """

    target_norm = _normalize_ccy(target)
    if not target_norm:
        return {}

    ccy_set = {c for c in (_normalize_ccy(x) for x in currencies) if c and c != target_norm}
    date_list = sorted(set(dates))
    if not ccy_set or not date_list:
        return {}

    latest = date_list[-1]

    # Fetch direct pairs covering the window, plus the most recent pre-window
    # row per ccy (to seed on-or-before fallback for the first day).
    direct_rows = list(
        DailyFxRate.objects.filter(
            Q(base_currency__in=ccy_set, quote_currency=target_norm)
            | Q(base_currency=target_norm, quote_currency__in=ccy_set),
            rate_date__lte=latest,
        ).order_by("rate_date")
    )

    # Build per-currency sorted rate list for greedy on-or-before lookup.
    per_ccy_direct: dict[str, list[tuple[date, Decimal]]] = {}
    per_ccy_inverse: dict[str, list[tuple[date, Decimal]]] = {}
    for row in direct_rows:
        if row.base_currency in ccy_set and row.quote_currency == target_norm:
            per_ccy_direct.setdefault(row.base_currency, []).append((row.rate_date, row.rate))
        elif row.quote_currency in ccy_set and row.base_currency == target_norm:
            if row.rate and row.rate > 0:
                per_ccy_inverse.setdefault(row.quote_currency, []).append(
                    (row.rate_date, (Decimal("1") / row.rate).quantize(_FX_PRECISION))
                )

    out: dict[tuple[date, str], Decimal] = {}
    for d in date_list:
        for ccy in ccy_set:
            rate = _pick_on_or_before(per_ccy_direct.get(ccy), d)
            if rate is None:
                rate = _pick_on_or_before(per_ccy_inverse.get(ccy), d)
            if rate is not None:
                out[(d, ccy)] = rate

    return out


def _pick_on_or_before(
    series: list[tuple[date, Decimal]] | None, on_date: date
) -> Decimal | None:
    if not series:
        return None
    # series is sorted ascending by date — walk backwards for the freshest
    # entry on-or-before ``on_date``. Linear is fine for typical ranges.
    chosen: Decimal | None = None
    for rate_date, rate in series:
        if rate_date <= on_date:
            chosen = rate
        else:
            break
    return chosen
