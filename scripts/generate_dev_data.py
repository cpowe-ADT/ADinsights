#!/usr/bin/env python3
"""Generate synthetic tenant metrics for local development."""

from __future__ import annotations

import argparse
import os
import random
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


PARISHES = [
    "Kingston",
    "St Andrew",
    "St James",
    "Manchester",
    "St Catherine",
    "Clarendon",
]

PLATFORMS = [
    ("Meta", "meta"),
    ("Google Ads", "google"),
    ("TikTok", "tiktok"),
]


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


@dataclass
class GenerationConfig:
    days: int
    campaigns: int
    adsets_per_campaign: int
    ads_per_adset: int
    currency: str
    source_label: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate synthetic performance data for a tenant.",
    )
    parser.add_argument("--tenant-id", help="Tenant UUID to seed.")
    parser.add_argument(
        "--tenant-name",
        help="Tenant name to seed (created if missing).",
    )
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--campaigns", type=int, default=3)
    parser.add_argument("--adsets-per-campaign", type=int, default=1)
    parser.add_argument("--ads-per-adset", type=int, default=1)
    parser.add_argument("--currency", default="JMD")
    parser.add_argument("--source", default="generated")
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument(
        "--start-date",
        help="Override start date (YYYY-MM-DD). Defaults to today - days + 1.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing performance records for the date range before inserting.",
    )
    parser.add_argument(
        "--skip-snapshot",
        action="store_true",
        help="Skip updating the warehouse snapshot payload.",
    )
    return parser.parse_args(argv)


def resolve_tenant(tenant_id: str | None, tenant_name: str | None):
    from accounts.dev_admin import resolve_default_tenant
    from accounts.models import Tenant

    if tenant_id:
        return Tenant.objects.get(id=tenant_id)
    if tenant_name:
        tenant, _ = Tenant.objects.get_or_create(name=tenant_name)
        return tenant
    return resolve_default_tenant()


def ensure_dimensions(tenant, config: GenerationConfig, rng: random.Random):
    from analytics.models import Ad, AdSet, Campaign

    existing_campaigns = list(
        Campaign.objects.filter(tenant=tenant).order_by("created_at")
    )
    needed = max(0, config.campaigns - len(existing_campaigns))
    for idx in range(needed):
        platform, _source = PLATFORMS[(len(existing_campaigns) + idx) % len(PLATFORMS)]
        Campaign.objects.create(
            tenant=tenant,
            external_id=f"gen-cmp-{len(existing_campaigns) + idx + 1}",
            name=f"Generated Campaign {len(existing_campaigns) + idx + 1}",
            platform=platform,
            account_external_id=f"acct-{len(existing_campaigns) + idx + 1}",
            status="Active",
            objective="Awareness",
            currency=config.currency,
        )

    campaigns = list(
        Campaign.objects.filter(tenant=tenant).order_by("created_at")[: config.campaigns]
    )

    for campaign in campaigns:
        adsets = list(
            AdSet.objects.filter(tenant=tenant, campaign=campaign).order_by("created_at")
        )
        adsets_needed = max(0, config.adsets_per_campaign - len(adsets))
        for idx in range(adsets_needed):
            parish = rng.choice(PARISHES)
            AdSet.objects.create(
                tenant=tenant,
                campaign=campaign,
                external_id=f"gen-adset-{campaign.external_id}-{len(adsets) + idx + 1}",
                name=f"{campaign.name} Adset {len(adsets) + idx + 1}",
                status="Active",
                bid_strategy="LOWEST_COST",
                daily_budget=Decimal(str(rng.randint(8000, 25000))),
                targeting={"parish": parish},
            )

        adsets = list(
            AdSet.objects.filter(tenant=tenant, campaign=campaign).order_by("created_at")[
                : config.adsets_per_campaign
            ]
        )
        for adset in adsets:
            ads = list(
                Ad.objects.filter(tenant=tenant, adset=adset).order_by("created_at")
            )
            ads_needed = max(0, config.ads_per_adset - len(ads))
            for idx in range(ads_needed):
                Ad.objects.create(
                    tenant=tenant,
                    adset=adset,
                    external_id=f"gen-ad-{adset.external_id}-{len(ads) + idx + 1}",
                    name=f"{adset.name} Ad {len(ads) + idx + 1}",
                    status="Active",
                    creative={"format": "image"},
                    preview_url="https://example.com/dev/ad-preview",
                )

    return campaigns


