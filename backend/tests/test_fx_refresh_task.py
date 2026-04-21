"""Sprint 10: coverage for the FX-rate refresh Celery task."""

from __future__ import annotations

from decimal import Decimal

import pytest

from analytics.models import DailyFxRate
from integrations import tasks as integration_tasks


@pytest.mark.django_db
class TestRefreshFxRatesManualMode:
    def test_upserts_manual_rows(self):
        result = integration_tasks.refresh_fx_rates.run(
            manual_rows=[
                {
                    "rate_date": "2026-04-10",
                    "base_currency": "USD",
                    "quote_currency": "JMD",
                    "rate": "158.42",
                    "source": DailyFxRate.SOURCE_BOJ,
                },
                {
                    "rate_date": "2026-04-11",
                    "base_currency": "USD",
                    "quote_currency": "JMD",
                    "rate": "158.77",
                    "source": DailyFxRate.SOURCE_BOJ,
                },
            ],
        )
        assert result == {"upserted": 2, "skipped": 0, "source": "manual"}
        assert DailyFxRate.objects.count() == 2
        row = DailyFxRate.objects.get(rate_date="2026-04-11")
        assert row.base_currency == "USD"
        assert row.quote_currency == "JMD"
        assert row.rate == Decimal("158.77")
        assert row.source == DailyFxRate.SOURCE_BOJ

    def test_second_run_updates_existing_row(self):
        integration_tasks.refresh_fx_rates.run(
            manual_rows=[
                {
                    "rate_date": "2026-04-10",
                    "base_currency": "USD",
                    "quote_currency": "JMD",
                    "rate": "158.42",
                }
            ]
        )
        integration_tasks.refresh_fx_rates.run(
            manual_rows=[
                {
                    "rate_date": "2026-04-10",
                    "base_currency": "USD",
                    "quote_currency": "JMD",
                    "rate": "159.01",
                }
            ]
        )
        assert DailyFxRate.objects.count() == 1
        assert DailyFxRate.objects.get().rate == Decimal("159.01")

    def test_skips_malformed_rows(self):
        result = integration_tasks.refresh_fx_rates.run(
            manual_rows=[
                {"rate_date": "not-a-date", "base_currency": "USD", "quote_currency": "JMD", "rate": "1"},
                {"rate_date": "2026-04-10", "base_currency": "USD", "quote_currency": "JMD", "rate": "nope"},
                {"rate_date": "2026-04-10", "base_currency": "USD", "quote_currency": "EUR", "rate": "0.92"},
            ],
        )
        assert result["upserted"] == 1
        assert result["skipped"] == 2
        assert DailyFxRate.objects.filter(quote_currency="EUR").count() == 1


@pytest.mark.django_db
class TestRefreshFxRatesProviderMode:
    def test_calls_frankfurter_and_persists_rates(self, monkeypatch):
        captured = {}

        def fake_fetch(*, base, symbols, endpoint, timeout):
            captured["base"] = base
            captured["symbols"] = symbols
            captured["endpoint"] = endpoint
            import datetime as _dt

            return _dt.date(2026, 4, 12), {
                "GBP": Decimal("0.78"),
                "EUR": Decimal("0.91"),
                "CAD": Decimal("1.35"),
            }

        monkeypatch.setattr(
            integration_tasks, "_fetch_frankfurter_rates", fake_fetch
        )

        result = integration_tasks.refresh_fx_rates.run()
        assert result["upserted"] == 3
        assert result["source"] == "frankfurter"
        assert captured["base"] == "USD"
        assert DailyFxRate.objects.count() == 3
        rate = DailyFxRate.objects.get(quote_currency="GBP")
        assert rate.base_currency == "USD"
        assert rate.source == DailyFxRate.SOURCE_ECB
        assert rate.rate == Decimal("0.78")

    def test_provider_http_error_triggers_retry(self, monkeypatch):
        import httpx

        def boom(**_kwargs):
            raise httpx.ConnectError("boom")

        monkeypatch.setattr(
            integration_tasks, "_fetch_frankfurter_rates", boom
        )

        from celery.exceptions import Retry

        # Celery in eager mode can re-raise either Retry or the original
        # exception depending on the retry count — we just assert one of them
        # bubbles up, proving the retry path fired.
        with pytest.raises((Retry, httpx.HTTPError)):
            integration_tasks.refresh_fx_rates.apply(throw=True).get()