def iterate_dates(start: date, days: int) -> list[date]:
    return [start + timedelta(days=offset) for offset in range(days)]


def generate_records(
    tenant,
    campaigns,
    config: GenerationConfig,
    rng: random.Random,
    start: date,
    reset: bool,
):
    from analytics.models import Ad, AdSet, RawPerformanceRecord
    from django.utils import timezone

    if reset:
        RawPerformanceRecord.objects.filter(
            tenant=tenant,
            date__gte=start,
            date__lt=start + timedelta(days=config.days),
        ).delete()

    records = []
    today = timezone.now()
    dates = iterate_dates(start, config.days)

    for campaign in campaigns:
        source = dict(PLATFORMS).get(campaign.platform, config.source_label)
        adsets = list(AdSet.objects.filter(tenant=tenant, campaign=campaign))
        for adset in adsets:
            ads = list(Ad.objects.filter(tenant=tenant, adset=adset))
            for ad in ads:
                for day in dates:
                    impressions = rng.randint(20000, 120000)
                    clicks = max(1, int(impressions * rng.uniform(0.01, 0.08)))
                    conversions = int(clicks * rng.uniform(0.02, 0.15))
                    spend = Decimal(str(round(clicks * rng.uniform(8, 20), 2)))
                    records.append(
                        RawPerformanceRecord(
                            tenant=tenant,
                            external_id=f"{config.source_label}-{ad.external_id}-{day.isoformat()}",
                            date=day,
                            source=source,
                            campaign=campaign,
                            adset=adset,
                            ad=ad,
                            impressions=impressions,
                            clicks=clicks,
                            spend=spend,
                            currency=config.currency,
                            conversions=conversions,
                            raw_payload={},
                            ingested_at=today,
                        )
                    )

    if records:
        RawPerformanceRecord.objects.bulk_create(records, batch_size=500)
    return records


def safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def update_snapshot(tenant, records, config: GenerationConfig):
    from analytics.models import TenantMetricsSnapshot
    from django.utils import timezone

    campaign_totals: dict[str, dict[str, float]] = {}
    ad_totals: dict[str, dict[str, float]] = {}
    parish_totals: dict[str, dict[str, float]] = {}
    trend_totals: dict[str, dict[str, float]] = {}

    for record in records:
        campaign_id = record.campaign.external_id
        ad_id = record.ad.external_id
        parish = (record.adset.targeting or {}).get("parish") or "Unknown"
        date_key = record.date.isoformat()

        def bump(target: dict[str, dict[str, float]], key: str):
            target.setdefault(
                key,
                {
                    "spend": 0.0,
                    "impressions": 0.0,
                    "clicks": 0.0,
                    "conversions": 0.0,
                },
            )
            target[key]["spend"] += float(record.spend)
            target[key]["impressions"] += float(record.impressions)
            target[key]["clicks"] += float(record.clicks)
            target[key]["conversions"] += float(record.conversions)

        bump(campaign_totals, campaign_id)
        bump(ad_totals, ad_id)
        bump(parish_totals, parish)
        bump(trend_totals, date_key)

    campaigns = {c.external_id: c for c in {r.campaign for r in records}}
    ads = {a.external_id: a for a in {r.ad for r in records}}
    campaign_rows = []
    total_spend = 0.0
    total_impressions = 0.0
    total_clicks = 0.0
    total_conversions = 0.0

    for campaign_id, totals in campaign_totals.items():
        campaign = campaigns[campaign_id]
        total_spend += totals["spend"]
        total_impressions += totals["impressions"]
        total_clicks += totals["clicks"]
        total_conversions += totals["conversions"]
        roas = round(safe_divide(totals["conversions"] * 200.0, totals["spend"]), 2)
        ctr = round(safe_divide(totals["clicks"], totals["impressions"]), 4)
        cpc = round(safe_divide(totals["spend"], totals["clicks"]), 2)
        cpm = round(safe_divide(totals["spend"], totals["impressions"]) * 1000, 2)
        campaign_rows.append(
            {
                "id": campaign.external_id,
                "name": campaign.name,
                "platform": campaign.platform,
                "status": campaign.status or "Active",
                "parish": "Multiple",
                "spend": round(totals["spend"], 2),
                "impressions": int(totals["impressions"]),
                "clicks": int(totals["clicks"]),
                "conversions": int(totals["conversions"]),
                "roas": roas,
                "ctr": ctr,
                "cpc": cpc,
                "cpm": cpm,
                "objective": campaign.objective or "",
            }
        )

    trend = [
        {
            "date": key,
            "spend": round(metrics["spend"], 2),
            "conversions": int(metrics["conversions"]),
            "clicks": int(metrics["clicks"]),
            "impressions": int(metrics["impressions"]),
        }
        for key, metrics in sorted(trend_totals.items())
    ]

    creative_rows = []
    for ad_id, totals in ad_totals.items():
        ad = ads[ad_id]
        campaign = ad.adset.campaign
        roas = round(safe_divide(totals["conversions"] * 200.0, totals["spend"]), 2)
        ctr = round(safe_divide(totals["clicks"], totals["impressions"]), 4)
        creative_rows.append(
            {
                "id": ad.external_id,
                "name": ad.name,
                "campaignId": campaign.external_id,
                "campaignName": campaign.name,
                "platform": campaign.platform,
                "parish": (ad.adset.targeting or {}).get("parish") or "Unknown",
                "spend": round(totals["spend"], 2),
                "impressions": int(totals["impressions"]),
                "clicks": int(totals["clicks"]),
                "conversions": int(totals["conversions"]),
                "roas": roas,
                "ctr": ctr,
            }
        )

    budget_rows = []
    for campaign_id, totals in campaign_totals.items():
        campaign = campaigns[campaign_id]
        monthly_budget = max(totals["spend"] * 1.25, totals["spend"] + 10000)
        projected_spend = totals["spend"] * 1.05
        budget_rows.append(
            {
                "id": f"budget-{campaign.external_id}",
                "campaignName": campaign.name,
                "parishes": list(
                    {
                        (ad.adset.targeting or {}).get("parish", "Unknown")
                        for ad in ads.values()
                        if ad.adset.campaign_id == campaign.id
                    }
                ),
                "monthlyBudget": round(monthly_budget, 2),
                "spendToDate": round(totals["spend"], 2),
                "projectedSpend": round(projected_spend, 2),
                "pacingPercent": round(safe_divide(totals["spend"], monthly_budget), 3),
            }
        )

    parish_rows = []
    for parish, totals in parish_totals.items():
        roas = round(safe_divide(totals["conversions"] * 200.0, totals["spend"]), 2)
        parish_rows.append(
            {
                "parish": parish,
                "spend": round(totals["spend"], 2),
                "impressions": int(totals["impressions"]),
                "clicks": int(totals["clicks"]),
                "conversions": int(totals["conversions"]),
                "roas": roas,
                "campaignCount": len(campaign_totals),
                "currency": config.currency,
            }
        )

    payload = {
        "campaign": {
            "summary": {
                "currency": config.currency,
                "totalSpend": round(total_spend, 2),
                "totalImpressions": int(total_impressions),
                "totalClicks": int(total_clicks),
                "totalConversions": int(total_conversions),
                "averageRoas": round(safe_divide(total_conversions * 200.0, total_spend), 2),
            },
            "trend": trend,
            "rows": campaign_rows,
        },
        "creative": creative_rows,
        "budget": budget_rows,
        "parish": parish_rows,
        "snapshot_generated_at": timezone.now().isoformat(),
    }

    TenantMetricsSnapshot.objects.update_or_create(
        tenant=tenant,
        source="warehouse",
        defaults={"payload": payload, "generated_at": timezone.now()},
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_django()

    if not dev_auth_enabled():
        print(
            "Refusing to generate dev data outside DEBUG. "
            "Set DEV_AUTH=1 or ALLOW_DEFAULT_ADMIN=1 to override.",
            file=sys.stderr,
        )
        return 1

    rng = random.Random(args.seed)
    config = GenerationConfig(
        days=max(1, args.days),
        campaigns=max(1, args.campaigns),
        adsets_per_campaign=max(1, args.adsets_per_campaign),
        ads_per_adset=max(1, args.ads_per_adset),
        currency=args.currency,
        source_label=args.source,
    )

    tenant = resolve_tenant(args.tenant_id, args.tenant_name)

    if args.start_date:
        start = date.fromisoformat(args.start_date)
    else:
        start = date.today() - timedelta(days=config.days - 1)

    campaigns = ensure_dimensions(tenant, config, rng)
    records = generate_records(tenant, campaigns, config, rng, start, args.reset)

    if records and not args.skip_snapshot:
        update_snapshot(tenant, records, config)

    print(f"Generated {len(records)} performance records for tenant {tenant.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
